import os
import base64
import logging
from cryptography.fernet import Fernet
from config import Config

logger = logging.getLogger(__name__)


class PasswordManager:
    def __init__(self):
        self.master_key = self._get_or_create_master_key()
        self.fernet = Fernet(self.master_key)

    def _get_or_create_master_key(self) -> bytes:
        master_key_env = Config.MASTER_KEY

        if master_key_env:
            return base64.urlsafe_b64decode(master_key_env)
        else:
            new_master_key = Fernet.generate_key()
            logger.warning(
                "⚠️  MASTER_KEY не найден в .env! Сгенерирован новый ключ.\n"
                f"Добавьте в ваш .env файл:\nMASTER_KEY={base64.urlsafe_b64encode(new_master_key).decode()}\n"
                "⚠️  СОХРАНИТЕ ЭТОТ КЛЮЧ БЕЗОПАСНО!"
            )
            return new_master_key

    def encrypt_password(self, password: str) -> str:
        encrypted = self.fernet.encrypt(password.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt_password(self, encrypted_password: str) -> str:
        try:
            encrypted = base64.urlsafe_b64decode(encrypted_password.encode())
            decrypted = self.fernet.decrypt(encrypted)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Ошибка дешифровки пароля: {e}")
            raise ValueError("Не удалось расшифровать пароль")


password_manager = PasswordManager()
