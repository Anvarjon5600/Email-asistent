import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Telegram Bot Token
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

    # Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # iRedMail сервер
    IMAP_SERVER = os.getenv("IMAP_SERVER", "email.hyperthink.uz")
    IMAP_PORT = int(os.getenv("IMAP_PORT", 993))

    # Настройки веб-интерфейса для кнопки "Подробнее"
    # Для Roundcube: https://mail.example.com/?_task=mail&_action=show&_uid={uid}&_mbox=INBOX
    # Для iRedMail: https://mail.example.com/mail/?_task=mail&_action=show&_uid={uid}&_mbox=INBOX
    # Или просто базовый URL: https://mail.example.com
    WEBMAIL_BASE_URL = os.getenv("WEBMAIL_BASE_URL", "")

    # Шаблон URL для прямого открытия письма (если поддерживается)
    # Используйте {uid} для UID письма
    WEBMAIL_MESSAGE_URL = os.getenv("WEBMAIL_MESSAGE_URL", "")

    # Определяем тип веб-интерфейса (roundcube, squirrelmail, iredmail и т.д.)
    WEBMAIL_TYPE = os.getenv("WEBMAIL_TYPE", "generic").lower()

    # Интервал проверки почты (в секундах)
    CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))

    # Мастер-ключ для шифрования
    MASTER_KEY = os.getenv("MASTER_KEY", "")
