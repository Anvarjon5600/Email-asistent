import imaplib
import email
import io
import os
import tempfile
from email.header import decode_header
from typing import List, Optional, Dict, Tuple
import logging

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

            status, msg_data = conn.fetch(email_id, "(RFC822)")
            if status != "OK":
                return None

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
            to = self._decode_header(msg.get("To", ""))
            cc = self._decode_header(msg.get("Cc", ""))

            # Получаем тело письма и вложения
            body, attachments = self._get_email_body_and_attachments(msg)

            return {
                "id": (
                    email_id.decode() if isinstance(email_id, bytes) else str(email_id)
                ),
                "subject": subject,
                "from": from_,
                "to": to,
                "cc": cc,
                "date": date,
                "body": body[:1000],
                "preview": body[:200] + "..." if len(body) > 200 else body,
                "full_body": body,
                "attachments": attachments,
                "has_attachments": len(attachments) > 0,
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

    def _get_email_body_and_attachments(self, msg) -> Tuple[str, List[Dict]]:
        """Извлекает тело письма и вложения"""
        body = ""
        attachments = []

        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))

                    # Пропускаем multipart контейнеры
                    if content_type.startswith("multipart/"):
                        continue

                    # Проверяем вложение
                    if (
                        "attachment" in content_disposition
                        or "filename" in content_disposition
                    ):
                        attachment = self._extract_attachment(part)
                        if attachment:
                            attachments.append(attachment)
                        continue

                    # Текстовое тело письма
                    if content_type == "text/plain" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="ignore")

                    # HTML тело (используем если текстового нет)
                    elif content_type == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            # Простая очистка HTML для текста
                            html_content = payload.decode("utf-8", errors="ignore")
                            body = self._html_to_text(html_content)
            else:
                # Простое письмо без вложений
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="ignore")

        except Exception as e:
            logger.error(f"Ошибка извлечения тела и вложений: {e}")

        return body, attachments

    def _extract_attachment(self, part) -> Optional[Dict]:
        """Извлекает информацию о вложении"""
        try:
            filename = part.get_filename()
            if filename:
                # Декодируем имя файла
                filename = self._decode_header(filename)

                # Получаем данные файла
                file_data = part.get_payload(decode=True)
                if not file_data:
                    return None

                # Определяем тип файла
                content_type = part.get_content_type()
                file_size = len(file_data)

                # Сохраняем во временный файл
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f"_{filename}"
                ) as tmp_file:
                    tmp_file.write(file_data)
                    temp_path = tmp_file.name

                return {
                    "filename": filename,
                    "content_type": content_type,
                    "size": file_size,
                    "temp_path": temp_path,
                    "data": (
                        file_data if file_size < 1024 * 1024 else None
                    ),  # Кэшируем только маленькие файлы
                }
        except Exception as e:
            logger.error(f"Ошибка извлечения вложения: {e}")

        return None

    def _html_to_text(self, html: str) -> str:
        """Простая конвертация HTML в текст"""
        try:
            import re

            # Удаляем теги
            text = re.sub(r"<[^>]+>", " ", html)
            # Заменяем HTML entities
            text = (
                text.replace("&nbsp;", " ")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
            )
            # Удаляем лишние пробелы
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except:
            return html
