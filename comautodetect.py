import logger
import serial.tools.list_ports
from datetime import datetime

def get_com_ports():
    try:
        com_ports = serial.tools.list_ports.comports()
        return [(port.device, port.description) for port in com_ports]
    except Exception:
        logger.logger_getad.error(f"Не удалось получить список COM-портов", exc_info=True)

def get_list_atol():
    try:
        com_ports = get_com_ports()
        atol_ports = []
        if com_ports:
            for port, description in com_ports:
                if 'ATOL' in description:
                    atol_ports.append(port)
        else:
            logger.logger_getad.warn("COM-порты не найдены.")
        return atol_ports
    except Exception:
        logger.logger_getad.error(f"Не удалось получить список com-портов c 'ATOL' в названии", exc_info=True)

def get_atol_port_dict():
    try:
        atol_ports = get_list_atol()
        atol_port_dict = {}  # Создаем словарь для хранения портов

        for i, port in enumerate(atol_ports, start=1):
            atol_port_dict[f"port{i}"] = port
        return atol_port_dict
    except Exception:
        logger.logger_getad.error(f"Не удалось создать словарь со списком com-портов", exc_info=True)

def current_time():
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return timestamp
    except Exception:
        logger.logger_getad.error(f"Не удалось получить текущее время", exc_info=True)
