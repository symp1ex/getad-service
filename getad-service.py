import logger
import configs
import fn_check
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import sys
import os
import atol

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
        logger.logger_service.info("Служба остановлена")

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        logger.logger_service.info("Служба запущена")
        service_path = os.path.dirname(os.path.abspath(__file__))
        logger.logger_service.info(f"Рабочая директория: '{service_path}'")
        self.main()

    def main(self):
        config_name = "service.json"
        folder_name = "updater"
        config = configs.read_config_file(logger.current_path, config_name, configs.service_data, create=True)
        exe_name = config["service"].get("updater_name", "updater.bat")

        validation = config.get("validation_fn").get("enabled", 1)
        update_enabled = config["service"].get("update", 1)

        try:
            if update_enabled == 2:
                atol.get_atol_data()
                config = configs.read_config_file(logger.current_path, config_name, configs.service_data, create=True)
                config["service"]["update"] = 666
                configs.write_json_file(config, config_name)
                configs.subprocess_run(folder_name, exe_name)
            elif update_enabled == 666:
                config["service"]["update"] = 2
                configs.write_json_file(config, config_name)
                if validation == 1:
                    fn_check.fn_check_process(config_name, folder_name, exe_name, self)
            elif update_enabled == 1:
                atol.get_atol_data()
                configs.subprocess_run(folder_name, exe_name)
                if validation == 1:
                    fn_check.fn_check_process(config_name, folder_name, exe_name, self)
            else:
                atol.get_atol_data()
                self.SvcStop()
        except Exception:
            logger.logger_service.critical(f"Что-то пошло сильно не так", exc_info=True)
            os._exit(1)

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(Service)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(Service)
