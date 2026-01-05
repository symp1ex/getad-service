import about
import service.logger
import service.sys_manager
import service.configs
import os
import json
import time
from websocket import WebSocketApp

resourcesmanager = service.sys_manager.ResourceManagement()

config_ra_name = "remote-access.json"
config_ra_path = os.path.join(about.current_path, "_resources", config_ra_name)
config_ra = service.configs.read_config_file(about.current_path, config_ra_path, service.configs.ra_config, create=True)

encryption_enabled = config_ra.get("connection_data", {}).get("encryption", False)

SERVER_WS = str(config_ra.get("connection_data", {}).get("url", ""))
API_KEY = str(config_ra.get("connection_data", {}).get("api_key", ""))
CLIENT_ID = str(resourcesmanager.get_uuid())


def get_connection_data():
    global SERVER_WS, API_KEY
    try:
        if encryption_enabled == True:
            SERVER_WS = resourcesmanager.decrypt_data(SERVER_WS)
            API_KEY = resourcesmanager.decrypt_data(API_KEY)
            service.logger.ra.info("Данные для подключения к NoIP-серверу успешно расшифрованы")
            return
        service.logger.ra.warning("Шифрование данных для подключения к NoIP-серверу отключено")
    except Exception:
        service.logger.ra.error("Не удалось расшифровать данные для подключения к NoIP-серверу", exc_info=True)


def send_password_once(password: str):
    service.logger.ra.info("Сделан запрос на установку постоянного пароля")
    get_connection_data()

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