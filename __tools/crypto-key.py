from cryptography.fernet import Fernet
import os, sys

log_file = os.path.join("code.txt")
sys.stdout = open(log_file, 'a')

def encrypt_data(key, data):
    cipher = Fernet(key)
    encrypted_data = cipher.encrypt(data.encode())
    return encrypted_data

def decrypt_data(key, encrypted_data):
    cipher = Fernet(key)
    decrypted_data = cipher.decrypt(encrypted_data).decode()
    return decrypted_data

# Пример использования:
key = b't_qxC_HN04Tiy1ish2P27ROYSJt_m7_FE2JT6gYngOM='  # Ваш ключ

data_to_encrypt = "telegram_token_bot"
data_to_encrypt2 = "telegram_chat_id"
data_to_encrypt3 = "url"
data_to_encrypt4 = "api_key"

encrypted_data = encrypt_data(key, data_to_encrypt)
print("Зашифрованные данные:", encrypted_data)

encrypted_data2 = encrypt_data(key, data_to_encrypt2)
print("Зашифрованные данные 2:", encrypted_data2)

encrypted_data3 = encrypt_data(key, data_to_encrypt3)
print("Зашифрованные данные 3:", encrypted_data3)

encrypted_data4 = encrypt_data(key, data_to_encrypt4)
print("Зашифрованные данные 4:", encrypted_data4)
print()

decrypted_data = decrypt_data(key, encrypted_data)
print("Расшифрованные данные:", decrypted_data)

decrypted_data2 = decrypt_data(key, encrypted_data2)
print("Расшифрованные данные2:", decrypted_data2)

decrypted_data3 = decrypt_data(key, encrypted_data3)
print("Расшифрованные данные3:", decrypted_data3)

decrypted_data4 = decrypt_data(key, encrypted_data4)
print("Расшифрованные данные4:", decrypted_data4)
print()
print()
print()


# если вдруг нужно расшифровать что-то другое этим же ключом =)
data_to_encrypt5 = ""
decrypted_data5 = decrypt_data(key, data_to_encrypt3)

print("Расшифрованные данные 5:", decrypted_data3)
