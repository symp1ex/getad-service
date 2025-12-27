import subprocess
import threading
import json
import time
from websocket import WebSocketApp

SERVER_WS = "ws://10.127.33.42:22233/ws"
CLIENT_ID = "476667a0-ab9f-432a-b008-3787582d7432"
CLIENT_PASSWORD = "112233"

class CMDClient:
    def __init__(self):
        self.cmd = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0
        )

        self.buffer = b""
        self.waiting_keypress = False

        threading.Thread(target=self.read_stdout, daemon=True).start()

        self.ws = WebSocketApp(
            SERVER_WS,
            on_open=self.on_open,
            on_message=self.on_message
        )

    def read_stdout(self):
        while True:
            data = self.cmd.stdout.read(1)
            if data:
                self.buffer += data

    def on_open(self, ws):
        ws.send(json.dumps({
            "type": "client_hello",
            "id": CLIENT_ID,
            "password": CLIENT_PASSWORD
        }))

    def on_message(self, ws, message):
        msg = json.loads(message)

        if msg["type"] == "command":
            self.execute(ws, msg["command"], msg["command_id"])

        elif msg["type"] == "interactive_response":
            if self.waiting_keypress:
                # ВАЖНО: символ + CR, БЕЗ LF
                self.cmd.stdin.write(
                    (msg["command"][:1] + "\r").encode("cp866")
                )
            else:
                # line-based ввод
                self.cmd.stdin.write(
                    (msg["command"] + "\n").encode("cp866")
                )

            self.cmd.stdin.flush()
            self.waiting_keypress = False

    def execute(self, ws, command, command_id):
        self.buffer = b""
        self.cmd.stdin.write((command + "\n").encode("cp866"))
        self.cmd.stdin.flush()

        last_text = ""
        last_change_ts = time.time()

        while True:
            time.sleep(0.1)
            text = self.buffer.decode("cp866", errors="replace")
            lower = text.lower()

            # фиксируем изменение stdout
            if text != last_text:
                last_text = text
                last_change_ts = time.time()

            # === EXISTING Y/N INTERACTIVE ===
            if "?" in lower or "[y" in lower:
                self.waiting_keypress = False
                ws.send(json.dumps({
                    "type": "interactive_prompt",
                    "command_id": command_id,
                    "prompt": text
                }))
                return

            lines = text.splitlines()

            # === GENERIC INTERACTIVE (ожидание нажатия клавиши) ===
            if lines:
                last_line = lines[-1].strip()
                no_prompt = not last_line.endswith(">")
                stalled = (time.time() - last_change_ts) > 0.7

                if stalled and no_prompt:
                    self.waiting_keypress = True
                    ws.send(json.dumps({
                        "type": "interactive_prompt",
                        "command_id": command_id,
                        "prompt": text
                    }))
                    return

            # === EXISTING PROMPT DETECT ===
            if lines and lines[-1].strip().endswith(">"):
                ws.send(json.dumps({
                    "type": "result",
                    "command_id": command_id,
                    "result": {
                        "output": "\n".join(lines[:-1]),
                        "prompt": lines[-1]
                    }
                }))
                return

    def run(self):
        self.ws.run_forever()
