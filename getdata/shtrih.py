import service.configs
import service.logger
import service.sys_manager
import win32event
import os
import json


class ShtrihData(service.sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        try: self.enabled = int(self.config.get("shtrihscanner", {}).get("enabled", 1))
        except: self.enabled = 1

        self.exe_name = self.config.get("shtrihscanner", {}).get("exe_name", "shtrihscanner.exe")


    def search_data_shtrih_devices(self):
        service.logger.logger_service.debug("Поиск json информация о ККТ из которых отсутствует в базе")
        # Получаем список всех json файлов в date_path
        if not os.path.exists(self.date_path):
            service.logger.logger_service.warning(f"Директория {self.date_path} не существует")
            return

        all_json_files = [f for f in os.listdir(self.date_path) if f.endswith('.json')]
        service.logger.logger_service.debug(f"Список json в директории '{self.date_path}':")
        service.logger.logger_service.debug(all_json_files)

        # Получаем  serialNumber из fiscals.json
        self.get_fiscals_json()
        registered_serials = []

        # Собираем все serialNumber из всех моделей ККТ в fiscals.json
        for model_kkt in self.fiscals_data:
            for device in self.fiscals_data[model_kkt]:
                if device.get('serialNumber'):
                    registered_serials.append(device.get('serialNumber'))

        # Отфильтровываем файлы, содержащие любые серийные номера из fiscals.json
        unregistered_files = [f for f in all_json_files if
                              not any(serial in f for serial in registered_serials if serial)]

        service.logger.logger_service.debug(f"Список json, данные из которых отсутствуют в базе: {unregistered_files}")

        # Обрабатываем каждый незарегистрированный файл
        for json_file in unregistered_files:
            try:
                file_path = os.path.join(self.date_path, json_file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Извлекаем необходимые данные
                serialNumber = data.get('serialNumber', '')
                if len(serialNumber) != 16:
                    service.logger.logger_service.debug(
                        f"'serialNumber' в json-файле '{file_path}' не принадлежит ККТ Штрих")
                    continue

                fn_serial = data.get('fn_serial', '')
                current_time = data.get('current_time', self.current_time())

                if serialNumber:
                    # Передаем данные в метод для обновления correlations
                    self.update_correlation_fiscals(serialNumber, fn_serial, current_time, 'shtrih')
                    service.logger.logger_service.info(
                        f"В базу добавлено новое устройство Штрих: SN={serialNumber}, FN={fn_serial}")
            except Exception:
                service.logger.logger_service.error(f"Не удалось обработать файл '{json_file}'", exc_info=True)

    def run(self, service_instance):
        try: type_connect_atol0 = int(self.config_connect["atol"][0].get("type_connect", 0))
        except: type_connect_atol0 = 0

        try: type_connect_atol1 = int(self.config_connect["atol"][1].get("type_connect", 0))
        except: type_connect_atol1 = 0

        if not (type_connect_atol0 == 2 or type_connect_atol1 == 2):
            self.check_network_cycle()

        self.subprocess_run("", self.exe_name)

        for attempt in range(18):
            if not service_instance.is_running:
                break

            process_found = self.check_process(self.exe_name)

            if process_found:
                service.logger.logger_service.debug("Cледующая проверка через (5) секунд.")
                rc = win32event.WaitForSingleObject(service_instance.hWaitStop, 5000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                continue
            else:
                service.logger.logger_service.info(f"Процесс '{self.exe_name}' завершил свою работу или не был запущен")
                self.search_data_shtrih_devices()
                return
        service.logger.logger_service.warn(f"Процесс '{self.exe_name}' остаётся активным в течении (90) секунд, "
                                           f"работа службы будет продолжена")
        self.subprocess_kill("", self.exe_name)
        self.search_data_shtrih_devices()
