import service.logger
import service.configs
import service.fn_check
import getdata.atol.atol
import getdata.shtrih
import about
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os

class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "MH_Getad"  # Название службы
    _svc_display_name_ = "MH_Getad"  # Отображаемое имя службы
    _svc_description_ = "MyHoreca Check Fiscal Service"  # Описание службы
    _svc_start_type_ = win32service.SERVICE_AUTO_START  # Автозапуск

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False
        service.logger.logger_service.info("Служба остановлена")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        service.logger.logger_service.info("Служба запущена")
        service.logger.logger_service.info(f"Версия исполянемого файла: {about.version}")
        service_path = os.path.dirname(os.path.abspath(__file__))
        service.logger.logger_service.info(f"Рабочая директория: '{service_path}'")
        self.main()

    def main(self):
        shtrihscanner = getdata.shtrih.ShtrihData()

        config_name = "service.json"
        folder_name = "updater"
        config = service.configs.read_config_file(about.current_path, config_name, service.configs.service_data, create=True)
        exe_name = config["service"].get("updater_name", "updater.exe")

        try: validation = int(config.get("validation_fn").get("enabled", 1))
        except Exception: validation = 1

        try: update_enabled = int(config["service"].get("updater_mode", 1))
        except Exception: update_enabled = 1

        try:
            if update_enabled == 1:
                getdata.atol.atol.get_atol_data()

                if shtrihscanner.enbaled == 1:
                    shtrihscanner.run_shtrihscanner()

                if validation == 1:
                    service.fn_check.fn_check_process(config_name, folder_name, exe_name, self)
            else:
                getdata.atol.atol.get_atol_data()

                if shtrihscanner.enbaled == 1:
                    shtrihscanner.run_shtrihscanner()

                self.SvcStop()
        except Exception:
            service.logger.logger_service.critical(f"Запуск основного потока службы завершился с ошибкой", exc_info=True)
            os._exit(1)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(Service)
