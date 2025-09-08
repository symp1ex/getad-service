import service.logger
import service.configs
import service.sys_manager
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
import time

def run_without_arguments():
    shtrihscanner = getdata.shtrih.ShtrihData()
    try:
        service.logger.logger_service.info("Произведён запуск исполняемого файла не от имени службы")

        getdata.atol.atol.get_atol_data()

        if shtrihscanner.enabled == 1:
            shtrihscanner.subprocess_run("", shtrihscanner.exe_name)

            for attempt in range(18):
                process_found = shtrihscanner.check_procces(shtrihscanner.exe_name)
                if process_found:
                    service.logger.logger_service.debug("Cледущая проверка через (5) секунд.")
                    time.sleep(5)
                    continue
                else:
                    service.logger.logger_service.info(f"Процесс '{shtrihscanner.exe_name}' "
                                                       f"завершил свою работу или не был запущен")
                    break
        shtrihscanner.subprocess_run("updater", shtrihscanner.updater_name)
    except Exception:
        service.logger.logger_service.error("Запуск исполняемого файла без аргументов завершился c ошибкой",
                                            exc_info=True)

class Service(win32serviceutil.ServiceFramework):
    _svc_name_ = "MH_Getad"  # Название службы
    _svc_display_name_ = "MH_Getad"  # Отображаемое имя службы
    _svc_description_ = "Check Fiscal Service"  # Описание службы
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
        service.logger.logger_service.debug(f"Рабочая директория: '{service_path}'")
        self.main()

    def main(self):
        validation_fn = service.fn_check.ValidationFn()
        shtrihscanner = getdata.shtrih.ShtrihData()

        try:
            getdata.atol.atol.get_atol_data()

            if shtrihscanner.enabled == 1:
                shtrihscanner.run(self)

            if validation_fn.validation == 1:
                validation_fn.fn_check_process(self)
            else:
                validation_fn.subprocess_run("updater", validation_fn.updater_name)
                self.SvcStop()
        except Exception:
            service.logger.logger_service.critical(f"Запуск основного потока службы завершился с ошибкой",
                                                   exc_info=True)
            os._exit(1)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        run_without_arguments()
    else:
        win32serviceutil.HandleCommandLine(Service)
