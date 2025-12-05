import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import re

logger = logging.getLogger(__name__)


class EventManager:
    def __init__(self, data_file: str = "events.json"):
        self.data_file = data_file
        self.events: Dict[int, List[Dict]] = {}
        self.load_events()

    def load_events(self):
        """Загружает события из файла"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Конвертируем ключи в int
                    self.events = {}
                    for key, value in data.items():
                        try:
                            self.events[int(key)] = value
                        except ValueError:
                            continue
                logger.info(
                    f"Загружено {sum(len(events) for events in self.events.values())} событий"
                )
            else:
                self.events = {}
        except Exception as e:
            logger.error(f"Ошибка загрузки событий: {e}")
            self.events = {}

    def save_events(self):
        """Сохраняет события в файл"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.events, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения событий: {e}")

    def extract_dates_from_text(self, text: str) -> List[str]:
        """Извлекает даты из текста используя различные форматы"""
        dates = []

        # Паттерны для поиска дат
        patterns = [
            r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b",  # DD.MM.YYYY
            r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",  # DD/MM/YYYY
            r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b",  # YYYY-MM-DD
            r"\b(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})\b",  # 1 января 2024
            r"\b(\d{1,2})\s+(янв|фев|мар|апр|май|июн|июл|авг|сен|окт|ноя|дек)[\.]?\s+(\d{4})\b",  # 1 янв 2024
            r"\b(\d{1,2})[\./](\d{1,2})[\./](\d{2,4})\b",  # DD.MM.YY или DD/MM/YY
        ]

        month_names = {
            "января": 1,
            "февраля": 2,
            "марта": 3,
            "апреля": 4,
            "мая": 5,
            "июня": 6,
            "июля": 7,
            "августа": 8,
            "сентября": 9,
            "октября": 10,
            "ноября": 11,
            "декабря": 12,
            "янв": 1,
            "фев": 2,
            "мар": 3,
            "апр": 4,
            "май": 5,
            "июн": 6,
            "июл": 7,
            "авг": 8,
            "сен": 9,
            "окт": 10,
            "ноя": 11,
            "дек": 12,
        }

        for pattern in patterns:
            matches = re.finditer(pattern, text.lower())
            for match in matches:
                try:
                    groups = match.groups()
                    if len(groups) == 3:
                        if groups[1] in month_names:
                            # Формат с названием месяца
                            day = int(groups[0])
                            month = month_names[groups[1]]
                            year = int(groups[2])
                        else:
                            # Числовой формат
                            if (
                                pattern == r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"
                            ):  # YYYY-MM-DD
                                year, month, day = (
                                    int(groups[0]),
                                    int(groups[1]),
                                    int(groups[2]),
                                )
                            else:
                                day, month, year = (
                                    int(groups[0]),
                                    int(groups[1]),
                                    int(groups[2]),
                                )

                                # Коррекция года для двухзначного формата
                                if year < 100:
                                    year = 2000 + year if year < 50 else 1900 + year

                        try:
                            date_obj = datetime(year, month, day)
                            date_str = date_obj.strftime("%Y-%m-%d")
                            if date_str not in dates:
                                dates.append(date_str)
                        except ValueError:
                            continue
                except (ValueError, IndexError) as e:
                    logger.debug(f"Ошибка парсинга даты: {e}")
                    continue

        return dates

    def add_event_from_email(
        self, user_id: int, email_subject: str, email_body: str
    ) -> List[Dict]:
        """Добавляет события из email"""
        dates = self.extract_dates_from_text(email_subject + " " + email_body)
        events_added = []

        for date in dates:
            # Создаем уникальный ID для события
            import hashlib

            unique_id = hashlib.md5(
                f"{user_id}_{email_subject}_{date}".encode()
            ).hexdigest()[:10]

            event = {
                "id": unique_id,
                "title": email_subject[:100],  # Обрезаем длинные темы
                "date": date,
                "original_date": date,
                "created_at": datetime.now().isoformat(),
                "reminder_sent": False,
                "email_preview": email_body[:200],  # Сохраняем превью письма
            }

            # Инициализируем список событий для пользователя если нужно
            if user_id not in self.events:
                self.events[user_id] = []

            # Проверяем, нет ли уже такого события
            existing_ids = [e["id"] for e in self.events[user_id]]
            if event["id"] not in existing_ids:
                self.events[user_id].append(event)
                events_added.append(event)

        if events_added:
            self.save_events()
            logger.info(
                f"Добавлено {len(events_added)} событий для пользователя {user_id}"
            )

        return events_added

    def get_upcoming_events(self, user_id: int, days: int = 7) -> List[Dict]:
        """Получает предстоящие события пользователя"""
        if user_id not in self.events:
            return []

        today = datetime.now().date()
        future_date = today + timedelta(days=days)

        upcoming = []
        for event in self.events[user_id]:
            try:
                event_date_str = event.get("date", event.get("original_date", ""))
                if not event_date_str:
                    continue

                # Пробуем разные форматы дат
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
                    try:
                        event_date = datetime.strptime(event_date_str, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    continue

                if today <= event_date <= future_date:
                    # Добавляем информацию о днях до события
                    days_left = (event_date - today).days
                    event_with_days = event.copy()
                    event_with_days["days_left"] = days_left
                    upcoming.append(event_with_days)
            except Exception as e:
                logger.debug(f"Ошибка обработки даты события: {e}")
                continue

        # Сортируем по дате (ближайшие первыми)
        upcoming.sort(key=lambda x: x.get("date", ""))
        return upcoming

    def get_events_for_reminder(self) -> List[tuple]:
        """Получает события для отправки напоминаний"""
        reminders = []
        today = datetime.now().date()

        for user_id, user_events in self.events.items():
            for event in user_events:
                if event.get("reminder_sent"):
                    continue

                try:
                    event_date_str = event.get("date", event.get("original_date", ""))
                    if not event_date_str:
                        continue

                    # Пробуем разные форматы дат
                    event_date = None
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                        try:
                            event_date = datetime.strptime(event_date_str, fmt).date()
                            break
                        except ValueError:
                            continue

                    if not event_date:
                        continue

                    days_until = (event_date - today).days

                    # Отправляем напоминания за 1, 3, 7 дней до события
                    if days_until in [1, 3, 7] and days_until >= 0:
                        reminders.append((user_id, event, days_until))
                except Exception as e:
                    logger.debug(f"Ошибка проверки напоминания: {e}")
                    continue

        return reminders

    def mark_reminder_sent(self, user_id: int, event_id: str):
        """Отмечает, что напоминание отправлено"""
        if user_id in self.events:
            for event in self.events[user_id]:
                if event["id"] == event_id:
                    event["reminder_sent"] = True
                    logger.info(f"Напоминание отправлено для события {event_id}")
                    break
            self.save_events()

    def delete_event(self, user_id: int, event_id: str) -> bool:
        """Удаляет событие"""
        if user_id in self.events:
            initial_count = len(self.events[user_id])
            self.events[user_id] = [
                e for e in self.events[user_id] if e["id"] != event_id
            ]
            if len(self.events[user_id]) != initial_count:
                self.save_events()
                return True
        return False

    def get_user_events(self, user_id: int) -> List[Dict]:
        """Получает все события пользователя"""
        return self.events.get(user_id, [])

    def clear_old_events(self, days: int = 30):
        """Удаляет старые события (более days дней назад)"""
        cutoff_date = datetime.now().date() - timedelta(days=days)
        removed_count = 0

        for user_id, user_events in list(self.events.items()):
            new_events = []
            for event in user_events:
                try:
                    event_date_str = event.get("date", event.get("original_date", ""))
                    if not event_date_str:
                        new_events.append(event)
                        continue

                    event_date = None
                    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                        try:
                            event_date = datetime.strptime(event_date_str, fmt).date()
                            break
                        except ValueError:
                            continue

                    if event_date and event_date >= cutoff_date:
                        new_events.append(event)
                    else:
                        removed_count += 1
                except:
                    new_events.append(event)

            if new_events:
                self.events[user_id] = new_events
            else:
                del self.events[user_id]

        if removed_count > 0:
            self.save_events()
            logger.info(f"Удалено {removed_count} старых событий")


# Глобальный экземпляр менеджера событий
event_manager = EventManager()

# Фоновая очистка старых событий при импорте
event_manager.clear_old_events(30)
