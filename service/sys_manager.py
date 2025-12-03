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
import winreg
import uuid
import hashlib
from datetime import datetime
import win32api
import shutil

rm_date_flag = 0

class ResourceManagement:
    config_file = "service.json"
    resource_path = "_resources"
    fiscals_file = os.path.join(about.current_path, resource_path, "fiscals.json")
    uuid_file = os.path.join(about.current_path, resource_path, "uuid")

    def __init__(self):
        self.config = service.configs.read_config_file(about.current_path, self.config_file,
                                                       service.configs.service_data, create=True)

        self.config_connect = service.configs.read_config_file(about.current_path, "connect.json",
                                                               service.configs.connect_data, create=True)

        self.updater_name = self.config.get("service", {}).get("updater_name", "updater.exe")
        self.reboot_file = self.config.get("service", {}).get("reboot_file", "reboot.bat")

        try: self.notification_enabled = int(self.config.get("notification", {}).get('enabled', 0))
        except: self.notification_enabled = 0

        try: self.delete_days = int(self.config.get("validation_fn", {}).get("delete_days", 21))
        except: self.delete_days = 21

        self.fiscals_data = None

    def get_fiscals_json(self):
        self.fiscals_data = service.configs.read_config_file(about.current_path, self.fiscals_file,
                                                             {"atol":[],"mitsu":[]}, create=True)

    def update_correlation_fiscals(self, serialNumber, fn_serial, get_current_time, model_kkt):
        self.get_fiscals_json()

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

    def disable_check_fr(self, get_current_time, validation_date, serial_number, i, model_kkt):
        self.get_fiscals_json()
        try:
            difference_in_days = (datetime.strptime(get_current_time, "%Y-%m-%d %H:%M:%S") -
                                  datetime.strptime(validation_date, "%Y-%m-%d %H:%M:%S")).days

            if difference_in_days > self.delete_days:
                service.logger.logger_service.warning(
                    f"С последней валидации ФР №{serial_number} прошло более {self.delete_days} дней, "
                    f"запись будет удалена")

                self.fiscals_data[model_kkt][i] = {
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

    def remove_empty_serials_from_file(self, model_kkt):
        self.get_fiscals_json()

        try:
            # Проверяем, есть ли пустые serialNumber
            if model_kkt in self.fiscals_data:
                empty_serials_exist = any(not fiscal.get('serialNumber') for fiscal in self.fiscals_data[model_kkt])

                # Только если есть пустые serialNumber, фильтруем и перезаписываем файл
                if empty_serials_exist:
                    self.fiscals_data[model_kkt] = [fiscal for fiscal in self.fiscals_data[model_kkt] if
                                                 fiscal.get('serialNumber')]
                    service.configs.write_json_file(self.fiscals_data, self.fiscals_file)
        except Exception:
            service.logger.logger_service.error(f"Не удалось очистить '{self.fiscals_file}' от неактуальных записей",
                                                exc_info=True)

    def get_uuid(self):
        try:
            if os.path.exists(self.uuid_file):
                with open(self.uuid_file, 'r') as f:
                    stored_uuid = f.read().strip()
                    # Проверяем, соответствует ли прочитанное значение формату UUID
                    try:
                        uuid.UUID(stored_uuid)
                        service.logger.logger_service.debug(
                            f"UUID прочитан из файла '{os.path.abspath(self.uuid_file)}': '{stored_uuid}'")
                        return stored_uuid
                    except ValueError:
                        service.logger.logger_service.warning(
                            f"Содержимое файла '{os.path.abspath(self.uuid_file)}' не соответствует формату UUID")
        except Exception:
            service.logger.logger_service.error("Не удалось прочитать файл 'uuid'", exc_info=True)

        try:
            # Получение MAC-адреса
            mac_address = self.get_mac_address()
            service.logger.logger_service.debug(f"Получен MAC-адрес: '{mac_address}'")

            # Читаем MachineGuid из реестра
            registry_path = r"SOFTWARE\Microsoft\Cryptography"
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                registry_path,
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY
            )
            machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            service.logger.logger_service.debug(f"Получено значение 'MachineGuid' из реестра: '{machine_guid}'")
            winreg.CloseKey(key)

            # Комбинируем MAC-адрес и MachineGuid
            combined_id = f"{mac_address}:{machine_guid}"
        except Exception:
            service.logger.logger_service.error(f"Не удалось получить MAC-адрес или MachineGuid", exc_info=True)
            combined_id = machine_guid  # Используем только MachineGuid если возникла ошибка

        try:
            # Хэшируем для стабильного UUID
            hash_bytes = hashlib.sha256(combined_id.encode('utf-8')).digest()
            # Создаём UUID из первых 16 байт хэша
            stable_uuid = uuid.UUID(bytes=hash_bytes[:16])
            service.logger.logger_service.debug(f"Сформирован uuid: '{stable_uuid}'")

            try:
                with open(self.uuid_file, 'w') as f:
                    f.write(str(stable_uuid))
                service.logger.logger_service.debug(
                    f"UUID '{stable_uuid}' записан в файл: '{os.path.abspath(self.uuid_file)}'")
            except Exception:
                service.logger.logger_service.error(
                    f"Не удалось записать UUID в файл '{os.path.abspath(self.uuid_file)}'", exc_info=True)
            return str(stable_uuid)
        except Exception:
            service.logger.logger_service.error(f"Не удалось сгенерировать uuid", exc_info=True)
            return "Error"

    def get_mac_address(self):
        """Получение MAC-адреса сетевого адаптера"""
        try:
            # Инициализация WMI
            pythoncom.CoInitialize()
            try:
                c = wmi.WMI()
                # Получаем все сетевые адаптеры
                for interface in c.Win32_NetworkAdapterConfiguration(IPEnabled=True):
                    if interface.MACAddress:
                        # Возвращаем MAC-адрес первого найденного активного адаптера
                        return interface.MACAddress

                # Если не нашли активный адаптер, ищем любой с MAC-адресом
                for interface in c.Win32_NetworkAdapterConfiguration():
                    if interface.MACAddress:
                        return interface.MACAddress

                return "00:00:00:00:00:00"  # Возвращаем дефолтный MAC, если ничего не нашли
            finally:
                # Освобождаем COM
                pythoncom.CoUninitialize()
        except Exception:
            service.logger.logger_service.error("Не удалось получить MAC-адрес", exc_info=True)
            return "00:00:00:00:00:00"

    def get_file_version(self, file_path):
        try:
            info = win32api.GetFileVersionInfo(file_path, '\\')
            version = info['FileVersionMS'] >> 16, info['FileVersionMS'] & 0xFFFF, info['FileVersionLS'] >> 16, info[
                'FileVersionLS'] & 0xFFFF
            service.logger.logger_getad.debug(f"Получены метаданные файла '{file_path}':\n{info}")
            return '.'.join(map(str, version))
        except Exception:
            service.logger.logger_service.error(f"Не удалось проверить версию файла: '{file_path}'",
                                              exc_info=True)
            return "Error"

    def rm_old_date(self):
        global rm_date_flag

        if rm_date_flag == 1:
            return

        rm_date_flag = 1
        try:
            old_date = os.path.join(about.current_path, "date")
            if os.path.exists(old_date):
                shutil.rmtree(old_date)
                service.logger.logger_getad.info(f"Старые данные успешно удалены")
        except Exception:
            service.logger.logger_getad.error(f"Error: Не удалось удалить старые данные", exc_info=True)

    def current_time(self):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return timestamp
        except Exception:
            service.logger.logger_service.error(f"Не удалось получить текущее время", exc_info=True)

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
    def check_process(self, file_name):
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
            return None

    def check_process_cycle(self, exe_name, kill_process=False, count_attempt=6):
        try:
            service.logger.logger_service.debug(f"Проверяем активность процесса '{exe_name}'")
            for attempt in range(count_attempt):
                process_found = self.check_process(exe_name)

                if process_found:
                    if kill_process:
                        self.subprocess_kill("", exe_name)
                    service.logger.logger_service.debug("Следующая проверка через (5) секунд")
                    time.sleep(5)
                    continue
                elif process_found == False:
                    service.logger.logger_service.debug(f"Процесс '{exe_name}' завершил свою работу или не был запущен")
                    return True
                else:
                    service.logger.logger_service.warn("Статус процесса неизвестен, работа службы будет продолжена")
                    return False
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
                    service.logger.logger_service.debug(f"Cледующая проверка через (5) секунд")
                    time.sleep(5)
                    continue
                else:
                    return
            service.logger.logger_service.warn(f"Сетевое соединение остаётся недоступным в течении "
                                               f"({self.tcp_timeout}) секунд. Работа службы будет продолжена")
        except Exception:
            service.logger.logger_service.error("Не удалось проверить доступность сетевого соединения", exc_info=True)
