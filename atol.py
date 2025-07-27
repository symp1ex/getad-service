import logger, configs, about
import json
import os
import shutil
from comautodetect import get_atol_port_dict, current_time
from get_remote import get_server_url, get_teamviewer_id, get_anydesk_id, get_hostname, get_litemanager_id

def file_exists_in_root(filename):
    try:
        root_path = os.path.join(os.getcwd(), filename)  # Получаем путь к файлу в корне
        return os.path.isfile(root_path)  # Возвращает True, если файл существует, иначе False
    except Exception:
        logger.logger_getad.error(f"Не удалось проверить наличие {filename}", exc_info=True)

def status_connect(fptr, port):
    try:
        isOpened = fptr.isOpened()  # спрашиваем состояние подключения
        if isOpened == 1:
            logger.logger_getad.info(f"Соединение с ККТ установлено ({port})")
            return isOpened
        elif isOpened == 0:
            logger.logger_getad.info(f"Соединение с ККТ разорвано ({port})")
            del fptr
            return isOpened
    except Exception:
        logger.logger_getad.error(f"Не удалось проверить статус соединения", exc_info=True)

def checkstatus_getdate(fptr, IFptr, port, installed_version):
    try:
        isOpened = status_connect(fptr, port)  # првоверяем статус подключения к ККТ
        if isOpened == 1:
            get_date_kkt(fptr, IFptr, port, installed_version)  # получаем и сохраняем данные
        elif isOpened == 0:
            del fptr
            return isOpened
    except Exception:
        logger.logger_getad.error(f"Не удалось получить данные из-за ошибки при проверке статуса подключения", exc_info=True)

def connect_kkt(fptr, IFptr, index):
    try:
        file_name = "connect.json"
        config = configs.read_config_file(about.current_path, file_name, configs.connect_data, create=True) or {}  # если нет конфигурации, используем пустой словарь
        connections = config.get("atol")

        settings_map = {
            1: {
                IFptr.LIBFPTR_SETTING_MODEL: IFptr.LIBFPTR_MODEL_ATOL_AUTO,
                IFptr.LIBFPTR_SETTING_PORT: IFptr.LIBFPTR_PORT_COM,
                IFptr.LIBFPTR_SETTING_COM_FILE: connections[index].get("com_port"),
                IFptr.LIBFPTR_SETTING_BAUDRATE: getattr(IFptr,
                                                        "LIBFPTR_PORT_BR_" + str(connections[index].get("com_baudrate"))) if connections[index].get(
                    "com_baudrate") else None
            },
            2: {
                IFptr.LIBFPTR_SETTING_MODEL: IFptr.LIBFPTR_MODEL_ATOL_AUTO,
                IFptr.LIBFPTR_SETTING_PORT: IFptr.LIBFPTR_PORT_TCPIP,
                IFptr.LIBFPTR_SETTING_IPADDRESS: connections[index].get("ip"),
                IFptr.LIBFPTR_SETTING_IPPORT: connections[index].get("ip_port")
            }
        }

        settings = settings_map.get(connections[index].get("type_connect"), {})  # Получаем настройки по типу подключения
        if not settings:  # Если тип подключения не определен в конфигурации
            settings = {
                IFptr.LIBFPTR_SETTING_MODEL: str(IFptr.LIBFPTR_MODEL_ATOL_AUTO),
                IFptr.LIBFPTR_SETTING_PORT: str(IFptr.LIBFPTR_PORT_USB)
            }
            fptr.applySingleSettings()
            fptr.open()  # подключаемся к ККТ
            return "USB"

        if settings:
            settings_str = json.dumps(settings)
            fptr.setSettings(settings_str)
            fptr.applySingleSettings()
            fptr.open()  # подключаемся к ККТ

            ip_with_port = f"{connections[index].get('ip')}:{connections[index].get('ip_port')}"
            return settings.get(IFptr.LIBFPTR_SETTING_COM_FILE, None) or ip_with_port
    except Exception:
        logger.logger_getad.error(f"Не удалось установить соединение с ККТ", exc_info=True)

def get_date_kkt(fptr, IFptr, port, installed_version):
    try:
        # общая инфа об ФР
        fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_STATUS)
        fptr.queryData()

        modelName = fptr.getParamString(IFptr.LIBFPTR_PARAM_MODEL_NAME)  # название модели
        serialNumber = fptr.getParamString(IFptr.LIBFPTR_PARAM_SERIAL_NUMBER)  # серийник ФР

        # запрос регистрационных данных
        fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_REG_INFO)
        fptr.fnQueryData()

        RNM = fptr.getParamString(1037)
        ofdName = fptr.getParamString(1046)
        organizationName = fptr.getParamString(1048)
        INN = fptr.getParamString(1018)
        attribute_excise = fptr.getParamBool(1207)
        attribute_marked = fptr.getParamBool(IFptr.LIBFPTR_PARAM_TRADE_MARKED_PRODUCTS)
    except Exception:
        logger.logger_getad.error(f"Не удалось сделать запрос к ФР", exc_info=True)
        attribute_marked = "Не поддерживается в текущей версии драйвера"

    # запрос общей инфы из ФН
    try:
        fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_FN_INFO)
        fptr.fnQueryData()

        fn_serial = fptr.getParamString(IFptr.LIBFPTR_PARAM_SERIAL_NUMBER)
        fnExecution = fptr.getParamString(IFptr.LIBFPTR_PARAM_FN_EXECUTION)
        # Используйте значение fn_execution здесь
    except Exception:
        # Обработка случая, когда атрибут LIBFPTR_PARAM_FN_EXECUTION отсутствует
        logger.logger_getad.error(f"Не удалось сделать запрос к ФР", exc_info=True)
        fnExecution = "Не поддерживается в текущей версии драйвера"

    # функция запроса даты регистрации, если регистрация была первой
    def datetime_reg_check(fptr):
        try:
            fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_LAST_REGISTRATION)
            fptr.fnQueryData()
            registrationsCount = fptr.getParamInt(IFptr.LIBFPTR_PARAM_REGISTRATIONS_COUNT)
            if registrationsCount == 1:
                dateTime = fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                return dateTime
            else:
                fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE,
                              IFptr.LIBFPTR_FNDT_DOCUMENT_BY_NUMBER)  # запрос информациия о фд 1
                fptr.setParam(IFptr.LIBFPTR_PARAM_DOCUMENT_NUMBER, 1)
                fptr.fnQueryData()
                dateTime = fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)
                return dateTime
        except Exception:
            logger.logger_getad.error(f"Не удалось сделать запрос к ФР", exc_info=True)

    datetime_reg = datetime_reg_check(fptr)

    try:
        # запрос даты окончания ФН
        fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_VALIDITY)
        fptr.fnQueryData()

        dateTime_end = fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_DATE_TIME)

        # # версия загрузчика
        # fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_UNIT_VERSION)
        # fptr.setParam(IFptr.LIBFPTR_PARAM_UNIT_TYPE, IFptr.LIBFPTR_UT_BOOT)
        # fptr.queryData()
        # bootVersion = fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_VERSION)


        # запрос версии конфигурации
        fptr.setParam(IFptr.LIBFPTR_PARAM_DATA_TYPE, IFptr.LIBFPTR_DT_UNIT_VERSION)
        fptr.setParam(IFptr.LIBFPTR_PARAM_UNIT_TYPE, IFptr.LIBFPTR_UT_CONFIGURATION)
        fptr.queryData()

        bootVersion = fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_VERSION)
        #releaseVersion = fptr.getParamString(IFptr.LIBFPTR_PARAM_UNIT_RELEASE_VERSION)


        # запрос версии ФФД
        fptr.setParam(IFptr.LIBFPTR_PARAM_FN_DATA_TYPE, IFptr.LIBFPTR_FNDT_FFD_VERSIONS)
        fptr.fnQueryData()

        ffdVersion = fptr.getParamInt(IFptr.LIBFPTR_PARAM_FFD_VERSION)

        # Вспомогательная функция чтения следующей записи

        def get_license():
            def readNextRecord(fptr, recordsID):
                fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, recordsID)
                return fptr.readNextRecord()

            fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_TYPE, IFptr.LIBFPTR_RT_LICENSES)
            fptr.beginReadRecords()
            recordsID = fptr.getParamString(IFptr.LIBFPTR_PARAM_RECORDS_ID)

            licenses = {}
            while readNextRecord(fptr, recordsID) == IFptr.LIBFPTR_OK:
                id = fptr.getParamInt(IFptr.LIBFPTR_PARAM_LICENSE_NUMBER)
                name = fptr.getParamString(IFptr.LIBFPTR_PARAM_LICENSE_NAME)
                dateFrom = fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_LICENSE_VALID_FROM)
                dateUntil = fptr.getParamDateTime(IFptr.LIBFPTR_PARAM_LICENSE_VALID_UNTIL)

                licenses[id] = {
                    "name": name,
                    "dateFrom": dateFrom.strftime('%Y-%m-%d %H:%M:%S'),  # Преобразование даты в строку
                    "dateUntil": dateUntil.strftime('%Y-%m-%d %H:%M:%S')  # Преобразование даты в строку
                }

            fptr.setParam(IFptr.LIBFPTR_PARAM_RECORDS_ID, recordsID)
            fptr.endReadRecords()

            return licenses

        licenses = get_license()

        fptr.close()
        status_connect(fptr, port)
        del fptr
    except Exception:
        logger.logger_getad.error(f"Не удалось сделать запрос к ФР", exc_info=True)

    logger.logger_getad.info(f"Данные от ККТ получены")

    try:
        hostname, url_rms, teamviever_id, anydesk_id, litemanager_id = get_remote()
        get_current_time = current_time()

        date_json = {
            "modelName": str(modelName),
            "serialNumber": str(serialNumber),
            "RNM": str(RNM),
            "organizationName": str(organizationName),
            "fn_serial": str(fn_serial),
            "datetime_reg": str(datetime_reg),
            "dateTime_end": str(dateTime_end),
            "ofdName": str(ofdName),
            "bootVersion": str(bootVersion),
            "ffdVersion": str(ffdVersion),
            "INN": str(INN),
            "attribute_excise": str(attribute_excise),
            "attribute_marked": str(attribute_marked),
            "fnExecution": str(fnExecution),
            "installed_driver": str(installed_version),
            "licenses": licenses,
            "hostname": str(hostname),
            "url_rms": str(url_rms),
            "teamviewer_id": str(teamviever_id),
            "anydesk_id": str(anydesk_id),
            "litemanager_id": str(litemanager_id),
            "current_time": str(get_current_time),
            "v_time": str(get_current_time),
            "vc": str(about.version)
        }
        folder_name = "date"
        folder_path = os.path.join(about.current_path, folder_name)
        json_name = f"{serialNumber}.json"
        configs.create_json_file(folder_path, json_name, date_json)
    except Exception:
        logger.logger_getad.error(f"Не удалось сохранить информацию от ККТ", exc_info=True)

    configs.update_correlation_fiscals(serialNumber, fn_serial, get_current_time)

def get_date_non_kkt():
    hostname, url_rms, teamviever_id, anydesk_id, litemanager_id = get_remote()
    get_current_time = current_time()

    date_json = {
        "hostname": str(hostname),
        "url_rms": str(url_rms),
        "teamviewer_id": str(teamviever_id),
        "anydesk_id": str(anydesk_id),
        "litemanager_id": str(litemanager_id),
        "current_time": str(get_current_time),
        "vc": str(about.version)
    }
    folder_name = "date"
    folder_path = os.path.join(about.current_path, folder_name)
    json_name = f"TV{teamviever_id}_AD{anydesk_id}.json"
    configs.create_json_file(folder_path, json_name, date_json)

def get_remote():
    try:
        hostname = get_hostname()
        url_rms = get_server_url()
        teamviever_id = get_teamviewer_id()
        anydesk_id = get_anydesk_id()
        litemanager_id = get_litemanager_id()

        #drive = 'C:\\'
        #total_space_gb, free_space_gb = get_disk_info(drive)
        return hostname, url_rms, teamviever_id, anydesk_id, litemanager_id
    except Exception:
        logger.logger_getad.error(f"Не удалось получить данные с хоста", exc_info=True)

def rm_old_date():
    try:
        old_date = os.path.join(about.current_path, "date")
        if os.path.exists(old_date):
            shutil.rmtree(old_date)
            logger.logger_getad.info(f"Старые данные успешно удалены")
    except Exception:
        logger.logger_getad.error(f"Error: Не удалось удалить старые данные", exc_info=True)

def get_atol_data():
    fptr10_path = os.path.join(about.current_path, "fptr10.dll")

    try:
        from libfptr108 import IFptr  # подтягиваем библиотеку от 10.8 и проверяем версию
        if file_exists_in_root(fptr10_path):
            logger.logger_getad.info(f"Будет использоваться приоритетный файл библиотеки '{fptr10_path}'")
            try:
                fptr = IFptr("")
                version_byte = fptr.version()
                installed_version = version_byte.decode()
                del fptr
            except Exception:
                logger.logger_getad.error(f"Не удалось проверить версию установленного драйвера", exc_info=True)
                installed_version = "Error"
            fptr = IFptr(fptr10_path)
        else:
            fptr = IFptr("")
            version_byte = fptr.version()
            installed_version = version_byte.decode()

        version_byte = fptr.version()
        version = version_byte.decode()
        logger.logger_getad.info(f"Инициализирован драйвер версии {version}")

        parts = version.split('.')
        if len(parts) < 3:
            logger.logger_getad.info("Некорректный формат версии")
            return None

        major, minor, patch, null = map(int, parts)

        if major == 10 and minor >= 9:  # если версия от 10.9.0.0 и выше (поддержка ФФД 1.2) то загружаем библиотеку с поддержкой драйвера вплоть до 10.10
            del fptr
            from libfptr109 import IFptr
            if file_exists_in_root(fptr10_path):
                fptr = IFptr(fptr10_path)
            else:
                fptr = IFptr("")
    except ImportError:
        pass
    except Exception:
        logger.logger_getad.error(f"Не удалось инициализировать драйвер", exc_info=True)

    file_name = "connect.json"
    config = configs.read_config_file(about.current_path, file_name, configs.connect_data, create=True)

    try:
        if config is not None and not config.get("atol")[0]["type_connect"] == 0:
            port = connect_kkt(fptr, IFptr, 0) # подключаемся к ККТ
            isOpened = status_connect(fptr, port)
            if isOpened == 1:
                rm_old_date()
                get_date_kkt(fptr, IFptr, port, installed_version)
            if config.get("atol")[1]["type_connect"] in [1, 2]:
                port_2 = connect_kkt(fptr, IFptr, 1)
                isOpened_2 = status_connect(fptr, port_2)
                if isOpened_2 == 1:
                    get_date_kkt(fptr, IFptr, port_2, installed_version)
            if isOpened == 0:
                get_date_non_kkt()
        elif config is not None and config.get("atol")[0]["type_connect"] == 0:
            port_number_ad = get_atol_port_dict()
            if not port_number_ad:
                get_date_non_kkt()
            elif not port_number_ad == {}:
                logger.logger_getad.info(f"Найдены порты: {port_number_ad}")
            baud_rate = config.get("atol")[0]["com_baudrate"]
            check_delete = 0
            for port in port_number_ad.values():
                settings = "{{\"{}\": {}, \"{}\": {}, \"{}\": \"{}\", \"{}\": {}}}".format(
                    IFptr.LIBFPTR_SETTING_MODEL, IFptr.LIBFPTR_MODEL_ATOL_AUTO,
                    IFptr.LIBFPTR_SETTING_PORT, IFptr.LIBFPTR_PORT_COM,
                    IFptr.LIBFPTR_SETTING_COM_FILE, port,
                    IFptr.LIBFPTR_SETTING_BAUDRATE, getattr(IFptr, "LIBFPTR_PORT_BR_" + str(baud_rate)))
                fptr.setSettings(settings)

                fptr.open()

                isOpened = status_connect(fptr, port)
                if isOpened == 1:
                    if check_delete == 0:
                        rm_old_date()
                        check_delete = 1
                    get_date_kkt(fptr, IFptr, port, installed_version)
        else:
            port = connect_kkt(fptr, IFptr, 0)  # подключаемся к ККТ
            isOpened = status_connect(fptr, port)
            if isOpened == 1:
                rm_old_date()
                get_date_kkt(fptr, IFptr, port, installed_version)
            elif isOpened == 0:
                get_date_non_kkt()
    except Exception:
        logger.logger_getad.error(f"Не удалось подключиться к ККТ", exc_info=True)