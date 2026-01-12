import service.logger
import service.sys_manager
import service.configs
import json
import time
from websocket import WebSocketApp

resourcesmanager = service.sys_manager.ResourceManagement()

encryption_enabled = resourcesmanager.config.get("service", {}).get("noip_connection", {}).get("encryption", False)
SERVER_WS = str(resourcesmanager.config.get("service", {}).get("noip_connection", {}).get("url", ""))
API_KEY = str(resourcesmanager.config.get("service", {}).get("noip_connection", {}).get("api_key", ""))
CLIENT_ID = str(resourcesmanager.get_uuid())


def get_connection_data():
    global SERVER_WS, API_KEY
    try:
        if encryption_enabled == True:
            SERVER_WS = resourcesmanager.decrypt_data(SERVER_WS)
            API_KEY = resourcesmanager.decrypt_data(API_KEY)
            service.logger.logger_service.info("Данные для подключения к NoIP-серверу успешно расшифрованы")
            return
        service.logger.logger_service.warning("Шифрование данных для подключения к NoIP-серверу отключено")
    except Exception:
        service.logger.logger_service.error("Не удалось расшифровать данные для подключения к NoIP-серверу", exc_info=True)


def send_password_once(password: str):
    service.logger.logger_service.info("Сделан запрос на установку постоянного пароля")

    try:
        get_connection_data()
        done = False

        def on_open(ws):
            service.logger.logger_service.info("Соединение с NoIP-сервером установлено, WebSocket открыт")
            ws.send(json.dumps({
                "type": "client_hello",
                "id": CLIENT_ID,
                "api_key": API_KEY,
                "password": password
            }))

        def on_message(ws, message):
            nonlocal done
            msg = json.loads(message)

            if msg.get("type") == "password_updated":
                done = True
                service.logger.logger_service.info("Сервер подтвердил смену пароля")
                ws.close()
                service.logger.logger_service.info("Соединение с NoIP-сервером разорвано, WebSocket закрыт")

        def on_close(ws, code, reason):
            if not done:
                service.logger.logger_service.warning(
                    f"Соединение закрыто без подтверждения смены пароля (code={code}, reason={reason})"
                )

        ws = WebSocketApp(
            SERVER_WS,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close
        )

        ws.run_forever()

        if done:
            service.logger.logger_service.info("Пароль успешно изменён")
        else:
            service.logger.logger_service.warning("Пароль не был подтверждён сервером")

    except Exception:
        service.logger.logger_service.error(
            "Не удалось выполнить запрос на изменение постоянного пароля",
            exc_info=True
        )
