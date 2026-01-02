import about
import os
import subprocess
import threading
import json
import time
from websocket import WebSocketApp

SERVER_WS = "ws://10.127.33.42:22233/ws"
CLIENT_ID = "476667a0-ab9f-432a-b008-3787582d7432"
API_KEY = "123"

config_path = os.path.join(about.current_path, "_resources/remote-access.json")

def send_password_once(password: str):
    done = False

    def on_open(ws):
        ws.send(json.dumps({
            "type": "client_hello",
            "id": CLIENT_ID,
            "api_key": API_KEY,
            "password": password
        }))

    def on_message(ws, message):
        nonlocal done
        msg = json.loads(message)

        # сервер может прислать temp_pass — игнорируем
        done = True
        ws.close()

    ws = WebSocketApp(
        SERVER_WS,
        on_open=on_open,
        on_message=on_message
    )

    ws.run_forever()

    # страховка от зависания
    time.sleep(0.2)

class CmdContextManager:
    def __init__(self):
        self.proc = None
        self.buffer = b""
        self.alive = threading.Event()
        self.reader_thread = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0
        )

        self.alive.set()
        self.reader_thread = threading.Thread(
            target=self._read_stdout,
            daemon=True
        )
        self.reader_thread.start()
        return self

    def _read_stdout(self):
        try:
            while self.alive.is_set():
                data = self.proc.stdout.read(1)
                if not data:
                    break
                self.buffer += data
        except Exception:
            pass

    def write(self, text: str):
        if self.proc and self.proc.stdin:
            self.proc.stdin.write(text.encode("cp866"))
            self.proc.stdin.flush()

    def read(self) -> str:
        return self.buffer.decode("cp866", errors="replace")

    def clear(self):
        self.buffer = b""

    def __exit__(self, exc_type, exc, tb):
        self.alive.clear()
        try:
            if self.proc:
                self.proc.kill()
                self.proc.wait(timeout=1)
        except Exception:
            pass


class CMDClient:
    def __init__(self):
        self.sessions = {}  # admin_id -> CmdContextManager
        self.waiting_keypress = {}

        self.ws = WebSocketApp(
            SERVER_WS,
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close
        )

    def save_temp_pass(self, temp_pass: str):
        data = {
            "temp_pass": temp_pass
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print("Failed to save temp_pass:", e)

    def on_open(self, ws):
        ws.send(json.dumps({
            "type": "client_hello",
            "id": CLIENT_ID,
            "api_key": API_KEY
        }))

    def on_close(self, ws, *args):
        for admin_id, session in list(self.sessions.items()):
            session.__exit__(None, None, None)
            del self.sessions[admin_id]

    def on_message(self, ws, message):
        msg = json.loads(message)

        if msg["type"] == "temp_pass":
            self.save_temp_pass(msg["temp_pass"])
            print("Received temp_pass from server")
            return

        if msg["type"] == "admin_attach":
            admin_id = msg["id"]
            threading.Thread(
                target=self.admin_session,
                args=(admin_id,),
                daemon=True
            ).start()

        elif msg["type"] == "admin_detach":
            admin_id = msg["id"]
            session = self.sessions.pop(admin_id, None)
            if session:
                session.__exit__(None, None, None)

        elif msg["type"] == "command":
            self.execute(
                msg["id"],
                ws,
                msg["command"],
                msg["command_id"]
            )

        elif msg["type"] == "interactive_response":
            session = self.sessions.get(msg["admin_id"])
            if not session:
                return

            if self.waiting_keypress.get(msg["admin_id"]):
                session.write(msg["command"][:1] + "\r")
            else:
                session.write(msg["command"] + "\n")

            self.waiting_keypress[msg["admin_id"]] = False

    def admin_session(self, admin_id):
        try:
            with CmdContextManager() as session:
                self.sessions[admin_id] = session
                self.waiting_keypress[admin_id] = False

                while admin_id in self.sessions:
                    # === КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ===
                    if session.proc.poll() is not None:
                        # cmd.exe завершился (exit / crash)
                        break

                    time.sleep(0.1)

        finally:
            # === УВЕДОМЛЕНИЕ СЕРВЕРА ===
            try:
                self.ws.send(json.dumps({
                    "type": "session_closed",
                    "id": admin_id
                }))
            except Exception:
                pass

            self.sessions.pop(admin_id, None)
            self.waiting_keypress.pop(admin_id, None)

    def execute(self, admin_id, ws, command, command_id):
        session = self.sessions.get(admin_id)
        if not session:
            return

        session.clear()
        session.write(command + "\n")

        last_text = ""
        last_change_ts = time.time()

        while True:
            time.sleep(0.1)
            text = session.read()

            if text != last_text:
                last_text = text
                last_change_ts = time.time()

            lines = text.splitlines()

            if lines and lines[-1].strip().endswith(">"):
                ws.send(json.dumps({
                    "type": "result",
                    "id": admin_id,  # ← ВАЖНО
                    "command_id": command_id,
                    "result": {
                        "output": "\n".join(lines[:-1]),
                        "prompt": lines[-1]
                    }
                }))
                return

            lines = text.splitlines()
            stalled = (time.time() - last_change_ts) > 0.7

            if lines:
                last_line = lines[-1].strip()
                if stalled and not last_line.endswith(">"):
                    self.waiting_keypress[admin_id] = True
                    ws.send(json.dumps({
                        "type": "interactive_prompt",
                        "admin_id": admin_id,
                        "command_id": command_id,
                        "prompt": text
                    }))
                    return

            if lines and lines[-1].strip().endswith(">"):
                ws.send(json.dumps({
                    "type": "result",
                    "admin_id": admin_id,
                    "command_id": command_id,
                    "result": {
                        "output": "\n".join(lines[:-1]),
                        "prompt": lines[-1]
                    }
                }))
                return

    def run(self):
        while True:
            try:
                self.ws = WebSocketApp(
                    SERVER_WS,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_close=self.on_close,
                )

                self.ws.run_forever()
            except Exception as e:
                print("WebSocket error:", e)

            print("Соединение потеряно. Повтор через 10 секунд...")
            time.sleep(10)

