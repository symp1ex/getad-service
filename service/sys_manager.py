import service.logger
import service.configs
import service.tg_notification
import about
import os
import wmi
import pythoncom
import subprocess
from datetime import datetime

class ResourceManagement:
    config_file = "service.json"
    fiscals_file = os.path.join("_resources", "fiscals.json")

    def __init__(self):
        self.config = service.configs.read_config_file(about.current_path, self.config_file,
                                                       service.configs.service_data, create=True)

        self.updater_name = self.config.get("service", {}).get("updater_name", "updater.exe")
        self.reboot_file = self.config.get("service", {}).get("reboot_file", "reboot.bat")

        try: self.notification_enabled = int(self.config.get("notification", {}).get('enabled', 0))
        except: self.notification_enabled = 0

        try: self.delete_days = int(self.config.get("validation_fn", {}).get("delete_days", 21))
        except Exception: self.delete_days = 21

        self.fiscals_data = None

    def get_fiscals_json(self, model_kkt):
        self.fiscals_data = service.configs.read_config_file(about.current_path, self.fiscals_file,
                                                             {model_kkt: []}, create=True)

    def update_correlation_fiscals(self, serialNumber, fn_serial, get_current_time, model_kkt):
        self.get_fiscals_json(model_kkt)

        try:
            # Проверка наличия ключа "fiscals" и добавление новой записи
            if model_kkt not in self.fiscals_data:
                self.fiscals_data[model_kkt] = []

            existing_entry = next((item for item in self.fiscals_data[model_kkt]
                                   if item["serialNumber"] == serialNumber), None)

            if existing_entry:
                # Обновление существующего элемента
                existing_entry["fn_serial"] = fn_serial
                existing_entry["v_time"] = get_current_time
            else:
                # Добавление нового элемента
                self.fiscals_data[model_kkt].append({
                    "serialNumber": serialNumber,
                    "fn_serial": fn_serial,
                    "v_time": get_current_time
                })
            # Запись обновленного содержимого обратно в service.json
            service.configs.write_json_file(self.fiscals_data, self.fiscals_file)
        except Exception:
            service.logger.logger_service.error(f"Не удалось обновить '{self.fiscals_file}'", exc_info=True)

    def disable_check_fr(self, get_current_time, validation_date, serial_number, i):
        self.get_fiscals_json("atol")

        difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                              datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days

        if difference_in_days > self.delete_days:
            service.logger.logger_service.warning(
                f"С последней валидации ФР №{serial_number} прошло более {self.delete_days} дней, запись будет удалена")

            self.fiscals_data["atol"][i] = {
                "serialNumber": "",
                "fn_serial": "",
                "v_time": ""
            }
            service.configs.write_json_file(self.fiscals_data, self.fiscals_file)

            if self.notification_enabled == True:
                service.logger.logger_service.info("Уведомление об удалении будет отправлено в ТГ")
                message = (f"Не удалось проверить ФР №{serial_number} более '{self.delete_days}' дней, дальнейшая проверка "
                           f"будет отключена до следующего успешного подключения к ФР.")
                service.tg_notification.send_tg_message(message)

    def remove_empty_serials_from_file(self):
        self.get_fiscals_json("atol")

        try:
            # Проверяем, есть ли пустые serialNumber
            if 'atol' in self.fiscals_data:
                empty_serials_exist = any(not fiscal.get('serialNumber') for fiscal in self.fiscals_data['atol'])

                # Только если есть пустые serialNumber, фильтруем и перезаписываем файл
                if empty_serials_exist:
                    self.fiscals_data['atol'] = [fiscal for fiscal in self.fiscals_data['atol'] if
                                                 fiscal.get('serialNumber')]
                    service.configs.write_json_file(self.fiscals_data, self.fiscals_file)
        except Exception:
            service.logger.logger_service.error(f"Не удалось очистить конфиг от неактуальных ФР", exc_info=True)

class ProcessManagement(ResourceManagement):
    def __init__(self):
        super().__init__()

    def subprocess_run(self, folder_name, file_name):
        exe_path = os.path.join(about.current_path, folder_name, file_name)
        service.logger.logger_service.info(f"Будет отдана команда на запуск '{exe_path}'")
        try:
            # получаем абсолютный путь к основному файлу скрипта sys.argv[0], а затем с помощью
            # os.path.dirname() извлекаем путь к директории, содержащей основной файл
            working_directory = os.path.join(about.current_path,
                                             folder_name)
            subprocess.Popen(exe_path, cwd=working_directory)
        except Exception:
            service.logger.logger_service.error(f"Не удалось запустить '{exe_path}'", exc_info=True)

    def check_procces(self, file_name):
        try:
            # Инициализируем COM для текущего потока
            pythoncom.CoInitialize()

            try:
                c = wmi.WMI()
                # Ищем процесс по имени
                for process in c.Win32_Process():
                    if process.Name.lower() == file_name.lower():
                        service.logger.logger_service.debug(f"Процесс '{file_name}' активен")
                        return True

                service.logger.logger_service.debug(f"Процесс '{file_name}' неактивен")
                return False

            finally:
                # Освобождаем COM
                pythoncom.CoUninitialize()

        except Exception:
            service.logger.logger_service.error(f"Не удалось получить статус процесса '{file_name}'", exc_info=True)
            return False

    # def check_procces_cycle(self, exe_name):
    #     count_attempt = int(self.action_timeout / 5 + 1)
    #
    #     try:
    #         service.logger.logger_service.updater.info(f"Проверяем активность процесса '{exe_name}'")
    #         for attempt in range(count_attempt):
    #             process_found = self.check_procces(exe_name)
    #
    #             if process_found:
    #                 service.logger.logger_service.debug(f"Cледущая проверка через (5) секунд.")
    #                 time.sleep(5)
    #                 continue
    #             else:
    #                 service.logger.logger_service.info(f"Процесс '{exe_name}' завершил свою работу или не был запущен")
    #                 return True
    #         service.logger.logger_service.warn(
    #             f"Процесс '{exe_name}' остаётся активным в течении ({self.action_timeout}) секунд, "
    #             f"процесс обновления будет прерван")
    #         return False
    #     except Exception:
    #         service.logger.logger_service.error(f"Не удалось отследить состояние процесса '{exe_name}'", exc_info=True)