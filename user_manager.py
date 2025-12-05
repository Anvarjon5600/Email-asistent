import json
import os
import logging
from typing import Dict, Optional, Any
from cryptography.fernet import Fernet
import base64

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = data_file
        self.users = {}
        self._load_users()

        # Генерируем ключ шифрования
        key_file = "encryption.key"
        if os.path.exists(key_file):
            with open(key_file, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            with open(key_file, "wb") as f:
                f.write(self.key)

        self.cipher = Fernet(self.key)

    def _load_users(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            self.users = {}

    def _save_users(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")

    def _encrypt(self, data: str) -> str:
        encrypted = self.cipher.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    def _decrypt(self, encrypted_data: str) -> str:
        decoded = base64.b64decode(encrypted_data.encode())
        return self.cipher.decrypt(decoded).decode()

    def add_user(
        self,
        user_id: int,
        login: str,
        password: str,
        imap_server: str,
        imap_port: int = 993,
        smtp_server: Optional[str] = None,
        smtp_port: Optional[int] = None,
        webmail_url: Optional[str] = None,
    ) -> bool:
        try:
            # Дополнительная информация о провайдере
            provider_info = self._detect_provider_info(login, imap_server)

            self.users[str(user_id)] = {
                "login": login,
                "password": self._encrypt(password),
                "imap_server": imap_server,
                "imap_port": imap_port,
                "smtp_server": smtp_server or provider_info.get("smtp_server", ""),
                "smtp_port": smtp_port or provider_info.get("smtp_port", 587),
                "webmail_url": webmail_url or provider_info.get("webmail_url", ""),
                "provider": provider_info.get("name", "custom"),
                "provider_type": provider_info.get("type", "custom"),
                "created_at": (
                    os.path.getctime(self.data_file)
                    if os.path.exists(self.data_file)
                    else None
                ),
            }

            self._save_users()
            logger.info(f"Добавлен пользователь {user_id} с сервером {imap_server}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False

    def get_user_data(self, user_id: int) -> Optional[Dict]:
        user_data = self.users.get(str(user_id))
        if user_data:
            # Создаем копию с расшифрованным паролем
            decrypted_data = user_data.copy()
            try:
                decrypted_data["password"] = self._decrypt(user_data["password"])
            except:
                decrypted_data["password"] = ""
            return decrypted_data
        return None

    def delete_user(self, user_id: int) -> bool:
        if str(user_id) in self.users:
            del self.users[str(user_id)]
            self._save_users()
            return True
        return False

    def update_user_setting(self, user_id: int, key: str, value: Any) -> bool:
        if str(user_id) in self.users:
            self.users[str(user_id)][key] = value
            self._save_users()
            return True
        return False

    def _detect_provider_info(self, login: str, imap_server: str) -> Dict:
        """Определяет информацию о почтовом провайдере"""
        email_domain = login.split("@")[-1].lower() if "@" in login else ""

        # Список популярных провайдеров
        providers = {
            # Google/Gmail
            "gmail.com": {
                "name": "Gmail",
                "type": "gmail",
                "imap_server": "imap.gmail.com",
                "imap_port": 993,
                "smtp_server": "smtp.gmail.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.google.com",
            },
            # Яндекс
            "yandex.ru": {
                "name": "Яндекс.Почта",
                "type": "yandex",
                "imap_server": "imap.yandex.ru",
                "imap_port": 993,
                "smtp_server": "smtp.yandex.ru",
                "smtp_port": 587,
                "webmail_url": "https://mail.yandex.ru",
            },
            "yandex.com": {
                "name": "Yandex Mail",
                "type": "yandex",
                "imap_server": "imap.yandex.com",
                "imap_port": 993,
                "smtp_server": "smtp.yandex.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.yandex.com",
            },
            # Mail.ru
            "mail.ru": {
                "name": "Mail.ru",
                "type": "mailru",
                "imap_server": "imap.mail.ru",
                "imap_port": 993,
                "smtp_server": "smtp.mail.ru",
                "smtp_port": 465,
                "webmail_url": "https://e.mail.ru",
            },
            "bk.ru": {
                "name": "Mail.ru (bk)",
                "type": "mailru",
                "imap_server": "imap.mail.ru",
                "imap_port": 993,
                "smtp_server": "smtp.mail.ru",
                "smtp_port": 465,
                "webmail_url": "https://e.mail.ru",
            },
            "inbox.ru": {
                "name": "Mail.ru (inbox)",
                "type": "mailru",
                "imap_server": "imap.mail.ru",
                "imap_port": 993,
                "smtp_server": "smtp.mail.ru",
                "smtp_port": 465,
                "webmail_url": "https://e.mail.ru",
            },
            # Outlook/Hotmail
            "outlook.com": {
                "name": "Outlook",
                "type": "outlook",
                "imap_server": "outlook.office365.com",
                "imap_port": 993,
                "smtp_server": "smtp.office365.com",
                "smtp_port": 587,
                "webmail_url": "https://outlook.live.com",
            },
            "hotmail.com": {
                "name": "Outlook",
                "type": "outlook",
                "imap_server": "outlook.office365.com",
                "imap_port": 993,
                "smtp_server": "smtp.office365.com",
                "smtp_port": 587,
                "webmail_url": "https://outlook.live.com",
            },
            "live.com": {
                "name": "Outlook",
                "type": "outlook",
                "imap_server": "outlook.office365.com",
                "imap_port": 993,
                "smtp_server": "smtp.office365.com",
                "smtp_port": 587,
                "webmail_url": "https://outlook.live.com",
            },
            # Yahoo
            "yahoo.com": {
                "name": "Yahoo Mail",
                "type": "yahoo",
                "imap_server": "imap.mail.yahoo.com",
                "imap_port": 993,
                "smtp_server": "smtp.mail.yahoo.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.yahoo.com",
            },
            # iCloud
            "icloud.com": {
                "name": "iCloud Mail",
                "type": "icloud",
                "imap_server": "imap.mail.me.com",
                "imap_port": 993,
                "smtp_server": "smtp.mail.me.com",
                "smtp_port": 587,
                "webmail_url": "https://www.icloud.com/mail",
            },
            # ProtonMail
            "protonmail.com": {
                "name": "ProtonMail",
                "type": "protonmail",
                "imap_server": "imap.protonmail.com",
                "imap_port": 993,
                "smtp_server": "smtp.protonmail.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.protonmail.com",
            },
            "proton.me": {
                "name": "Proton Mail",
                "type": "protonmail",
                "imap_server": "imap.proton.me",
                "imap_port": 993,
                "smtp_server": "smtp.proton.me",
                "smtp_port": 587,
                "webmail_url": "https://mail.proton.me",
            },
            # Zoho
            "zoho.com": {
                "name": "Zoho Mail",
                "type": "zoho",
                "imap_server": "imap.zoho.com",
                "imap_port": 993,
                "smtp_server": "smtp.zoho.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.zoho.com",
            },
            # AOL
            "aol.com": {
                "name": "AOL Mail",
                "type": "aol",
                "imap_server": "imap.aol.com",
                "imap_port": 993,
                "smtp_server": "smtp.aol.com",
                "smtp_port": 587,
                "webmail_url": "https://mail.aol.com",
            },
        }

        # Пробуем найти точное совпадение
        if email_domain in providers:
            return providers[email_domain]

        # Проверяем частичные совпадения для поддоменов
        for domain, info in providers.items():
            if email_domain.endswith("." + domain):
                return info

        # Для кастомных серверов
        return {
            "name": "Custom Server",
            "type": "custom",
            "imap_server": imap_server,
            "imap_port": 993,
            "smtp_server": (
                f'smtp.{imap_server.replace("imap.", "")}'
                if imap_server.startswith("imap.")
                else f"smtp.{imap_server}"
            ),
            "smtp_port": 587,
            "webmail_url": (
                f'https://{imap_server.replace("imap.", "")}'
                if imap_server.startswith("imap.")
                else f"https://{imap_server}"
            ),
        }


user_manager = UserManager()
