import service.logger
import service.configs
import service.tg_notification
import about
import os
import wmi
import pythoncom
import subprocess
import socket
import time
from datetime import datetime

class ResourceManagement:
    config_file = "service.json"
    fiscals_file = os.path.join("_resources", "fiscals.json")

    def __init__(self):
        self.config = service.configs.read_config_file(about.current_path, self.config_file,
                                                       service.configs.service_data, create=True)

        self.config_connect = service.configs.read_config_file(about.current_path, "connect.json",
                                                               service.configs.service_data, create=True)

        self.updater_name = self.config.get("service", {}).get("updater_name", "updater.exe")
        self.reboot_file = self.config.get("service", {}).get("reboot_file", "reboot.bat")

        try: self.notification_enabled = int(self.config.get("notification", {}).get('enabled', 0))
        except: self.notification_enabled = 0

        try: self.delete_days = int(self.config.get("validation_fn", {}).get("delete_days", 21))
        except: self.delete_days = 21

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
        try:
            difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                                  datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days

            if difference_in_days > self.delete_days:
                service.logger.logger_service.warning(
                    f"С последней валидации ФР №{serial_number} прошло более {self.delete_days} дней, "
                    f"запись будет удалена")

                self.fiscals_data["atol"][i] = {
                    "serialNumber": "",
                    "fn_serial": "",
                    "v_time": ""
                }
                service.configs.write_json_file(self.fiscals_data, self.fiscals_file)

                if self.notification_enabled == True:
                    service.logger.logger_service.info("Уведомление об удалении будет отправлено в ТГ")
                    message = (f"Не удалось проверить ФР №{serial_number} более '{self.delete_days}' дней, "
                               f"дальнейшая проверка будет отключена до следующего успешного подключения к ФР.")
                    service.tg_notification.send_tg_message(message)
        except Exception:
            service.logger.logger_service.error(f"Не удалось перезаписать '{self.fiscals_file}'", exc_info=True)

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
            service.logger.logger_service.error(f"Не удалось очистить '{self.fiscals_file}' от неактуальных записей",
                                                exc_info=True)

class ProcessManagement(ResourceManagement):
    def __init__(self):
        super().__init__()

        try: self.tcp_timeout = int(self.config_connect.get("tcp_timeout", 30))
        except: self.tcp_timeout = 30

    def subprocess_run(self, folder_name, file_name):
        exe_path = os.path.join(about.current_path, folder_name, file_name)
        service.logger.logger_service.info(f"Будет отдана команда на запуск '{exe_path}'")
        try:
            # получаем абсолютный путь к основному файлу скрипта sys.argv[0], а затем с помощью
            # os.path.dirname() извлекаем путь к директории, содержащей основной файл
            working_directory = os.path.join(about.current_path, folder_name)
            subprocess.Popen(exe_path, cwd=working_directory)
        except Exception:
            service.logger.logger_service.error(f"Не удалось запустить '{exe_path}'", exc_info=True)

    def subprocess_kill(self, folder_name, exe_name):
        service.logger.logger_service.debug(f"Будет отдана команда на завершение процесса: '{exe_name}'")
        try:
            command = f"taskkill /F /IM \"{exe_name}\""
            working_directory = os.path.join(about.current_path, folder_name)
            # Выполняем команду в отдельном процессе
            subprocess.Popen(command, shell=True, cwd=working_directory)
        except Exception:
            service.logger.logger_service.error(f"Не удалось отдать команду на завершение процесса: '{exe_name}'",
                                                exc_info=True)
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

    def check_procces_cycle(self, exe_name, kill_process=False, count_attempt=6):
        try:
            service.logger.logger_service.debug(f"Проверяем активность процесса '{exe_name}'")
            for attempt in range(count_attempt):
                process_found = self.check_procces(exe_name)

                if process_found:
                    if kill_process:
                        self.subprocess_kill("", exe_name)
                    service.logger.logger_service.debug("Cледущая проверка через (5) секунд")
                    time.sleep(5)
                    continue
                else:
                    service.logger.logger_service.debug(f"Процесс '{exe_name}' завершил свою работу или не был запущен")
                    return True
            service.logger.logger_service.warn(
                f"Процесс '{exe_name}' остаётся активным в течении (30) секунд, работа службы будет продолжена")
            return False
        except Exception:
            service.logger.logger_service.error(f"Не удалось отследить состояние процесса '{exe_name}'", exc_info=True)

    def check_network(self):
        try:
            # Создаем UDP-сокет
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            sock.close()
            service.logger.logger_service.debug("Сетевое соединение доступно")
            return True
        except Exception:
            service.logger.logger_service.error("Не удалось проверить доступность сетевого соединения", exc_info=True)
            return False

    def check_network_cycle(self):
        count_attempt = int(self.tcp_timeout / 5 + 1)
        try:
            service.logger.logger_service.debug("Проверяем доступность сетевого соединения")
            for attempt in range(count_attempt):
                network_found = self.check_network()

                if network_found == False:
                    service.logger.logger_service.debug(f"Cледущая проверка через (5) секунд")
                    time.sleep(5)
                    continue
                else:
                    return
            service.logger.logger_service.warn(f"Сетевое соединения остаётся недоступным в течении "
                                               f"({self.tcp_timeout}) секунд. Работа службы будет продолжена")
        except Exception:
            service.logger.logger_service.error("Не удалось проверить доступность сетевого соединения", exc_info=True)
