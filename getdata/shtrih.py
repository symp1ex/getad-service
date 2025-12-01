import service.configs
import service.logger
import service.sys_manager
import win32event

class ShtrihData(service.sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        try: self.enabled = int(self.config.get("shtrihscanner", {}).get("enabled", 1))
        except: self.enabled = 1

        self.exe_name = self.config.get("shtrihscanner", {}).get("exe_name", "shtrihscanner.exe")

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
                return
        service.logger.logger_service.warn(f"Процесс '{self.exe_name}' остаётся активным в течении (90) секунд, "
                                           f"работа службы будет продолжена")
        self.subprocess_kill("", self.exe_name)
