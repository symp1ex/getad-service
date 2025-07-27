import logger
import json
import os
import subprocess
import about

connect_data = {
    "atol": [
        {
            "type_connect": 0,
            "com_port": "COM4",
            "com_baudrate": "115200",
            "ip": "10.127.1.22",
            "ip_port": "5555",
        },
        {
            "type_connect": 0,
            "com_port": "COM10",
            "com_baudrate": "115200",
            "ip": "10.127.1.100",
            "ip_port": "5555"
        }
    ]
}

service_data = {
    "service": {
        "updater_mode": 1,
        "updater_name": "updater.exe",
        "reboot_file": "reboot.bat",
        "log_level": "info",
        "log_days": 7
    },
    "validation_fn": {
        "enabled": True,
        "interval": 12,
        "trigger_days": 3,
        "target_time": "05:30",
        "delete_days": 21,
        "logs_mask_name": "AtolFiscalRegister",
        "logs_dir": "iiko",
        "serialNumber_key": "serialNumber=",
        "fnNumber_key": "fnNumber="
    },
    "fiscals": []
}

def write_json_file(config, file_name):
    file_path = os.path.join(about.current_path, file_name)
    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=4)
        logger.logger_service.info(f"Данные записаны в '{file_name}'")
        logger.logger_service.debug(config)
    except Exception:
        logger.logger_service.error(f"Не удалось записать данные в '{file_path}'.")

def read_config_file(folder_name, file_name, config_data, create=False):
    json_file = os.path.join(folder_name, file_name)
    try:
        with open(json_file, "r", encoding="utf-8") as file:
            config = json.load(file)
            return config
    except FileNotFoundError:
        logger.logger_service.warn(f"Файл конфига '{json_file}' отсутствует.")
        if create == True:
            create_json_file(folder_name, file_name, config_data)
    except json.JSONDecodeError:
        logger.logger_service.warn(f"Файл конфига '{json_file}' имеет некорректный формат данных")
        if create == True:
            create_json_file(folder_name, file_name, config_data)

def create_json_file(folder_name, file_name, data):
    json_file = os.path.join(folder_name, file_name)
    try:
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
        write_json_file(data, json_file)
    except Exception:
        logger.logger_service.error(f"Не удалось записать данные при создании файла: '{json_file}'", exc_info=True)

def update_correlation_fiscals(serialNumber, fn_serial, get_current_time):
    service_file_name = "service.json"
    service_json_path = about.current_path

    try:
        service_data = read_config_file(service_json_path, service_file_name, "", create=False)

        # Проверка наличия ключа "fiscals" и добавление новой записи
        if "fiscals" not in service_data:
            service_data["fiscals"] = []

        existing_entry = next((item for item in service_data["fiscals"] if item["serialNumber"] == serialNumber), None)

        if existing_entry:
            # Обновление существующего элемента
            existing_entry["fn_serial"] = fn_serial
            existing_entry["v_time"] = get_current_time
        else:
            # Добавление нового элемента
            service_data["fiscals"].append({
                "serialNumber": serialNumber,
                "fn_serial": fn_serial,
                "v_time": get_current_time
            })
        # Запись обновленного содержимого обратно в service.json
        write_json_file(service_data, "service.json")
    except Exception:
        logger.logger_service.error(f"Не удалось обновить '{service_json_path}'", exc_info=True)

def subprocess_run(folder_name, file_name):
    exe_path = os.path.join(about.current_path, folder_name, file_name)
    try:
        working_directory = os.path.join(about.current_path,
                                         folder_name)  # получаем абсолютный путь к основному файлу скрипта sys.argv[0], а затем с помощью os.path.dirname() извлекаем путь к директории, содержащей основной файл
        subprocess.Popen(exe_path, cwd=working_directory)
        logger.logger_service.info(f"Будет запущен '{exe_path}'")
    except Exception:
        logger.logger_service.error(f"Не удалось запустить '{exe_path}'", exc_info=True)



