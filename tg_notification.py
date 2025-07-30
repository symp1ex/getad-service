import requests
import logger
import configs
import about


def request_tg_message(message):
    config_name = "service.json"
    config = configs.read_config_file(about.current_path, config_name, configs.service_data, create=True)

    bot_token = config.get("notification")['bot_token']
    chat_id = config.get("notification")['chat_id']

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
            logger.logger_service.info("Уведомление в телеграм успешно отправлено!")
            logger.logger_service.debug(f"\n\n{message}")
        else:
            logger.logger_service.error(f"Не удалось отправить уведомление: {result.get('description')}")

        return result
    except Exception:
        logger.logger_service.error("Не удалось сделать запрос к API Telegram", exc_info=True)

def send_tg_delete(serialNumber, delete_days):
    import get_remote

    try:
        url_rms = get_remote.get_server_url()
        teamviever_id = get_remote.get_teamviewer_id()
        anydesk_id = get_remote.get_anydesk_id()
        litemanager_id = get_remote.get_litemanager_id()

        message = (f"Не удалось проверить ФР №{serialNumber} более '{delete_days}' дней, дальнейшая проверка будет отключена до следующего успешного подключения. \n\n"
                   f"RMS: {url_rms}\n"
                   f"TV: {teamviever_id}\n"
                   f"AD: {anydesk_id}\n"
                   f"LM: {litemanager_id}\n")

        request_tg_message(message)
    except Exception:
        logger.logger_service.error("Не сформировать сообщение для отправки уведомления", exc_info=True)