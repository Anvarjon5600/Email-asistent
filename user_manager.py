import json
import os
import logging
from typing import Dict, Optional, Any
from datetime import datetime
from security import password_manager

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = data_file
        self.users = {}
        self._load_users()

    def _load_users(self):
        """Загружает данные пользователей из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
                logger.info(f"Загружено {len(self.users)} пользователей")
            else:
                self.users = {}
                logger.info("Файл пользователей не найден, создан новый")
        except Exception as e:
            logger.error(f"Ошибка загрузки пользователей: {e}")
            self.users = {}

    def _save_users(self):
        """Сохраняет данные пользователей в файл"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
            logger.debug("Данные пользователей сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения пользователей: {e}")

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
        """Добавляет или обновляет пользователя"""
        try:
            # Определяем информацию о провайдере
            provider_info = self._detect_provider_info(login, imap_server)

            # Шифруем пароль
            encrypted_password = password_manager.encrypt_password(password)

            self.users[str(user_id)] = {
                "login": login,
                "password": encrypted_password,
                "imap_server": imap_server,
                "imap_port": imap_port,
                "smtp_server": smtp_server or provider_info.get("smtp_server", ""),
                "smtp_port": smtp_port or provider_info.get("smtp_port", 587),
                "webmail_url": webmail_url or provider_info.get("webmail_url", ""),
                "provider": provider_info.get("name", "Custom Server"),
                "provider_type": provider_info.get("type", "custom"),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            }

            self._save_users()
            logger.info(f"Пользователь {user_id} ({login}) успешно добавлен/обновлен")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя {user_id}: {e}")
            return False

    def get_user_data(self, user_id: int) -> Optional[Dict]:
        """Получает данные пользователя с расшифрованным паролем"""
        user_data = self.users.get(str(user_id))
        if user_data:
            try:
                # Создаем копию данных
                decrypted_data = user_data.copy()

                # Расшифровываем пароль
                decrypted_data["password"] = password_manager.decrypt_password(
                    user_data["password"]
                )
                return decrypted_data
            except Exception as e:
                logger.error(f"Ошибка расшифровки данных пользователя {user_id}: {e}")
                return None
        return None

    def delete_user(self, user_id: int) -> bool:
        """Удаляет пользователя"""
        if str(user_id) in self.users:
            login = self.users[str(user_id)].get("login", "unknown")
            del self.users[str(user_id)]
            self._save_users()
            logger.info(f"Пользователь {user_id} ({login}) удален")
            return True
        logger.warning(f"Попытка удалить несуществующего пользователя {user_id}")
        return False

    def update_user_setting(self, user_id: int, key: str, value: Any) -> bool:
        """Обновляет конкретную настройку пользователя"""
        if str(user_id) in self.users:
            self.users[str(user_id)][key] = value
            self.users[str(user_id)]["updated_at"] = datetime.now().isoformat()
            self._save_users()
            logger.info(f"Настройка '{key}' обновлена для пользователя {user_id}")
            return True
        return False

    def user_exists(self, user_id: int) -> bool:
        """Проверяет существование пользователя"""
        return str(user_id) in self.users

    def get_all_users(self) -> Dict:
        """Возвращает всех пользователей (без расшифровки паролей)"""
        return self.users.copy()

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
            "webmail_url": "",
        }


# Глобальный экземпляр менеджера пользователей
user_manager = UserManager()
