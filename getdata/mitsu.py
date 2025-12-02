import serial
import struct
import socket
import os
import re
import service.logger
import service.configs
import service.sys_manager
import getdata.get_remote
import about


class MitsuConnect(service.sys_manager.ProcessManagement):
    def __init__(self):
        super().__init__()
        self.config_connect = service.configs.read_config_file(about.current_path, "connect.json",
                                                               service.configs.connect_data, create=True)

        try: self.fr_0 = int(self.config_connect.get("mitsu")[0]["type_connect"])
        except: self.fr_0 = 0

        if self.fr_0 != 0:
            self.fr_0_com_port = self.config_connect.get("mitsu")[0]["com_port"]
            self.fr_0_com_baudrate = self.config_connect.get("mitsu")[0]["com_baudrate"]
            self.fr_0_ip = self.config_connect.get("mitsu")[0]["ip"]
            self.fr_0_ip_port = int(self.config_connect.get("mitsu")[0]["ip_port"])


        try: self.fr_1 = int(self.config_connect.get("mitsu")[1]["type_connect"])
        except: self.fr_1 = 0

        if self.fr_1 != 0:
            self.fr_1_com_port = self.config_connect.get("mitsu")[1]["com_port"]
            self.fr_1_com_baudrate = self.config_connect.get("mitsu")[1]["com_baudrate"]
            self.fr_1_ip = self.config_connect.get("mitsu")[1]["ip"]
            self.fr_1_ip_port = int(self.config_connect.get("mitsu")[1]["ip_port"])

    def calculate_lrc(self, data):
        try:
            # Вычисление контрольной суммы LRC (XOR всех байтов)
            lrc = 0
            for byte in data:
                lrc ^= byte
            return lrc
        except Exception:
            service.logger.logger_mitsu.error(f"Не удалось вычислить контрольную сумму LRC", exc_info=True)


    def send_command_to_com(self, command, port, baudrate=115200):
        try:
            # Преобразуем команду в байты (Windows-1251)
            command_bytes = command.encode('cp1251')

            # Формируем пакет
            stx = b'\x02'  # STX (начало пакета)
            length = len(command_bytes)
            length_bytes = struct.pack('<H', length)  # 2 байта, little-endian
            etx = b'\x03'  # ETX (конец пакета)

            # Собираем пакет для расчета LRC
            packet = stx + length_bytes + command_bytes + etx

            # Вычисляем LRC
            lrc = self.calculate_lrc(packet)

            # Добавляем LRC к пакету
            packet += bytes([lrc])

            service.logger.logger_mitsu.info(f"Отправлена команда '{command}' на COM-порт '{port}'")
            # Открываем COM-порт
            with serial.Serial(port, baudrate, timeout=5) as ser:
                # Отправляем пакет
                ser.write(packet)

                # Считываем ответ (без STX и длины)
                response = b''
                while True:
                    byte = ser.read(1)
                    if not byte:
                        break
                    response += byte
                    if len(response) >= 2 and response[-2] == 0x03:  # ETX
                        break

                # Проверяем LRC
                if len(response) >= 2:
                    received_lrc = response[-1]
                    data = response[:-1]
                    calculated_lrc = self.calculate_lrc(data)

                    if received_lrc != calculated_lrc:
                        service.logger.logger_mitsu.warning("Ошибка: неверная контрольная сумма")
                        return None
                    # Возвращаем ответ без ETX и LRC, декодируем из Windows-1251
                    response = data[:-1].decode('cp1251')
                    service.logger.logger_mitsu.debug(f"Получен ответ: '{response}'")
                    return response
                else:
                    service.logger.logger_mitsu.warning("Ответ COM-устройства не подходит под формат")
                    return None

        except Exception:
            service.logger.logger_mitsu.error(f"Не удалось подключиться к ФР", exc_info=True)
            return None


    def send_command_to_ethernet(self, command, host, port):
        try:
            # Преобразуем команду в байты (Windows-1251)
            command_bytes = command.encode('cp1251')

            # Если команда длиннее 535 байт, разбиваем на пакеты
            packets = []
            if len(command_bytes) > 535:
                for i in range(0, len(command_bytes), 535):
                    chunk = command_bytes[i:i + 535]
                    if i + 535 < len(command_bytes):
                        # Не последний пакет, добавляем ETB (0x17)
                        chunk += b'\x17'
                    packets.append(chunk)
            else:
                packets = [command_bytes]

            service.logger.logger_mitsu.info(f"Отправлена команда '{command}' на '{host}:{port}'")
            # Открываем соединение
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                s.settimeout(10)  # Таймаут 10 секунд

                # Отправляем все пакеты
                for packet in packets:
                    s.sendall(packet)

                # Получаем ответ
                response = b''
                while True:
                    chunk = s.recv(1024)
                    if not chunk:
                        break
                    response += chunk

                # Декодируем ответ из Windows-1251
                response_decode = response.decode('cp1251')
                service.logger.logger_mitsu.debug(f"Получен ответ: '{response_decode}'")
                return response_decode

        except Exception:
            service.logger.logger_mitsu.error(f"Не удалось подключиться к ФР", exc_info=True)
            return None


class MitsuGetData(MitsuConnect):
    get_model = "<GET DEV='?' />"
    get_version = "<GET VER='?' />"
    get_reg_data = "<GET REG='?'/>"
    get_fn_data = "<GET INFO='FN'/>"

    def __init__(self):
        super().__init__()
        self.driver_path = "C:\\Program Files\\MITSU.1-F\\MitsuCube.exe"

    def get_driver_version(self):
        driver_version = self.get_file_version(self.driver_path)
        return driver_version

    def get_value_by_tag(self, xml_data, tag):
        try:
            # Очищаем тег от возможных символов
            if tag.startswith('<') and tag.endswith('>'):
                clean_tag = tag[1:-1]
            elif '=' in tag:
                clean_tag = tag.split('=')[0]
            else:
                clean_tag = tag

            # Поиск атрибута
            attr_pattern = rf"{clean_tag}='([^']*)'|{clean_tag}=\"([^\"]*)\""
            attr_match = re.search(attr_pattern, xml_data)
            if attr_match:
                return attr_match.group(1) if attr_match.group(1) is not None else attr_match.group(2)

            # Поиск тега
            tag_pattern = rf"<{clean_tag}>(.*?)</{clean_tag}>"
            tag_match = re.search(tag_pattern, xml_data, re.DOTALL)
            if tag_match:
                return tag_match.group(1)

            return None
        except Exception:
            service.logger.logger_mitsu.error(f"Не удалось извлечь данные из полученного ответа от ККТ", exc_info=True)

    def decode_html_entities(self, text):
        replacements = {
            '&quot;': '"',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&apos;': "'"
        }

        for entity, char in replacements.items():
            text = text.replace(entity, char)
        return text

    def save_to_fiscals_data(self, model, version, reg_data, fn_data):
        try:
            modelDev = self.get_value_by_tag(model, "DEV=")
            modelversion = self.get_value_by_tag(reg_data, "T1188=")
            modelName = f"{modelDev} {modelversion}"

            serialNumber = self.get_value_by_tag(version, "SERIAL=")
            RNM = self.get_value_by_tag(reg_data, "T1037=")

            organizationName_raw = self.get_value_by_tag(reg_data, "<T1048>")
            organizationName = self.decode_html_entities(organizationName_raw)

            fn_serial = self.get_value_by_tag(fn_data, "FN=")
            datetime_reg = self.get_value_by_tag(reg_data, "DATE=")
            dateTime_end = self.get_value_by_tag(fn_data, "VALID=")
            ofdName = self.get_value_by_tag(reg_data, "<T1046>")
            bootVersion = self.get_value_by_tag(version, "VER=")
            ffdVersion = self.get_value_by_tag(reg_data, "T1209=")
            INN = self.get_value_by_tag(reg_data, "T1018=")
            address = self.get_value_by_tag(reg_data, "<T1009>")

            # получаем значение в виде битовой маски
            attributes = int(self.get_value_by_tag(reg_data, "ExtMODE="))
            # проверяем значение 0 и 4 бита
            attribute_excise = bool((attributes >> 0) & 1)
            attribute_marked = bool((attributes >> 4) & 1)

            fnExecution = self.get_value_by_tag(fn_data, "EDITION=")
            hostname = getdata.get_remote.get_hostname()
            url_rms = getdata.get_remote.get_server_url()
            teamviever_id = getdata.get_remote.get_teamviewer_id()
            anydesk_id = getdata.get_remote.get_anydesk_id()
            litemanager_id = getdata.get_remote.get_litemanager_id()
            get_current_time = self.current_time()

            date_json = {
                "modelName": modelName,
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
                "address": str(address),
                "attribute_excise": str(attribute_excise),
                "attribute_marked": str(attribute_marked),
                "fnExecution": str(fnExecution),
                "installed_driver": str(self.get_driver_version()),
                "licenses": "None",
                "hostname": str(hostname),
                "url_rms": str(url_rms),
                "teamviewer_id": str(teamviever_id),
                "anydesk_id": str(anydesk_id),
                "litemanager_id": str(litemanager_id),
                "current_time": str(get_current_time),
                "v_time": str(get_current_time),
                "vc": str(about.version),
                "uuid": self.get_uuid()
            }

            self.rm_old_date()

            folder_name = "date"
            folder_path = os.path.join(about.current_path, folder_name)
            json_name = f"{serialNumber}.json"
            service.configs.create_json_file(folder_path, json_name, date_json)
        except Exception:
            service.logger.logger_mitsu.error(f"Не удалось сохранить информацию от ККТ", exc_info=True)


    def get_data_to_com(self, port, baudrate):
        model = self.send_command_to_com(self.get_model, port, baudrate)
        if model == None:
            service.logger.logger_mitsu.warning(f"Данные от ККТ не были получены, дальнейшая работа прекращена")
            return

        version = self.send_command_to_com(self.get_version, port, baudrate)
        reg_data = self.send_command_to_com(self.get_reg_data, port, baudrate)
        fn_data = self.send_command_to_com(self.get_fn_data, port, baudrate)
        return model, version, reg_data, fn_data

    def get_data_to_ethernet(self, host, port):
        model = self.send_command_to_ethernet(self.get_model, host, port)
        if model == None:
            service.logger.logger_mitsu.warning(f"Данные от ККТ не были получены, дальнейшая работа прекращена")
            return

        version = self.send_command_to_ethernet(self.get_version, host, port)
        reg_data = self.send_command_to_ethernet(self.get_reg_data, host, port)
        fn_data = self.send_command_to_ethernet(self.get_fn_data, host, port)
        return model, version, reg_data, fn_data


    def get_data(self):
        if self.fr_0 not in [1, 2] and self.fr_1 not in [1, 2]:
            service.logger.logger_mitsu.info(f"В файле конфигурации не задан тип подключения к ККТ Mitsu")
            return

        try: type_connect_atol0 = int(self.config_connect["atol"][0].get("type_connect", 0))
        except: type_connect_atol0 = 0

        try: type_connect_atol1 = int(self.config_connect["atol"][1].get("type_connect", 0))
        except: type_connect_atol1 = 0

        if not (type_connect_atol0 == 2 or type_connect_atol1 == 2):
            self.check_network_cycle()

        try:
            if self.fr_0 == 1:
                model, version, reg_data, fn_data = self.get_data_to_com(self.fr_0_com_port, self.fr_0_com_baudrate)
            if self.fr_0 == 2:
                model, version, reg_data, fn_data = self.get_data_to_ethernet(self.fr_0_ip, self.fr_0_ip_port)

            self.save_to_fiscals_data(model, version, reg_data, fn_data)
        except Exception:
            service.logger.logger_mitsu.warning(f"Запрос к первой ККТ завершился ошибкой",
                                                exc_info=True)
        if self.fr_1 not in [1, 2]:
            return

        try:
            if self.fr_1 == 1:
                model_1, version_1, reg_data_1, fn_data_1 = self.get_data_to_com(self.fr_1_com_port, self.fr_1_com_baudrate)
            if self.fr_1 == 2:
                model_1, version_1, reg_data_1, fn_data_1 = self.get_data_to_ethernet(self.fr_1_ip, self.fr_1_ip_port)

            self.save_to_fiscals_data(model_1, version_1, reg_data_1, fn_data_1)
        except Exception:
            service.logger.logger_mitsu.warning(f"Запрос ко второй ККТ завершился ошибкой",
                                                exc_info=True)