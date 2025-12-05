import imaplib
import email
import re
from email.header import decode_header
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)


class EmailClient:
    def __init__(
        self, login: str, password: str, imap_server: str, imap_port: int = 993
    ):
        self.login = login
        self.password = password
        self.imap_server = imap_server
        self.imap_port = imap_port
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        try:
            self.connection = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.connection.login(self.login, self.password)
            logger.info(f"Успешное подключение к почте: {self.login}")
            return True
        except Exception as e:
            logger.error(f"Ошибка подключения к почте {self.login}: {e}")
            return False

    def disconnect(self):
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
            self.connection = None

    def get_unread_emails(self, limit: int = 10) -> List[Dict]:
        if not self.connection:
            if not self.connect():
                return []

        # Ensure static analyzers and runtime checks have a non-None connection
        if self.connection is None:
            return []

        try:
            self.connection.select("INBOX")
            status, messages = self.connection.search(None, "UNSEEN")
            if status != "OK":
                return []

            email_ids = messages[0].split()
            emails = []

            for email_id in email_ids[-limit:][::-1]:
                email_data = self._fetch_email(email_id)
                if email_data:
                    emails.append(email_data)

            return emails

        except Exception as e:
            logger.error(f"Ошибка получения писем: {e}")
            return []

    def _fetch_email(self, email_id: bytes) -> Optional[Dict]:
        if self.connection is None:
            logger.error(f"Нет подключения для получения письма {email_id}")
            return None

        try:
            conn = self.connection

            # Получаем UID письма
            uid = None
            try:
                # Получаем UID через отдельный запрос
                status_uid, uid_data = conn.fetch(email_id, "(UID)")
                if status_uid == "OK" and uid_data and uid_data[0]:
                    # Парсим ответ для получения UID
                    # Ответ может быть в формате: b'1 (UID 1001)' или [b'1 (UID 1001)']
                    uid_response = uid_data[0]
                    if isinstance(uid_response, bytes):
                        uid_response_str = uid_response.decode("utf-8", errors="ignore")
                        # Ищем UID в ответе с помощью регулярного выражения
                        uid_match = re.search(r"UID\s+(\d+)", uid_response_str)
                        if uid_match:
                            uid = int(uid_match.group(1))
            except Exception as uid_error:
                logger.warning(
                    f"Не удалось получить UID для письма {email_id}: {uid_error}"
                )
                uid = None

            # Получаем данные письма
            status, msg_data = conn.fetch(email_id, "(RFC822)")
            if status != "OK":
                return None

            # Ensure msg_data has the expected structure and extract bytes
            raw_msg = None
            if (
                isinstance(msg_data, list)
                and msg_data
                and isinstance(msg_data[0], tuple)
                and len(msg_data[0]) > 1
            ):
                raw_msg = msg_data[0][1]
            elif (
                isinstance(msg_data, tuple)
                and len(msg_data) > 1
                and isinstance(msg_data[1], bytes)
            ):
                raw_msg = msg_data[1]
            elif isinstance(msg_data, bytes):
                raw_msg = msg_data
            else:
                raw_msg = None

            if not isinstance(raw_msg, (bytes, bytearray)):
                return None

            msg = email.message_from_bytes(raw_msg)

            subject = self._decode_header(msg["Subject"])
            from_ = self._decode_header(msg["From"])
            date = msg["Date"]

            body = self._get_email_body(msg)

            # Получаем Message-ID если есть
            message_id = msg.get("Message-ID", "").strip("<>")

            return {
                "id": (
                    email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                ),
                "uid": uid,
                "message_id": message_id,
                "subject": subject,
                "from": from_,
                "date": date,
                "body": body[:1000],
                "preview": body[:200] + "..." if len(body) > 200 else body,
                "full_body": body,  # Добавляем полное тело письма
            }

        except Exception as e:
            logger.error(f"Ошибка обработки письма {email_id}: {e}")
            return None

    def _decode_header(self, header: Optional[str]) -> str:
        if not header:
            return ""

        try:
            decoded_parts = decode_header(header)
            decoded = []
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded.append(part.decode(encoding))
                    else:
                        decoded.append(part.decode("utf-8", errors="ignore"))
                else:
                    decoded.append(part)
            return " ".join(decoded)
        except:
            return str(header) if header else ""

    def _get_email_body(self, msg) -> str:
        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    if (
                        content_type == "text/plain"
                        and "attachment" not in content_disposition
                    ):
                        payload = part.get_payload(decode=True)
                        if payload:
                            return payload.decode("utf-8", errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    return payload.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Ошибка извлечения тела письма: {e}")

        return ""
