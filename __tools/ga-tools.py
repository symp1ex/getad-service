from cryptography.fernet import Fernet
import os
import sys
import json

log_file = os.path.join("output.txt")
sys.stdout = open(log_file, 'a')

def write_json_file(json_file, config):
    with open(json_file, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=4)

def read_config_file(json_file):
    with open(json_file, "r", encoding="utf-8") as file:
        config = json.load(file)
        return config


def encrypt_data(crypto_key_bytes, data):
    try:
        cipher = Fernet(crypto_key_bytes)
        encrypted_data = cipher.encrypt(data.encode())
    except Exception as e:
        print("Error:", e)
        encrypted_data = "None"
    return encrypted_data

def decrypt_data(crypto_key_bytes, encrypted_data):
    try:
        encrypted_bytes = encrypted_data.encode('utf-8')
        cipher = Fernet(crypto_key_bytes)
        decrypted_data = cipher.decrypt(encrypted_bytes).decode()
    except Exception as e:
        print("Error:", e)
        decrypted_data = "None"
    return decrypted_data

def main():
    json_file = "ga-tools.json"
    config = read_config_file(json_file)

    crypto_key = config.get("crypto_key")
    crypto_key_bytes = crypto_key.encode('utf-8')

    url = config.get("url")
    api_key = config.get("api_key")

    bot_token = config.get("bot_token")
    chat_id = config.get("chat_id")

    decrypt_data_1 = config.get("decrypt_data_1")
    decrypt_data_2 = config.get("decrypt_data_2")
    decrypt_data_3 = config.get("decrypt_data_3")
    decrypt_data_4 = config.get("decrypt_data_4")

    encrypted_data = encrypt_data(crypto_key_bytes, url)
    encrypted_data2 = encrypt_data(crypto_key_bytes, api_key)
    encrypted_data3 = encrypt_data(crypto_key_bytes, bot_token)
    encrypted_data4 = encrypt_data(crypto_key_bytes, chat_id)

    try: encrypted_data_decode = encrypted_data.decode('utf-8')
    except: encrypted_data_decode = "None"

    try: encrypted_data_decode2 = encrypted_data2.decode('utf-8')
    except: encrypted_data_decode2 = "None"

    try: encrypted_data_decode3 = encrypted_data3.decode('utf-8')
    except: encrypted_data_decode3 = "None"

    try: encrypted_data_decode4 = encrypted_data4.decode('utf-8')
    except: encrypted_data_decode4 = "None"


    print("url:", encrypted_data_decode)
    print()

    print("api_key:", encrypted_data_decode2)
    print()

    print("bot_token:", encrypted_data_decode3)
    print()

    print("chat_id:", encrypted_data_decode4)
    print()


    try: decrypted_data_1 = decrypt_data(crypto_key_bytes, decrypt_data_1)
    except: decrypted_data_1 = "None"
    try: decrypted_data_2 = decrypt_data(crypto_key_bytes, decrypt_data_2)
    except: decrypted_data_2 = "None"
    try: decrypted_data_3 = decrypt_data(crypto_key_bytes, decrypt_data_3)
    except: decrypted_data_3 = "None"
    try: decrypted_data_4 = decrypt_data(crypto_key_bytes, decrypt_data_4)
    except: decrypted_data_4 = "None"

    print("Расшифрованные данные:", decrypted_data_1)
    print("Расшифрованные данные 2:", decrypted_data_2)
    print("Расшифрованные данные 3:", decrypted_data_3)
    print("Расшифрованные данные 4:", decrypted_data_4)
    print(".")
    print(".")
    print(".")
    print(".")

if __name__ == "__main__":
    main()
