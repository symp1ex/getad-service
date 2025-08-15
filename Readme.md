# getad-service

## Описание
Утилита для автоматического получения данных с фискальных регистраторов АТОЛ, работающая в режиме службы Windows. Поддерживается работа с двумя ФР.

Подключение к ФР происходит только при запуске службы. В остальное время служба, с заданным в днях интервалом, сопоставляет по свежим логам номер ФР к номеру ФН и отправляет на сервер подтверждение, если ФН всё ещё актуален. При обнаружении замены ФН планируется перезагрузка в ближайшую ночь, для повторного подключения и получения свежих данных от ФР.

Функционал проверялся только при работе с логами iikoFront. Технически должно работать с любым логом, в котором есть записи содержащие номер ФР и номер ФН в пределах одной строки со спецефическими ключами перед ними.

<details>
<summary>Пример получаемого json при подключении к ККТ</summary>

```json
  {
    "modelName": "АТОЛ 22 v2 Ф",
    "serialNumber": "00123456790012",
    "RNM": "0000000001036518",
    "organizationName": "ООО Предприятие",
    "fn_serial": "7380440700067159",
    "datetime_reg": "2024-04-13 07:20:00",
    "dateTime_end": "2099-12-31 00:00:00",
    "ofdName": "ООО Эвотор ОФД",
    "bootVersion": "5.8.100",
    "ffdVersion": "105",
    "INN": "1111222233  ",
    "attribute_excise": "True",
    "attribute_marked": "False",
    "fnExecution": "Эмулятор ФН с поддержкой ФФД 1.2",
    "installed_driver": "10.9.1.0",
    "licenses": {
        "1": {
            "name": "Фискальные функции",
            "dateFrom": "2018-11-21 00:00:00",
            "dateUntil": "2038-01-19 03:14:07"
        },
        "10": {
            "name": "ФФД 1.2",
            "dateFrom": "2019-12-26 00:00:00",
            "dateUntil": "2038-01-19 03:14:07"
        }
    },
    "hostname": "Isaac-LT",
    "url_rms": "https://resto.iiko.it:443/resto",
    "teamviewer_id": "111222333",
    "anydesk_id": "222333444",
    "litemanager_id": "ID_1111",
    "current_time": "2024-05-05 21:57:25",
    "v_time": "2024-05-05 21:57:25"
}
```
(bootVersion - начиная с версии 1.1.0.4 не является версией загрузчика, теперь это версия конфигурации.)

</details>

## Установка и настройка

### Требования
- Windows 7/8/10/11 (На `Win7` и `Embedded` может появиться сообщение об ошибке при запуске, тогда понадобится установка обновления безопасности `KB3063858`. Гуглится по номеру обновления и названию Винды, весит 900кб. Для `Win7` отдельный установщик, для `Embedded` отдельный)

- Установленный драйвер АТОЛ версии 10.7.0.0+ 
	(или библиотека драйвера `fptr10.dll` подходящей версии, расположенная в корне с исполняемым файлом службы)

- Python 3.8.10+ 32-bit (не требуется, если служба запускается из исполняемого `.exe-файла`)

### Команды управления службой
```bash
# Установка службы
python getad-service.py install

# Запуск службы
python getad-service.py start

# Остановка службы
python getad-service.py stop

# Удаление службы
python getad-service.py remove

# Запуск в debug-режиме
python getad-service.py debug

# Пользователь
python getad-service.py --username domain\user

#Для установки с автозапуском
python getad-service.py --startup auto install 
```
<details>
<summary>Тоже самое работает если служба собрана в <b>.exe-файл</b></summary>
  
```bash
# Установка службы
getad-service.exe install

# Запуск службы
getad-service.exe start

# Остановка службы
getad-service.exe stop

# Удаление службы
getad-service.exe remove

# Запуск в debug-режиме
getad-service.exe debug

# Пользователь
getad-service.exe --username domain\user

#Для установки с автозапуском
getad-service.exe --startup auto install 
```

</details>

## Конфигурация

### connect.json
<details>
<summary>Настройки подключения к ККТ</summary>

```json
{
    "timeout_to_ip_port": 15,
    "atol": [
        {
            "type_connect": 0,
            "com_port": "COM4",
            "com_baudrate": "115200",
            "ip": "192.168.1.1",
            "ip_port": "5555"
        },
        {
            "type_connect": 0,
            "com_port": "COM10",
            "com_baudrate": "115200",
            "ip": "192.168.1.2",
            "ip_port": "5555"
        }
    ]
}
```

Параметры:
- `timeout_to_ip_port`: задержка перед подключением по IP (в секундах)
- `type_connect`: тип подключения (0 - автопоиск на виртуальных COM-портах, 1 - COM-порт, 2 - TCP/IP, 3 - USB)
- `com_port`: номер COM-порта
- `com_baudrate`: скорость порта (115200 по умолчанию)
- `ip`: IP-адрес ККТ
- `ip_port`: порт ККТ

Значение **`type_connect[1]`** проверяется только если **`type_connect[0]`** не равен **`0`**, т.е. на случай если ФРа два и один из них (или оба) подключен НЕ по USB.
Ключ **`type_connect[1]`** может принимать только два значения:
1 - если второй ФР подключен по COM
2 - если второй ФР подключен по IP
(при любом другом значении ключа `type_connect[1]` или его отсутствии не происходит ничего.)
</details>

### service.json
<details>
<summary>Настройки службы</summary>

```json
{
    "service": {
        "updater_mode": 1,
        "updater_name": "updater.exe",
        "reboot_file": "reboot.bat",
        "log_level": "info",
        "log_days": 7
    },
    "validation_fn": {
        "enabled": true,
        "interval": 12,
        "trigger_days": 3,
        "target_time": "05:30",
        "delete_days": 21,
        "logs_mask_name": "AtolFiscalRegister",
        "logs_dir": "iiko",
        "serialNumber_key": "serialNumber=",
        "fnNumber_key": "fnNumber="
    },
    "notification": {
        "enabled": false,
        "authentication": {
            "encryption": false,
            "bot_token": "",
            "chat_id": ""
        },
        "max_attempts": 5,
        "delay": 10
    }
}
```

Параметры службы:
- `updater_mode`: выключение/включение отправки данных\автообновления (1 - вкл, 0 - выкл)
- `updater_name`: имя файла скрипта отправки данных (любой .exe или .bat файл)
- `reboot_file`: имя файла для перезагрузки
- `log_level`: уровень логирования
- `log_days`: срок хранения логов (дни)

Параметры проверки ФН:
- `enabled`: включение проверки ФН
- `interval`: интервал проверки (часы)
- `trigger_days`: дней до повторного сопоставления ФР к ФН по логам
- `target_time`: время перезагрузки если была обнаружена замена ФН
- `delete_days`: дней до удаления неактивного ФР
- `logs_mask_name`: маска имени лог-файла
- `logs_dir`: директория с логами (можно использовать абсолютный путь к любой папке с логами)
- `serialNumber_key`: ключ серийного номера ФР в логе
- `fnNumber_key`: ключ номера ФН в логе

Параметры уведомлений:
- `enabled`: включение уведомлений
- `encryption`: шифрование данных для подключения боту
- `bot_token`: токен Telegram бота
- `chat_id`: ID чата
- `max_attempts`: максимум попыток отправки
- `delay`: задержка между попытками
</details>

## updater
Подразумевается, что рядом с исполняемым файлом службы лежит папка **`updater`**, которая содержит приложение\скрипт для отправки данных и скачивания обновления.

Можно взять тут: https://github.com/symp1ex/ftp-updater

Но вообще это может быть любой скрипт, например в виде **`.bat-файла`**. Важно положить его в папку **`updater`** и прописать правильное имя файла в **`service.json`**

## Сборка
### 1. Необходимо сделать замену переменной **`current_path`** в файле **`about.py`**

```python
import os
import sys

version = "2.1.1.9"

'''
в зависимости от того, как запускается служба, нужно менять переменную current_path

#отладочный путь под .py-скрипт
current_path = os.path.dirname(os.path.abspath(__file__))

#путь под собранный .exe-файл
current_path = os.path.dirname(sys.executable)
'''

#отладочный путь под .py-скрипт
current_path = os.path.dirname(os.path.abspath(__file__))
```

Поменять на

```python
import os
import sys

version = "2.1.1.9"

#путь под собранный .exe-файл
current_path = os.path.dirname(sys.executable)
```

### 2. При сборке при помощи **`PyInstaller`**, необходимо явно указать некоторые импорты. Команда будет выглядеть так:
```bash
py -3.8 -m PyInstaller --hidden-import win32timezone --hidden-import win32serviceutil --hidden-import cryptography.fernet --hidden-import serial.tools.list_ports --hidden-import win32security --hidden-import win32ts --hidden-import win32service --hidden-import win32event --hidden-import servicemanager --hidden-import socket --hidden-import pywintypes --hidden-import win32api --onefile --noconsole --icon=favicon.ico getad-service.py
```
## Отправка уведомлений в Telegram

### Настройка со стороны Telegram
Нужно создать бота в Telegram и получить его токен. Создать группу, добавить бота в группу как админа и получить **`chat_id`** группы. Указать в **`service.json`** токен и **`chat_id`**

### Использование шифрования учётных данных для бота

Переменная **`key`** функции **`decrypt_data()`** в файле **`tg_notification.py`** сожержит ключ, которым шифруются учётные данные для получения доступа к тг-боту

<details>
<summary><b>tg_notification.py</b></summary>
  
```python
def decrypt_data(encrypted_data):
    try:
        key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM=' # ключ
        cipher = Fernet(key)
        decrypted_data = cipher.decrypt(encrypted_data).decode()
        return decrypted_data
    except Exception:
        logger.logger_service.error("Не удалось дешифровать данные для подключения к боту", exc_info=True)
```
</details>

В **`tools\crypto-key`** лежит скрипт, в который нужно вставить свои учётные данные и выполнить его. На выходе получите текстовый документ с зашифрованными данными, которые нужно будет вставить в конфиг

<details>
<summary><b>crypto-key.py</b></summary>
  
```python
# Пример использования:
key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='  # Ваш ключ
data_to_encrypt = "telegram_token_bot"
data_to_encrypt2 = "telegram_chat_id"
```
</details>

Там же лежит **`gen-key.py`**, запустив который, можно сгенерировать свой уникальный ключ.

