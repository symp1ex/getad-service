import service.logger
import service.configs
import service.tg_notification
import getdata.get_remote
import service.sys_manager
from getdata.atol.comautodetect import current_time
import about
import re
import os
import win32event
from datetime import datetime, timedelta


class ValidationFn(service.sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        self.mask_name = self.config.get("validation_fn")['logs_mask_name']
        self.logs_dir = self.config.get("validation_fn")['logs_dir']
        self.serialNumber_key = self.config.get("validation_fn")['serialNumber_key']
        self.fnNumber_key = self.config.get("validation_fn")['fnNumber_key']
        self.target_time = self.config.get("validation_fn", {}).get("target_time", "05:30")

        try: self.validation = int(self.config.get("validation_fn", {}).get("enabled", 1))
        except Exception: self.validation = 1

        try: self.trigger_days = int(self.config.get("validation_fn", {}).get("trigger_days", 3))
        except Exception: self.trigger_days = 3

        try: self.interval_in_hours = int(self.config.get("validation_fn", {}).get("interval", 12))
        except Exception: self.interval_in_hours = 12

        self.time_sleep_ms = None
        self.hh = None
        self.mm = None

    def check_validation_date(self, i):
        try:
            try:
                serialNumber = self.fiscals_data.get("atol")[i]["serialNumber"]
                validation_date = self.fiscals_data.get("atol")[i]["v_time"]
            except Exception:
                service.logger.logger_service.error(f"Не удалось получить значение запрашиваемого ключа из конфига",
                                                    exc_info=True)
                return

            get_current_time = current_time()

            service.logger.logger_service.info(f"Будет произведена валидация ФР №{serialNumber}")
            service.logger.logger_service.debug(f"Дата последней валидации: {validation_date}")
            service.logger.logger_service.debug(f"Количество дней, после которого валидация считается не пройденной: "
                                                f"{self.trigger_days}")

            difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                                  datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days
            valid = difference_in_days < self.trigger_days
            service.logger.logger_service.info(f"Результат валидации ФР №{serialNumber}: '{valid}'")
            return valid
        except Exception:
            service.logger.logger_service.error(f"Не удалось вычислить разницу между текущей датой и датой последней "
                                                f"валидации ФН.", exc_info=True)

    def calc_time_before_reboot(self):
        if self.target_time == 0:
            self.hh = 0
            self.mm = 0
            return

        time_sleep = self.get_seconds_until_next_time()
        self.time_sleep_ms = time_sleep * 1000
        self.hh = int(time_sleep / 3600)
        self.mm = int((time_sleep % 3600) / 60)

    def get_seconds_until_next_time(self):
        try:
            # Получаем текущую дату и время
            current = datetime.strptime(current_time(), "%Y-%m-%d %H:%M:%S")

            try:
                # Разбиваем целевое время на часы и минуты
                target_hour, target_minute = map(int, self.target_time.split(':'))
            except Exception:
                service.logger.logger_service.warn("Не удалось получить из конфига время следующей перезагрузки, "
                                                   "будет использовано дефолтное значение", exc_info=True)
                target_hour = 5
                target_minute = 30
            service.logger.logger_service.debug(f"Получено время следующей перезагрузки: {target_hour}:"
                                                f"{target_minute}")

            # Создаем новую дату с заменой времени на целевое
            target_datetime = current.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)

            # Вычисляем разницу в секундах
            difference = (target_datetime - current).total_seconds()

            if difference != abs(difference):
                # Создаем дату на следующий день
                next_day = current + timedelta(days=1)
                target_datetime = next_day.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
                difference = (target_datetime - current).total_seconds()
                service.logger.logger_service.debug(f"Расчитано время до следующей перезагрузки: {difference} сек.")
                return int(difference)

            service.logger.logger_service.debug(f"Расчитано время до следующей перезагрузки: {difference} сек.")
            return int(difference)
        except Exception:
            service.logger.logger_service.error(f"Не удалось вычислить дату для перезагрузки", exc_info=True)

    def check_fiscal_register(self, i):
        get_current_time = current_time()

        # Получаем значения из JSON
        try:
            serial_number = self.fiscals_data.get("atol")[i]['serialNumber']
            fn_serial = self.fiscals_data.get("atol")[i]['fn_serial']
            validation_date = self.fiscals_data.get("atol")[i]["v_time"]
        except Exception:
            service.logger.logger_service.error(f"Не удалось получить значение запрашиваемого ключа из конфига",
                                                exc_info=True)
            return "skip"

        if self.logs_dir == "iiko":
            target_folder_path = "iiko\\cashserver"
            self.logs_dir = os.path.join(getdata.get_remote.get_user_appdata(target_folder_path),
                                         'iiko', 'Cashserver', 'logs')

        if not os.path.exists(self.logs_dir):
            service.logger.logger_service.warning(
                f"Путь до папки с логами: '{self.logs_dir}' не найден, невозможно провести валидацию")
            self.disable_check_fr(get_current_time, validation_date, serial_number, i)
            return "skip"

        try:
            # Находим все подходящие файлы
            log_files = [
                os.path.join(self.logs_dir, filename)
                for filename in os.listdir(self.logs_dir)
                if self.mask_name in filename and filename.endswith('.log')
            ]

            if not log_files:
                service.logger.logger_service.warning(f"Файл лога, содержащий в названии '%{self.mask_name}%' "
                                                      f"не найден, невозможно провести валидацию")
                self.disable_check_fr(get_current_time, validation_date, serial_number, i)
                return "skip"

            service.logger.logger_service.debug(f"Найденные следующие файлы логов по пути: '{self.logs_dir}'")
            for log_file in log_files:
                service.logger.logger_service.debug(log_file)

            log_days_update = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                               timedelta(days=self.trigger_days))

            # Фильтруем файлы, оставляя только те, которые не старше 3 дней
            recent_files = [
                f for f in log_files
                if datetime.fromtimestamp(os.path.getmtime(f)) > log_days_update
            ]

            if not recent_files:
                service.logger.logger_service.warning(f"Не найдено логов, которые обновлялись бы менее "
                                                      f"'{self.trigger_days}' дней назад")
                self.disable_check_fr(get_current_time, validation_date, serial_number, i)
                return "skip"

            # Находим файл с самой поздней датой изменения
            latest_file = max(recent_files, key=os.path.getmtime)
            service.logger.logger_service.info(f"Будет произведён поиск ФР №{serial_number} по файлу: '{latest_file}'")

            # Регулярка для поиска нужной строки
            pattern = re.compile(
                rf'{re.escape(self.serialNumber_key)}(\d+),.*?{re.escape(self.fnNumber_key)}(\d+)\b'
            )

            with open(latest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        log_serial = match.group(1)
                        log_fn = match.group(2)
                        if log_serial == serial_number:
                            service.logger.logger_service.info(f"Соответствие ФР и ФН проверено: {log_fn == fn_serial}")
                            if log_fn == fn_serial:
                                json_name = f"{serial_number}.json"
                                json_path = os.path.join(about.current_path, "date", json_name)
                                json_file = service.configs.read_config_file(about.current_path, json_path, "",
                                                                             create=False)

                                self.fiscals_data["atol"][i]["v_time"] = get_current_time
                                service.configs.write_json_file(self.fiscals_data, self.fiscals_file)

                                json_file["v_time"] = get_current_time
                                json_file["vc"] = about.version
                                service.configs.write_json_file(json_file, json_path)
                                return True

                            service.logger.logger_service.info(f"Для ФР№{serial_number}, актуальным является ФН №{log_fn}")
                            self.calc_time_before_reboot()
                            if self.notification_enabled == True:
                                service.logger.logger_service.info("Уведомление о не соответствии будет отправлено в ТГ")
                                message = (f"ФР №{serial_number} больше не соответствует ФН №{fn_serial}, "
                                           f"актуальный для него ФН №{log_fn}.\nСистема будете перезагружена "
                                           f"через {self.hh}ч. {self.mm}м.")
                                service.tg_notification.send_tg_message(message)
                            return False

            service.logger.logger_service.warning(f"Запись об ФР №{serial_number}, не найдена в файле '{latest_file}'")
            self.disable_check_fr(get_current_time, validation_date, serial_number, i)
            return "skip"
        except Exception:
            service.logger.logger_service.error(f"Неизвестная ошибка при парсинге лога, мне жаль ;(", exc_info=True)
            return "skip"

    def fn_check_process(self, service_instance):
        self.get_fiscals_json("atol")

        interval = 3600000 * self.interval_in_hours

        try:
            while service_instance.is_running:
                reboot_flag = 0

                for i in range(len(self.fiscals_data.get("atol"))):
                    result_validation = self.check_validation_date(i)
                    if result_validation == False:
                        service.logger.logger_service.info(f"По логам будет произведено сопоставление ФР и ФН")
                        result_correlation = self.check_fiscal_register(i)
                        if result_correlation == False:
                            reboot_flag = 1

                self.subprocess_run("updater", self.updater_name)
                self.remove_empty_serials_from_file()

                if reboot_flag == 1:
                    if self.target_time == 0:
                        self.subprocess_run("_resources", self.reboot_file)
                    else:
                        service.logger.logger_service.info(f"Через {self.hh}ч.{self.mm}м. будет запущен файл "
                                                           f"'{self.reboot_file}'")

                        rc = win32event.WaitForSingleObject(service_instance.hWaitStop, self.time_sleep_ms)
                        if rc == win32event.WAIT_OBJECT_0:
                            break
                        self.subprocess_run("_resources", self.reboot_file)
                service.logger.logger_service.info(f"До следующей проверки осталось {self.interval_in_hours} часов")
                rc = win32event.WaitForSingleObject(service_instance.hWaitStop, interval)
                if rc == win32event.WAIT_OBJECT_0:
                    break
        except Exception:
            service.logger.logger_service.critical(f"Произошло нештатное прерывание основного потока службы",
                                    exc_info=True)
            os._exit(1)
