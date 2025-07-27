import logger
import re
import os
import win32event
from comautodetect import current_time
from datetime import datetime, timedelta
import configs
import about
import get_remote

def check_validation_date(config, i):
    try:
        serialNumber = config.get("fiscals")[i]["serialNumber"]
        validation_date = config.get("fiscals")[i]["v_time"]
        get_current_time = current_time()
        trigger_days = config["validation_fn"].get("trigger_days", 3)

        logger.logger_service.info(f"Будет произведена проверка валидации для ФР №{serialNumber}")
        logger.logger_service.debug(f"Дата последней валидации: {validation_date}")
        logger.logger_service.debug(f"Количество дней, после которого валидация считается не пройденной: {trigger_days}")

        difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") - datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days
        valid = difference_in_days < trigger_days
        logger.logger_service.info(f"Результат проверки валидации для ФР №{serialNumber}: '{valid}'")
        return valid
    except Exception:
        logger.logger_service.error(f"Не удалось вычислить разницу между текущей датой и датой последней валидации ФН.", exc_info=True)

def check_fiscal_register(config, i, file_name):
    # Получаем значения из JSON
    serial_number = config.get("fiscals")[i]['serialNumber']
    fn_serial = config.get("fiscals")[i]['fn_serial']
    validation_date = config.get("fiscals")[i]["v_time"]
    mask_name = config.get("validation_fn")['logs_mask_name']
    logs_dir = config.get("validation_fn")['logs_dir']
    serialNumber_key = config.get("validation_fn")['serialNumber_key']
    fnNumber_key = config.get("validation_fn")['fnNumber_key']
    delete_days = config["validation_fn"].get("delete_days", 21)
    get_current_time = current_time()

    if logs_dir == "iiko":
        target_folder_path = "iiko\\cashserver"
        logs_dir = os.path.join(get_remote.get_user_appdata(target_folder_path), 'iiko', 'Cashserver', 'logs')

    try:
        # Находим все подходящие файлы
        log_files = [
            os.path.join(logs_dir, filename)
            for filename in os.listdir(logs_dir)
            if mask_name in filename and filename.endswith('.log')
        ]

        if not log_files:
            logger.logger_service.warning(f"Файл лога, содержащий в названии %{mask_name}% не найден, невозможно провести валидацию")
            return "skip"

        logger.logger_service.debug(f"Найденные следущие файлы логов по пути: {logs_dir}")
        for log_file in log_files:
            logger.logger_service.debug(log_file)

        # Находим файл с самой поздней датой изменения
        latest_file = max(log_files, key=os.path.getmtime)
        logger.logger_service.info(f"Будет произведён поиск ФР №{serial_number} по файлу: '{latest_file}'")

        # Регулярка для поиска нужной строки
        pattern = re.compile(
            rf'{re.escape(serialNumber_key)}(\d+),.*?{re.escape(fnNumber_key)}(\d+)\b'
        )

        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                match = pattern.search(line)
                if match:
                    log_serial = match.group(1)
                    log_fn = match.group(2)
                    if log_serial == serial_number:
                        logger.logger_service.info(f"Соответствие ФР и ФН проверено: {log_fn == fn_serial}")
                        if log_fn == fn_serial:
                            json_name = f"{serial_number}.json"
                            json_path = os.path.join(about.current_path, "date", json_name)
                            json_file = configs.read_config_file(about.current_path, json_path, "", create=False)

                            config["fiscals"][i]["v_time"] = get_current_time
                            configs.write_json_file(config, file_name)

                            json_file["v_time"] = get_current_time
                            configs.write_json_file(json_file, json_path)
                            return True
                        return False

        logger.logger_service.warning(f"Запись об ФР №{serial_number}, не найдена в файле {latest_file}")

        difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                              datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days

        if difference_in_days > delete_days:
            logger.logger_service.warning(
                f"С последней валидации ФР №{serial_number} прошло более {delete_days} дней, запись будет удалена")

            config["fiscals"][i] = {
                "serialNumber": "",
                "fn_serial": "",
                "v_time": ""
            }
            configs.write_json_file(config, file_name)
        return "skip"
    except Exception:
        logger.logger_service.error(f"Неизвестная ошибка при парсинге лога, мне жаль ;(",
                                    exc_info=True)
        return "skip"

def fn_check_process(config_name, folder_name, exe_name, service_instance):
    config = configs.read_config_file(about.current_path, config_name, configs.service_data, create=True)
    update_enabled = config["service"].get("updater_mode", 1)

    interval_in_hours = config["validation_fn"].get("interval", 24)
    interval = 3600000 * interval_in_hours

    try:
        while service_instance.is_running:
            update_flag = 0
            reboot_flag = 0

            for i in range(len(config.get("fiscals"))):
                result_validation = check_validation_date(config, i)
                if result_validation == False:
                    logger.logger_service.info(f"По логам будет произведено сопоставление ФР и ФН")
                    result_correlation = check_fiscal_register(config, i, config_name)
                    if result_correlation == True:
                        update_flag = 1
                    if result_correlation == False:
                        reboot_flag = 1

            remove_empty_serials_from_file()

            if update_flag == 1:
                if update_enabled == 2:
                    config = configs.read_config_file(about.current_path, config_name, configs.service_data, create=True)
                    config["service"]["updater_mode"] = 333
                    configs.write_json_file(config, config_name)
                configs.subprocess_run(folder_name, exe_name)
            if reboot_flag == 1:
                reboot_file = config["service"].get("reboot_file", "reboot.bat")
                target_time = config["validation_fn"].get("target_time", "05:30")

                time_sleep = get_seconds_until_next_time(target_time)
                time_sleep_ms = time_sleep * 1000
                logger.logger_service.info(f"Через {time_sleep / 3600} часов будет запущен файл '{reboot_file}'")

                rc = win32event.WaitForSingleObject(service_instance.hWaitStop, time_sleep_ms)
                if rc == win32event.WAIT_OBJECT_0:
                    break

                logger.logger_service.info(f"Будет запущен файл '{reboot_file}'")
                configs.subprocess_run("", reboot_file)

            logger.logger_service.info(f"До следующей проверки осталось {interval_in_hours} часов")
            rc = win32event.WaitForSingleObject(service_instance.hWaitStop, interval)
            if rc == win32event.WAIT_OBJECT_0:
                break
    except Exception:
        logger.logger_service.critical(f"Произошло нештатное прерывание основного потока",
                                exc_info=True)
        os._exit(1)

def get_seconds_until_next_time(target_time):
    try:
        # Получаем текущую дату и время
        current = datetime.strptime(current_time(), "%Y-%m-%d %H:%M:%S")

        # Создаем дату на следующий день
        next_day = current + timedelta(days=1)

        # Разбиваем целевое время на часы и минуты
        target_hour, target_minute = map(int, target_time.split(':'))

        # Создаем новую дату с заменой времени на целевое
        target_datetime = next_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

        # Вычисляем разницу в секундах
        difference = (target_datetime - current).total_seconds()

        return int(difference)
    except Exception:
        logger.logger_service.error(f"Не удалось вычислить дату для перезагрузки",
                                    exc_info=True)

def remove_empty_serials_from_file():
    config_name = "service.json"
    config = configs.read_config_file(about.current_path, config_name, configs.service_data, create=True)

    try:
        # Проверяем, есть ли пустые serialNumber
        if 'fiscals' in config:
            empty_serials_exist = any(not fiscal.get('serialNumber') for fiscal in config['fiscals'])

            # Только если есть пустые serialNumber, фильтруем и перезаписываем файл
            if empty_serials_exist:
                config['fiscals'] = [fiscal for fiscal in config['fiscals'] if fiscal.get('serialNumber')]
                configs.write_json_file(config, config_name)
    except Exception:
        logger.logger_service.error(f"Не удалось очистить конфиг от неактуальных ФР",
                                    exc_info=True)