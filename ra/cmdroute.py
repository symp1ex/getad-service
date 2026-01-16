import about
import service.logger
import service.sys_manager
import service.configs
import os
import subprocess
import threading
import json
import time
import win32event
from websocket import WebSocketApp


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


class CMDClient(service.sys_manager.ResourceManagement):
    config_ra_name = "remote-access.json"

    def __init__(self):
        super().__init__()

        self.config_ra_path = os.path.join(about.current_path, self.resource_path, self.config_ra_name)
        self.config_ra = service.configs.read_config_file(
            about.current_path, self.config_ra_path, service.configs.ra_config, create=True)

        try: self.ra_enabled = int(self.config_ra.get("enabled", False))
        except: self.ra_enabled = 0

        self.encryption_enabled = self.config.get("service", {}).get("noip_connection", {}).get("encryption", False)
        self.server_ws = str(self.config.get("service", {}).get("noip_connection", {}).get("url", ""))
        self.api_key = str(self.config.get("service", {}).get("noip_connection", {}).get("api_key", ""))
        self.client_id = str(self.get_uuid())

        if self.ra_enabled == False:
            service.logger.logger_service.info("Функция удалённого доступа отключена")
        else:
            self.get_connection_data()

        self.sessions = {}  # admin_id -> CmdContextManager
        self.waiting_keypress = {}

        self.ws = WebSocketApp(
            self.server_ws,
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close,
            on_error=self.on_error,
        )

    def get_connection_data(self):
        try:
            if self.encryption_enabled == True:
                self.server_ws = self.decrypt_data(self.server_ws)
                self.api_key = self.decrypt_data(self.api_key)
                service.logger.logger_service.info("Данные для подключения к NoIP-серверу успешно расшифрованы")
                return
            service.logger.logger_service.warning("Шифрование данных для подключения к NoIP-серверу отключено")
        except Exception:
            service.logger.logger_service.error("Не удалось расшифровать данные для подключения к NoIP-серверу", exc_info=True)

    def on_error(self, ws, error):
        err = str(error)

        if "403" in err or "forbidden" in err.lower():
            service.logger.logger_service.critical(
                "Подключение отклонено сервером: IP заблокирован"
            )
            self.ra_enabled = False
            return

        service.logger.logger_service.error(
            f"WebSocket error: {error}"
        )

    def save_temp_pass(self, temp_pass: str):
        service.logger.logger_service.debug(f"Получен временный пароль: {temp_pass}")
        self.config_ra["temp_pass"] = temp_pass
        service.configs.write_json_file(self.config_ra, self.config_ra_path)

    def on_open(self, ws):
        service.logger.logger_service.info("Соединение с NoIP-сервером установлено, WebSocket открыт")
        try:
            ws.send(json.dumps({
                "type": "client_hello",
                "id": self.client_id,
                "api_key": self.api_key
            }))
        except Exception:
            service.logger.logger_service.error("Ошибка при отправке 'client_hello'", exc_info=True)

    def on_close(self, ws, *args):
        try:
            for admin_id, session in list(self.sessions.items()):
                session.__exit__(None, None, None)
                del self.sessions[admin_id]
                service.logger.logger_service.debug("Соединение с NoIP-сервером разорвано, WebSocket закрыт")
        except Exception:
            service.logger.logger_service.error("Возникло неожиданное исключение при попытке закрыть WebSocket",
                                                exc_info=True)

    def on_message(self, ws, message):
        msg = json.loads(message)

        if msg.get("type") == "error":
            service.logger.logger_service.error(
                f"Ошибка от сервера: {msg.get('error')}"
            )
            return

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
            service.logger.logger_service.debug("Получено сообщение на отключение клиента")
            service.logger.logger_service.debug(f"admin_id '{admin_id}'")


        elif msg["type"] == "command":
            admin_id = msg["id"]

            if msg["command"].strip().lower() == "exit":
                session = self.sessions.pop(admin_id, None)
                if session:
                    session.__exit__(None, None, None)
                ws.send(json.dumps({
                    "type": "session_closed",
                    "id": admin_id
                }))
            else:
                self.execute(msg["id"], ws, msg["command"], msg["command_id"])


        elif msg["type"] == "interactive_response":
            admin_id = msg["id"]
            session = self.sessions.get(admin_id)

            if not session:
                return

            if self.waiting_keypress.get(admin_id):
                session.write(msg["command"][:1])
            else:
                session.write(msg["command"] + "\r\n")
            self.waiting_keypress[admin_id] = False

    def admin_session(self, admin_id):
        try:
            with CmdContextManager() as session:
                service.logger.logger_service.info(f"Запущена cmd-сессия для admin_id '{admin_id}'")
                self.sessions[admin_id] = session
                self.waiting_keypress[admin_id] = False

                while admin_id in self.sessions:
                    if session.proc.poll() is not None:
                        # cmd.exe завершился (exit / crash)
                        break

                    time.sleep(0.1)
        except Exception:
            service.logger.logger_service.error(f"Не удалось запустить cmd-сессию для admin_id '{admin_id}'",
                                                exc_info=True)
        finally:
            try:
                service.logger.logger_service.info(f"Закрыта cmd-сессия admin_id '{admin_id}'")
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
            service.logger.logger_service.warning(f"Не найдена cmd-сессия для admin_id '{admin_id}'")
            return

        try:
            session.clear()
            session.write(command + "\r\n")
            service.logger.logger_service.debug(f"Выполнена команда от admin_id '{admin_id}'")
            service.logger.logger_service.debug(f"Command_id: '{command_id}'")
            service.logger.logger_service.debug(f"Command: {command}")
        except Exception:
            service.logger.logger_service.error(f"Не удалось выполнить команду от admin_id '{admin_id}'",
                                                exc_info=True)
            service.logger.logger_service.debug(f"Command: {command}")

            session = self.sessions.pop(admin_id, None)
            if session:
                session.__exit__(None, None, None)
            ws.send(json.dumps({
                "type": "session_closed",
                "id": admin_id
            }))

        interactive_sent = False

        try:
            last_len = 0
            line_buffer = ""
            interactive_sent = False

            while True:
                time.sleep(0.05)

                raw = session.buffer
                if len(raw) <= last_len:
                    continue

                # берём только новые данные
                chunk = raw[last_len:]
                last_len = len(raw)

                text = chunk.decode("cp866", errors="replace")
                line_buffer += text

                # разбиваем на строки
                lines = line_buffer.splitlines(keepends=True)

                # если последняя строка не завершена — оставляем в буфере
                if not lines[-1].endswith(("\n", "\r")):
                    line_buffer = lines.pop()
                else:
                    line_buffer = ""

                for line in lines:
                    # === обычная строка вывода ===
                    ws.send(json.dumps({
                        "type": "result",
                        "id": admin_id,
                        "command_id": command_id,
                        "result": {
                            "output": line
                        }
                    }))
                lines = text.splitlines()

                # === завершение команды ===
                if line_buffer.rstrip().endswith(">"):
                    ws.send(json.dumps({
                        "type": "result",
                        "id": admin_id,
                        "command_id": command_id,
                        "result": {
                            "output": lines[-1],
                            "prompt": ""
                        }
                    }))
                    service.logger.logger_service.debug(
                        "Результат выполнения отправлен на сервер"
                    )
                    return

                if ("?" in text or ". . ." in text) and not interactive_sent:
                    interactive_sent = True
                    self.waiting_keypress[admin_id] = True

                    ws.send(json.dumps({
                        "type": "interactive_prompt",
                        "id": admin_id,
                        "command_id": command_id,
                        "prompt": lines[-1]
                    }))
                    return

        except Exception:
            service.logger.logger_service.error(f"Возникло исключение при обработке ответа от cmd",
                                                exc_info=True)

            session = self.sessions.pop(admin_id, None)
            if session:
                session.__exit__(None, None, None)
            ws.send(json.dumps({
                "type": "session_closed",
                "id": admin_id
            }))

    def run(self, service_instance):
        while service_instance.is_running and self.ra_enabled:
            try:
                self.ws = WebSocketApp(
                    self.server_ws,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_close=self.on_close,
                    on_error=self.on_error,
                )

                self.ws.run_forever()
            except Exception:
                service.logger.logger_service.error("WebSocket error", exc_info=True)

            service.logger.logger_service.warning(
                "Соединение с NoIP-сервером потеряно, повторная попытка подключения через 10 секунд...")

            rc = win32event.WaitForSingleObject(service_instance.hWaitStop, 10000)
            if rc == win32event.WAIT_OBJECT_0:
                break
