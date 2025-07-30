import requests
import logger
import configs
import about
import time
from cryptography.fernet import Fernet

def decrypt_data(encrypted_data):
    try:
        key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=' # ключ
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data).decode()
        return decrypted_data
    except Exception:
        logger.logger_service.error("Не удалось дешифровать данные для подключения к боту", exc_info=True)

def connect_bot(config):
    try: encryption_enbled = int(config["notification"]["authentication"].get("encryption", 1))
    except Exception: encryption_enbled = 1

    try:
        if encryption_enbled == False:
            bot_token = config.get("notification")["authentication"]["bot_token"]
            chat_id = config.get("notification")["authentication"]["chat_id"]
        else:
            bot_token = decrypt_data(config.get("notification")["authentication"]["bot_token"])
            chat_id = decrypt_data(config.get("notification")["authentication"]["chat_id"])
        return bot_token, chat_id
    except Exception:
        logger.logger_service.error("Не удалось дешифровать данные для подключения к боту", exc_info=True)

def request_tg_message(message):
    config_name = "service.json"
    config = configs.read_config_file(about.current_path, config_name, configs.service_data, create=True)

    bot_token, chat_id = connect_bot(config)

    try: max_attempts = int(config["notification"].get("max_attempts", 5))
    except Exception: max_attempts = 5
    try: delay = int(config["notification"].get("delay", 10))
    except Exception: delay = 10


    for attempt in range(max_attempts):
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            params = {
                "chat_id": chat_id,
                "text": message
            }

            response = requests.get(url, params=params)
            result = response.json()

            # Вывод полного ответа API
            logger.logger_service.debug("Ответ от API Telegram:")
            logger.logger_service.debug(result)

            # Проверка статуса отправки
            if result.get('ok'):
                logger.logger_service.info("Уведомление в телеграм успешно отправлено")
                logger.logger_service.debug(f"\n\n{message}")
            else:
                logger.logger_service.error(f"Не удалось отправить уведомление: {result.get('description')}")

            return result
        except Exception:
            current_attempt = attempt + 1
            if attempt < max_attempts - 1:
                logger.logger_service.warning(
                    f"Попытка ({current_attempt}) отправить уведомление не удалась. Повторная попытка через ({delay}) секунд")
                time.sleep(delay)
                delay *= 2
                continue
            logger.logger_service.error("Не удалось сделать запрос к API Telegram", exc_info=True)

def send_tg_delete(serialNumber, delete_days):
    import get_remote

    try:
        url_rms = get_remote.get_server_url()
        teamviever_id = get_remote.get_teamviewer_id()
        anydesk_id = get_remote.get_anydesk_id()
        litemanager_id = get_remote.get_litemanager_id()

        message = (f"Не удалось проверить ФР №{serialNumber} более '{delete_days}' дней, дальнейшая проверка будет отключена до следующего успешного подключения к ФР. \n\n"
                   f"RMS: {url_rms}\n"
                   f"TV: {teamviever_id}\n"
                   f"AD: {anydesk_id}\n"
                   f"LM: {litemanager_id}\n")

        request_tg_message(message)
    except Exception:
        logger.logger_service.error("Не удалось сформировать сообщение для отправки уведомления", exc_info=True)