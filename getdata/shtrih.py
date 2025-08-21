import service.configs
import service.logger
import about
import time

class ShtrihData:
    def __init__(self):
        self.config_name = "service.json"
        self.config = service.configs.read_config_file(about.current_path, self.config_name, service.configs.service_data,
                                                  create=True)
        try: self.enbaled = int(self.config["shtrihscanner"].get("enabled", 1))
        except Exception: self.enbaled = 1

        try: self.timeout = int(self.config["shtrihscanner"].get("timeout", 15))
        except Exception: self.timeout = 15

        self.exe_name = self.config["shtrihscanner"].get("exe_name", "shtrihscanner.exe")

    def run_shtrihscanner(self):
        time.sleep(self.timeout)
        service.configs.subprocess_run("", self.exe_name)

        for attempt in range(18):
            process_found = service.configs.check_procces(self.exe_name)

            if process_found:
                service.logger.logger_service.debug("Cледущая проверка через (5) секунд.")
                time.sleep(5)
                continue
            else:
                service.logger.logger_service.info(f"Процесс '{self.exe_name}' завершил свою работу или не был запущен")
                return
        service.logger.logger_service.warn(f"Процесс '{self.exe_name}' остаётся активным, работа службы будет продолжена")


