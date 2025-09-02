import service.configs
import service.logger
import about
import time
import win32event

class ShtrihData:
    def __init__(self):
        self.config_service = service.configs.read_config_file(about.current_path, "service.json",
                                                               service.configs.service_data, create=True)
        self.config_connect = service.configs.read_config_file(about.current_path, "connect.json",
                                                               service.configs.service_data, create=True)

        try: self.enabled = int(self.config_service.get("shtrihscanner", {}).get("enabled", 1))
        except Exception: self.enabled = 1

        self.exe_name = self.config_service.get("shtrihscanner", {}).get("exe_name", "shtrihscanner.exe")

    def run(self, service_instance):
        try: timeout = int(self.config_connect.get("timeout_to_ip_port", 15))
        except Exception: timeout = 15

        try: type_connect_atol0 = int(self.config_connect["atol"][0].get("type_connect", 0))
        except Exception: type_connect_atol0 = 0

        try: type_connect_atol1 = int(self.config_connect["atol"][1].get("type_connect", 0))
        except Exception: type_connect_atol1 = 0

        if type_connect_atol0 == 2 or type_connect_atol1 == 2:
            pass
        else:
            service.logger.logger_service.debug(f"Работа службы будет продолжена через ({timeout}) секунд")
            time.sleep(timeout)

        service.configs.subprocess_run("", self.exe_name)

        for attempt in range(18):
            if not service_instance.is_running:
                break

            process_found = service.configs.check_procces(self.exe_name)

            if process_found:
                service.logger.logger_service.debug("Cледущая проверка через (5) секунд.")
                rc = win32event.WaitForSingleObject(service_instance.hWaitStop, 5000)
                if rc == win32event.WAIT_OBJECT_0:
                    break
                continue
            else:
                service.logger.logger_service.info(f"Процесс '{self.exe_name}' завершил свою работу или не был запущен")
                return
        service.logger.logger_service.warn(f"Процесс '{self.exe_name}' остаётся активным в течении (90) секунд, "
                                           f"работа службы будет продолжена")


