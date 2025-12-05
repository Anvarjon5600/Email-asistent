import json
import os
import logging
from typing import Dict, Optional
from security import password_manager

logger = logging.getLogger(__name__)


class UserManager:
    def __init__(self, data_file: str = "users_data.json"):
        self.data_file = data_file
        self.users: Dict[int, dict] = {}
        self.load_users()

    def load_users(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.users = {int(k): v for k, v in data.items()}
                logger.info(f"Загружено {len(self.users)} пользователей")
            else:
                self.users = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {e}")
            self.users = {}

    def save_users(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения данных: {e}")

    def add_user(self, user_id: int, login: str, password: str) -> bool:
        try:
            encrypted_password = password_manager.encrypt_password(password)

            self.users[user_id] = {
                "login": login,
                "password_encrypted": encrypted_password,
                "active": True,
            }

            self.save_users()
            logger.info(f"Добавлены данные для пользователя {user_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка добавления пользователя: {e}")
            return False

    def get_user_data(self, user_id: int) -> Optional[dict]:
        try:
            if user_id not in self.users:
                return None

            user_data = self.users[user_id].copy()
            encrypted_password = user_data.pop("password_encrypted")
            user_data["password"] = password_manager.decrypt_password(
                encrypted_password
            )

            return user_data
        except Exception as e:
            logger.error(f"Ошибка получения данных пользователя {user_id}: {e}")
            return None

    def delete_user(self, user_id: int) -> bool:
        try:
            if user_id in self.users:
                del self.users[user_id]
                self.save_users()
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка удаления пользователя: {e}")
            return False


user_manager = UserManager()
