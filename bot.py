import logging
import html
import os
from datetime import datetime
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
from config import Config
from user_manager import user_manager
from email_client import EmailClient
from gemini_client import gemini_client
from event_manager import event_manager

LOGIN, PASSWORD, IMAP_SERVER, IMAP_PORT, CONFIRMATION = range(5)
CHANGE_INTERVAL, TOGGLE_NOTIFICATIONS = range(5, 7)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
LOGIN, PASSWORD, IMAP_SERVER, IMAP_PORT, CONFIRMATION = range(5)


class EmailBot:
    def __init__(self):
        self.application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        self.setup_handlers()
        self.setup_jobs()
        self.email_providers = self._init_email_providers()

    def _init_email_providers(self):
        """Инициализация списка почтовых провайдеров"""
        return {
            "gmail.com": {
                "name": "Gmail",
                "webmail_url": "https://mail.google.com",
            },
            "yandex.ru": {
                "name": "Яндекс.Почта",
                "webmail_url": "https://mail.yandex.ru",
            },
            "yandex.com": {
                "name": "Yandex Mail",
                "webmail_url": "https://mail.yandex.com",
            },
            "mail.ru": {
                "name": "Mail.ru",
                "webmail_url": "https://e.mail.ru",
            },
            "bk.ru": {
                "name": "Mail.ru (bk)",
                "webmail_url": "https://e.mail.ru",
            },
            "inbox.ru": {
                "name": "Mail.ru (inbox)",
                "webmail_url": "https://e.mail.ru",
            },
            "outlook.com": {
                "name": "Outlook",
                "webmail_url": "https://outlook.live.com",
            },
            "hotmail.com": {
                "name": "Outlook",
                "webmail_url": "https://outlook.live.com",
            },
            "live.com": {
                "name": "Outlook",
                "webmail_url": "https://outlook.live.com",
            },
            "yahoo.com": {
                "name": "Yahoo Mail",
                "webmail_url": "https://mail.yahoo.com",
            },
            "icloud.com": {
                "name": "iCloud Mail",
                "webmail_url": "https://www.icloud.com/mail",
            },
        }

    # ===================== МЕНЮ И КНОПКИ =====================

    def get_main_menu(self, user_id: int):
        """Возвращает главное меню в зависимости от статуса пользователя"""
        user_data = user_manager.get_user_data(user_id)

        if not user_data:
            # Пользователь не зарегистрирован
            return ReplyKeyboardMarkup(
                [["📝 Начать настройку"], ["ℹ️ О боте", "🆘 Помощь"]],
                resize_keyboard=True,
                one_time_keyboard=False,
            )
        else:
            # Пользователь зарегистрирован
            return ReplyKeyboardMarkup(
                [
                    ["📧 Проверить почту", "🔄 Автопроверка"],
                    ["📅 Мои события", "⚙️ Настройки"],
                    ["📊 Статистика", "🆘 Помощь"],
                ],
                resize_keyboard=True,
                one_time_keyboard=False,
            )

    def get_settings_menu(self):
        """Меню настроек"""
        return ReplyKeyboardMarkup(
            [
                ["✏️ Изменить данные", "⏰ Интервал проверки"],
                ["🔔 Напоминания", "🔐 Безопасность"],
                ["⬅️ Назад в меню"],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    def get_autocheck_menu(self):
        """Меню автопроверки"""
        return ReplyKeyboardMarkup(
            [
                ["✅ Включить автопроверку", "❌ Выключить автопроверку"],
                ["⬅️ Назад"],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    def get_confirmation_menu(self):
        """Меню подтверждения"""
        return ReplyKeyboardMarkup(
            [["✅ Да, сохранить", "🔄 Ввести заново"], ["❌ Отмена"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    def get_interval_menu(self):
        """Меню выбора интервала проверки"""
        return ReplyKeyboardMarkup(
            [
                ["⏱️ 10 секунд", "⏱️ 30 секунд"],
                ["⏱️ 1 минута", "⏱️ 5 минут"],
                ["⏱️ 10 минут", "⏱️ 30 минут"],
                ["⬅️ Назад в настройки"],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    async def change_check_interval(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Меню изменения интервала автопроверки"""
        user_id = update.message.from_user.id
        user_data = user_manager.get_user_data(user_id)
        if not user_data:
            await update.message.reply_text(
                "❌ Сначала настройте бота через /start",
                reply_markup=self.get_main_menu(user_id),
            )
            return ConversationHandler.END

        current_interval = user_data.get("check_interval", 10)

        await update.message.reply_text(
            f"⏰ <b>Интервал автопроверки почты</b>\n\n"
            f"Текущий интервал: <b>{current_interval} секунд</b>\n\n"
            f"Выберите новый интервал:",
            parse_mode="HTML",
            reply_markup=self.get_interval_menu(),
        )
        return CHANGE_INTERVAL

    async def handle_interval_change(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает изменение интервала"""
        user_id = update.message.from_user.id
        text = update.message.text
        if text == "⬅️ Назад в настройки":
            await update.message.reply_text(
                "⚙️ Настройки:", reply_markup=self.get_settings_menu()
            )
            return ConversationHandler.END
        # Парсим выбранный интервал
        interval_map = {
            "⏱️ 10 секунд": 10,
            "⏱️ 30 секунд": 30,
            "⏱️ 1 минута": 60,
            "⏱️ 5 минут": 300,
            "⏱️ 10 минут": 600,
            "⏱️ 30 минут": 1800,
        }

        if text in interval_map:
            new_interval = interval_map[text]

            # Сохраняем в базе пользователя
            user_manager.update_user_setting(user_id, "check_interval", new_interval)
            await update.message.reply_text(
                f"✅ <b>Интервал автопроверки изменен!</b>\n\n"
                f"Новый интервал: <b>{new_interval} секунд</b>\n\n"
                f"⚠️ <i>Примечание: изменения применятся при следующей проверке</i>",
                parse_mode="HTML",
                reply_markup=self.get_main_menu(user_id),
            )
        else:
            await update.message.reply_text(
                "❌ Неверный выбор. Попробуйте снова:",
                reply_markup=self.get_interval_menu(),
            )
            return CHANGE_INTERVAL

        return ConversationHandler.END

    async def toggle_notifications(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Переключает настройки уведомлений"""
        user_id = update.message.from_user.id
        user_data = user_manager.get_user_data(user_id)
        if not user_data:
            await update.message.reply_text(
                "❌ Сначала настройте бота через /start",
                reply_markup=self.get_main_menu(user_id),
            )
            return

        notifications_enabled = user_data.get("notifications_enabled", True)
        reminder_days = user_data.get("reminder_days", [7, 3, 1])

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if notifications_enabled else '❌'} Уведомления о письмах",
                    callback_data="toggle_email_notifications",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 7 in reminder_days else '❌'} За 7 дней",
                    callback_data="toggle_reminder_7",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 3 in reminder_days else '❌'} За 3 дня",
                    callback_data="toggle_reminder_3",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 1 in reminder_days else '❌'} За 1 день",
                    callback_data="toggle_reminder_1",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 0 in reminder_days else '❌'} В день события",
                    callback_data="toggle_reminder_0",
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")],
        ]

        await update.message.reply_text(
            "🔔 <b>Настройки уведомлений</b>\n\n"
            "Выберите, какие уведомления вы хотите получать:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def handle_notification_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает нажатия на кнопки уведомлений"""
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_data = user_manager.get_user_data(user_id)

        if not user_data:
            await query.edit_message_text("❌ Ошибка: данные пользователя не найдены")
            return

        data = query.data

        if data == "toggle_email_notifications":
            current = user_data.get("notifications_enabled", True)
            user_manager.update_user_setting(user_id, "notifications_enabled", not current)
            status = "включены" if not current else "выключены"
            await query.answer(f"✅ Уведомления о письмах {status}")

        elif data.startswith("toggle_reminder_"):
            day = int(data.split("_")[-1])
            reminder_days = user_data.get("reminder_days", [7, 3, 1])

            if day in reminder_days:
                reminder_days.remove(day)
                status = "выключено"
            else:
                reminder_days.append(day)
                reminder_days.sort(reverse=True)
                status = "включено"

            user_manager.update_user_setting(user_id, "reminder_days", reminder_days)

            day_text = {0: "В день события", 1: "За 1 день", 3: "За 3 дня", 7: "За 7 дней"}
            await query.answer(f"✅ Напоминание '{day_text.get(day, str(day))}' {status}")

        elif data == "back_to_settings":
            await query.edit_message_text("⚙️ Настройки:", reply_markup=None)
            await query.message.reply_text(
                "Выберите раздел:", reply_markup=self.get_settings_menu()
            )
            return

        # Обновляем клавиатуру
        user_data = user_manager.get_user_data(user_id)
        notifications_enabled = user_data.get("notifications_enabled", True)
        reminder_days = user_data.get("reminder_days", [7, 3, 1])

        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if notifications_enabled else '❌'} Уведомления о письмах",
                    callback_data="toggle_email_notifications",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 7 in reminder_days else '❌'} За 7 дней",
                    callback_data="toggle_reminder_7",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 3 in reminder_days else '❌'} За 3 дня",
                    callback_data="toggle_reminder_3",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 1 in reminder_days else '❌'} За 1 день",
                    callback_data="toggle_reminder_1",
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if 0 in reminder_days else '❌'} В день события",
                    callback_data="toggle_reminder_0",
                )
            ],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_settings")],
        ]

        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== РЕГИСТРАЦИЯ ====================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает диалог с пользователя"""
        user = update.message.from_user
        user_id = user.id
        
        # ВАЖНО: Очищаем контекст при новом старте
        context.user_data.clear()
        context.user_data["user_id"] = user_id

        existing_data = user_manager.get_user_data(user_id)

        if existing_data:
            # Пользователь уже зарегистрирован - предлагаем варианты
            keyboard = ReplyKeyboardMarkup(
                [
                    ["✅ Продолжить с текущими данными"],
                    ["🔄 Перенастроить заново"],
                    ["❌ Отмена"],
                ],
                resize_keyboard=True,
                one_time_keyboard=True,
            )
            
            await update.message.reply_text(
                f"👋 С возвращением, {user.first_name}!\n\n"
                f"✅ У вас уже настроен почтовый ящик:\n"
                f"📧 <b>Email:</b> {existing_data['login']}\n"
                f"🌐 <b>Сервер:</b> {existing_data['imap_server']}:{existing_data['imap_port']}\n\n"
                f"Что вы хотите сделать?",
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            context.user_data["awaiting_start_choice"] = True
            return LOGIN  # Возвращаем LOGIN чтобы обработать выбор
        else:
            # Новый пользователь - начинаем регистрацию
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n\n"
                "🤖 Я - умный почтовый ассистент!\n\n"
                "📧 <b>Что я умею:</b>\n"
                "• Проверять вашу почту\n"
                "• Анализировать письма с помощью AI\n"
                "• Отправлять уведомления\n\n"
                "📝 <b>Для начала введите ваш email:</b>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            return LOGIN

    async def get_login(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает логин"""
        user_id = context.user_data.get("user_id")
        
        # Проверяем, ждем ли мы выбор от уже зарегистрированного пользователя
        if context.user_data.get("awaiting_start_choice"):
            choice = update.message.text
            
            if choice == "✅ Продолжить с текущими данными":
                # Возвращаемся в главное меню
                del context.user_data["awaiting_start_choice"]
                await update.message.reply_text(
                    "✅ Отлично! Продолжаем работу.",
                    reply_markup=self.get_main_menu(user_id),
                )
                return ConversationHandler.END
            
            elif choice == "🔄 Перенастроить заново":
                # Удаляем старые данные
                user_manager.delete_user(user_id)
                
                # Удаляем события пользователя
                if user_id in event_manager.events:
                    del event_manager.events[user_id]
                    event_manager.save_events()
                
                # Очищаем флаг и начинаем заново
                del context.user_data["awaiting_start_choice"]
                
                await update.message.reply_text(
                    "🔄 <b>Начинаем настройку заново</b>\n\n"
                    "Старые данные удалены.\n\n"
                    "📝 Введите ваш email:",
                    parse_mode="HTML",
                    reply_markup=ReplyKeyboardRemove(),
                )
                return LOGIN
            
            elif choice == "❌ Отмена":
                del context.user_data["awaiting_start_choice"]
                await update.message.reply_text(
                    "Отменено.", reply_markup=self.get_main_menu(user_id)
                )
                return ConversationHandler.END
            
            else:
                # Неверный выбор - показываем меню снова
                keyboard = ReplyKeyboardMarkup(
                    [
                        ["✅ Продолжить с текущими данными"],
                        ["🔄 Перенастроить заново"],
                        ["❌ Отмена"],
                    ],
                    resize_keyboard=True,
                    one_time_keyboard=True,
                )
                await update.message.reply_text(
                    "❓ Пожалуйста, выберите один из вариантов:",
                    reply_markup=keyboard,
                )
                return LOGIN
        
        # Обычная обработка ввода email
        login = update.message.text.strip()

        if "@" not in login:
            await update.message.reply_text(
                "❌ Это не похоже на email. Введите корректный email:"
            )
            return LOGIN

        context.user_data["login"] = login

        domain = login.split("@")[1].lower()
        popular_servers = self._get_popular_servers_for_domain(domain)

        message = f"✅ Логин <b>{login}</b> сохранен.\n\n"

        if popular_servers:
            message += f"📡 <b>Рекомендуемые настройки:</b>\n"
            for server in popular_servers:
                message += f"• {server['name']}: {server['imap_server']}:{server['imap_port']}\n"
            message += "\n"

        message += "🌐 <b>Введите IMAP сервер вашей почты:</b>\n"
        message += "Пример: imap.gmail.com, imap.yandex.ru"

        await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return IMAP_SERVER

    def _get_popular_servers_for_domain(self, domain: str):
        """Возвращает популярные серверы для домена"""
        servers = []

        if "gmail.com" in domain or "google.com" in domain:
            servers.append(
                {"name": "Gmail", "imap_server": "imap.gmail.com", "imap_port": 993}
            )

        elif "yandex" in domain:
            servers.append(
                {"name": "Яндекс", "imap_server": "imap.yandex.ru", "imap_port": 993}
            )

        elif any(x in domain for x in ["mail.ru", "bk.ru", "inbox.ru"]):
            servers.append(
                {"name": "Mail.ru", "imap_server": "imap.mail.ru", "imap_port": 993}
            )

        elif any(x in domain for x in ["outlook.com", "hotmail.com", "live.com"]):
            servers.append(
                {
                    "name": "Outlook",
                    "imap_server": "outlook.office365.com",
                    "imap_port": 993,
                }
            )

        return servers

    async def get_imap_server(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает IMAP сервер"""
        imap_server = update.message.text.strip()

        if not imap_server or len(imap_server) < 5:
            await update.message.reply_text(
                "❌ Некорректный сервер. Введите правильный IMAP сервер:"
            )
            return IMAP_SERVER

        context.user_data["imap_server"] = imap_server

        await update.message.reply_text(
            f"✅ Сервер <b>{imap_server}</b> сохранен.\n\n"
            f"🔢 <b>Введите порт IMAP:</b>\n"
            f"Обычно 993 (SSL) или 143 (STARTTLS)\n\n"
            f"<i>Выберите вариант:</i>",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardMarkup(
                [["993 (SSL)", "143 (STARTTLS)"], ["Другой порт"]],
                resize_keyboard=True,
                one_time_keyboard=True,
            ),
        )
        return IMAP_PORT

    async def get_imap_port(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает IMAP порт"""
        port_text = update.message.text.strip()

        if port_text == "Другой порт":
            await update.message.reply_text(
                "🔢 Введите номер порта вручную:",
                reply_markup=ReplyKeyboardRemove(),
            )
            return IMAP_PORT

        try:
            if port_text.startswith("993") or port_text == "993 (SSL)":
                port = 993
            elif port_text.startswith("143") or port_text == "143 (STARTTLS)":
                port = 143
            else:
                port = int(port_text.split()[0])

                if port < 1 or port > 65535:
                    raise ValueError("Некорректный порт")

            context.user_data["imap_port"] = port

            await update.message.reply_text(
                f"✅ Порт <b>{port}</b> сохранен.\n\n"
                f"🔑 Теперь введите пароль от почты:",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            return PASSWORD

        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Некорректный порт. Введите число от 1 до 65535:",
                reply_markup=ReplyKeyboardRemove(),
            )
            return IMAP_PORT

    async def get_password(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает пароль"""
        password = update.message.text
        context.user_data["password"] = password

        hidden_password = (
            password[:2] + "*" * (len(password) - 2) if len(password) > 2 else "**"
        )

        await update.message.reply_text(
            f"📋 <b>Проверьте данные:</b>\n\n"
            f"📧 <b>Email:</b> {context.user_data['login']}\n"
            f"🌐 <b>IMAP сервер:</b> {context.user_data['imap_server']}\n"
            f"🔢 <b>IMAP порт:</b> {context.user_data['imap_port']}\n"
            f"🔑 <b>Пароль:</b> {hidden_password}\n\n"
            f"✅ <b>Все верно?</b>",
            parse_mode="HTML",
            reply_markup=self.get_confirmation_menu(),
        )
        return CONFIRMATION

    async def confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает подтверждение"""
        choice = update.message.text
        user_id = context.user_data.get("user_id")

        if choice == "✅ Да, сохранить":
            login = context.user_data["login"]
            password = context.user_data["password"]
            imap_server = context.user_data["imap_server"]
            imap_port = context.user_data["imap_port"]

            await update.message.reply_text(
                "🔐 Подключаюсь к почтовому серверу...",
                reply_markup=ReplyKeyboardRemove(),
            )

            email_client = EmailClient(login, password, imap_server, imap_port)
            if email_client.connect():
                email_client.disconnect()

                if user_manager.add_user(
                    user_id=user_id,
                    login=login,
                    password=password,
                    imap_server=imap_server,
                    imap_port=imap_port,
                ):
                    await update.message.reply_text(
                        f"🎉 <b>Настройка завершена!</b>\n\n"
                        f"✅ <b>Почта:</b> {login}\n"
                        f"🌐 <b>Сервер:</b> {imap_server}:{imap_port}\n"
                        f"🔄 <b>Автопроверка:</b> каждые 10 секунд\n\n"
                        f"<b>Выберите действие:</b>",
                        parse_mode="HTML",
                        reply_markup=self.get_main_menu(user_id),
                    )
                else:
                    await update.message.reply_text(
                        "❌ Ошибка сохранения данных.",
                        reply_markup=self.get_main_menu(user_id),
                    )
            else:
                await update.message.reply_text(
                    "❌ Не удалось подключиться.\n\n"
                    "Возможные причины:\n"
                    "• Неправильный логин/пароль\n"
                    "• Неправильный сервер/порт\n"
                    "• IMAP не включен\n\n"
                    "Попробуйте снова /start",
                    reply_markup=self.get_main_menu(user_id),
                )

            return ConversationHandler.END

        elif choice == "🔄 Ввести заново":
            await update.message.reply_text(
                "Введите ваш email:", reply_markup=ReplyKeyboardRemove()
            )
            return LOGIN

        elif choice == "❌ Отмена":
            await update.message.reply_text(
                "Настройка отменена.", reply_markup=self.get_main_menu(user_id)
            )
            return ConversationHandler.END

        else:
            await update.message.reply_text(
                "Пожалуйста, выберите один из вариантов:",
                reply_markup=self.get_confirmation_menu(),
            )
            return CONFIRMATION

    # ==================== ОСНОВНЫЕ ФУНКЦИИ ====================

    async def check_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Проверяет почту и показывает новые письма"""
        user_id = update.message.from_user.id

        user_data = user_manager.get_user_data(user_id)
        if not user_data:
            await update.message.reply_text(
                "❌ У вас нет сохраненных данных.\n"
                "Используйте кнопку '📝 Начать настройку'",
                reply_markup=self.get_main_menu(user_id),
            )
            return

        await update.message.reply_text(
            "📨 Проверяю почту...", reply_markup=ReplyKeyboardRemove()
        )

        await self._check_user_emails(
            user_id, update.message.reply_text, notify_no_emails=True
        )

        await update.message.reply_text(
            "Выберите следующее действие:", reply_markup=self.get_main_menu(user_id)
        )

    def _create_email_buttons(self, user_data):
        """Создает кнопку для открытия почтового ящика"""
        webmail_url = user_data.get("webmail_url", "")

        if webmail_url:
            button = InlineKeyboardButton(
                text="📬 Открыть почтовый ящик", url=webmail_url
            )
            return InlineKeyboardMarkup([[button]])

        return None

    async def _check_user_emails(
        self, user_id: int, reply_function, notify_no_emails=False
    ):
        """Внутренний метод для проверки почты пользователя"""
        user_data = user_manager.get_user_data(user_id)

        if not user_data:
            await reply_function(
                "❌ У тебя нет сохраненных данных. Используй /start чтобы настроить бота"
            )
            return False

        try:
            email_client = EmailClient(
                user_data["login"],
                user_data["password"],
                user_data["imap_server"],
                user_data["imap_port"],
            )

            emails = email_client.get_unread_emails(limit=5)

            if not emails:
                if notify_no_emails:
                    await reply_function("📭 Новых писем нет")
                email_client.disconnect()
                return True

            # Создаем кнопку для почтового ящика
            reply_markup = self._create_email_buttons(user_data)

            for email_data in emails:
                try:
                    analysis = gemini_client.analyze_email_for_reminder(
                        email_data["subject"], email_data["body"]
                    )

                    extracted_data = gemini_client.extract_dates_and_links(
                        email_data["subject"], email_data["body"]
                    )

                    events_added = event_manager.add_event_from_email(
                        user_id, email_data["subject"], email_data["body"]
                    )

                    email_from = html.escape(email_data["from"])
                    email_subject = html.escape(email_data["subject"])
                    email_date = html.escape(str(email_data["date"]))
                    analysis_escaped = html.escape(analysis)

                    message = (
                        f"📧 <b>От:</b> {email_from}\n"
                        f"📬 <b>Тема:</b> {email_subject}\n"
                        f"🕒 <b>Дата письма:</b> {email_date}\n"
                        f"🔍 <b>Анализ:</b>\n{analysis_escaped}\n"
                    )

                    if email_data.get("has_attachments") and email_data.get(
                        "attachments"
                    ):
                        attachments = email_data["attachments"]
                        message += f"\n📎 <b>Вложения ({len(attachments)}):</b>\n"
                        for i, att in enumerate(attachments[:3], 1):
                            size_kb = att["size"] / 1024
                            message += f"• {att['filename']} ({size_kb:.1f} KB)\n"

                        if len(attachments) > 3:
                            message += f"• ... и еще {len(attachments) - 3}\n"

                    if events_added:
                        events_text = "\n".join(
                            [f"📅 {e['title']} - {e['date']}" for e in events_added]
                        )
                        message += f"\n🎯 <b>Найдены события:</b>\n{events_text}\n"

                    if extracted_data.get("links"):
                        links_text = "\n".join(
                            [f"🔗 {link}" for link in extracted_data["links"][:3]]
                        )
                        message += f"\n🔗 <b>Важные ссылки:</b>\n{links_text}\n"

                    await reply_function(
                        message, parse_mode="HTML", reply_markup=reply_markup
                    )

                except Exception as e:
                    logger.error(f"Ошибка при обработке письма: {e}")
                    await reply_function(
                        f"❌ Ошибка при обработке письма: {email_data.get('subject', 'Без темы')}",
                        reply_markup=reply_markup,
                    )

            email_client.disconnect()
            return True

        except Exception as e:
            logger.error(f"Ошибка при проверке почты пользователя {user_id}: {e}")
            if notify_no_emails:
                await reply_function("❌ Ошибка при проверке почты")
            return False

    async def show_events(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает события пользователя"""
        user_id = update.message.from_user.id
        events = event_manager.get_upcoming_events(user_id, days=30)

        if not events:
            await update.message.reply_text(
                "📅 У тебя пока нет предстоящих событий.",
                reply_markup=self.get_main_menu(user_id),
            )
            return

        message = "📅 <b>Твои предстоящие события:</b>\n\n"
        for event in events:
            try:
                event_date_str = event.get("date", event.get("original_date", ""))
                if not event_date_str:
                    continue

                event_date = None
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        event_date = datetime.strptime(event_date_str, fmt)
                        break
                    except ValueError:
                        continue

                if not event_date:
                    continue

                event_date_formatted = event_date.strftime("%d.%m.%Y")
                days_left = (event_date.date() - datetime.now().date()).days

                if days_left == 0:
                    days_text = "⏰ <b>СЕГОДНЯ!</b>"
                elif days_left == 1:
                    days_text = "🚨 <b>Завтра!</b>"
                elif days_left < 0:
                    days_text = f"❌ Просрочено ({abs(days_left)} дн. назад)"
                else:
                    days_text = f"⏳ Через {days_left} дн."

                message += f"<b>{event_date_formatted}</b> - {event['title'][:50]}\n"
                message += f"   {days_text}\n\n"

            except Exception as e:
                logger.error(f"Ошибка при отображении события: {e}")
                continue

        await update.message.reply_text(
            message, parse_mode="HTML", reply_markup=self.get_main_menu(user_id)
        )

    async def show_statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает статистику пользователя"""
        user_id = update.message.from_user.id
        user_data = user_manager.get_user_data(user_id)

        if not user_data:
            await update.message.reply_text(
                "❌ У вас нет сохраненных данных.",
                reply_markup=self.get_main_menu(user_id),
            )
            return

        events_count = len(event_manager.get_user_events(user_id))
        upcoming_events = len(event_manager.get_upcoming_events(user_id, days=7))

        await update.message.reply_text(
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"📧 <b>Почта:</b> {user_data['login']}\n"
            f"🌐 <b>Сервер:</b> {user_data['imap_server']}:{user_data['imap_port']}\n"
            f"📅 <b>Всего событий:</b> {events_count}\n"
            f"🎯 <b>Предстоящие (7 дней):</b> {upcoming_events}\n"
            f"🔄 <b>Автопроверка:</b> каждые 10 секунд\n",
            parse_mode="HTML",
            reply_markup=self.get_main_menu(user_id),
        )

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает справку"""
        help_text = (
            "🆘 <b>Справка по боту:</b>\n\n"

            "📋 <b>Основные функции:</b>\n"

            "• 📧 <b>Проверить почту</b> - ручная проверка новых писем\n"

            "• 🔄 <b>Автопроверка</b> - настройка автоматической проверки\n"

            "• 📅 <b>Мои события</b> - просмотр найденных событий\n"

            "• ⚙️ <b>Настройки</b> - настройка бота\n"

            "• 📊 <b>Статистика</b> - ваша статистика\n\n"

            "🔐 <b>Безопасность:</b>\n"

            "• Ваши данные шифруются\n"
            "• Пароли хранятся безопасно\n\n"
            
            "🤖 <b>AI функции:</b>\n"
            "• Автоматический анализ писем\n"
            "• Извлечение дат и событий\n"
            "• Определение срочности\n"
            "• Поиск важных ссылок"
        )

        await update.message.reply_text(
            help_text,
            parse_mode="HTML",
            reply_markup=self.get_main_menu(update.message.from_user.id),
        )

    async def show_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показывает информацию о боте"""
        about_text = (
            "ℹ️ <b>О боте:</b>\n\n"
            "🤖 <b>Умный почтовый ассистент</b>\n"
            "Версия: 2.0\n\n"
            "🚀 <b>Возможности:</b>\n"
            "• Проверка почты\n"
            "• AI анализ через Gemini\n"
            "• Автоматический календарь\n"
            "• Безопасное хранение\n\n"
            "🔧 <b>Технологии:</b>\n"
            "• Python 3\n"
            "• Telegram Bot API\n"
            "• Google Gemini AI\n"
            "• Шифрование"
        )

        await update.message.reply_text(
            about_text,
            parse_mode="HTML",
            reply_markup=self.get_main_menu(update.message.from_user.id),
        )

    # ==================== ОБРАБОТЧИКИ КНОПОК МЕНЮ ====================

    async def handle_menu_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обрабатывает нажатия кнопок в меню"""
        user_id = update.message.from_user.id
        text = update.message.text

        # Проверяем, ждем ли подтверждения удаления
        if context.user_data.get("awaiting_delete_confirmation"):
            await self.handle_delete_confirmation(update, context)
            return

        if text == "📝 Начать настройку":
            await self.start(update, context)

        elif text == "📧 Проверить почту":
            await self.check_email(update, context)
        elif text == "🔄 Автопроверка":
            await update.message.reply_text(
                "🔧 <b>Настройка автопроверки:</b>\n\n" "Выберите действие:",
                parse_mode="HTML",
                reply_markup=self.get_autocheck_menu(),
            )

        elif text == "✅ Включить автопроверку":
            await update.message.reply_text(
                "✅ Автопроверка включена!",
                reply_markup=self.get_main_menu(user_id),
            )

        elif text == "❌ Выключить автопроверку":
            await update.message.reply_text(
                "❌ Автопроверка выключена.",
                reply_markup=self.get_main_menu(user_id),
            )

        elif text == "📅 Мои события":
            await self.show_events(update, context)

        elif text == "⚙️ Настройки":
            await update.message.reply_text(
                "⚙️ <b>Настройки бота:</b>\n\n" "Выберите раздел настроек:",
                parse_mode="HTML",
                reply_markup=self.get_settings_menu(),
            )

        elif text == "✏️ Изменить данные":
            await update.message.reply_text(
                "🔄 Для изменения данных нужно пройти настройку заново.\n"
                "Используйте /start для перенастройки бота.",
                reply_markup=self.get_main_menu(user_id),
            )

        elif text == "⏰ Интервал проверки":
            await update.message.reply_text(
                "⏰ <b>Интервал автопроверки:</b>\n\n"
                "Текущий интервал: 10 секунд\n\n"
                "ℹ️ Для изменения интервала обратитесь к администратору или "
                "измените настройки в коде бота.",
                parse_mode="HTML",
                reply_markup=self.get_settings_menu(),
            )

        elif text == "🔔 Напоминания":
            await update.message.reply_text(
                "🔔 <b>Настройки напоминаний:</b>\n\n"
                "✅ Напоминания включены\n"
                "📅 Напоминания приходят за 7, 3 и 1 день до события\n"
                "⏰ Проверка событий: каждый час\n\n"
                "Все события автоматически извлекаются из ваших писем!",
                parse_mode="HTML",
                reply_markup=self.get_settings_menu(),
            )

        elif text == "🔐 Безопасность":
            await update.message.reply_text(
                "🔐 <b>Информация о безопасности:</b>\n\n"
                "✅ Ваши пароли зашифрованы\n"
                "✅ Используется криптография Fernet\n"
                "✅ Данные хранятся локально\n"
                "✅ Соединение с почтой по SSL\n\n"
                "⚠️ Для полного удаления данных используйте /delete",
                parse_mode="HTML",
                reply_markup=self.get_settings_menu(),
            )

        elif text == "📊 Статистика":
            await self.show_statistics(update, context)

        elif text == "🆘 Помощь":
            await self.show_help(update, context)

        elif text == "ℹ️ О боте":
            await self.show_about(update, context)

        elif text == "⬅️ Назад в меню":
            await update.message.reply_text(
                "Главное меню:", reply_markup=self.get_main_menu(user_id)
            )

        elif text == "⬅️ Назад":
            await update.message.reply_text(
                "Главное меню:", reply_markup=self.get_main_menu(user_id)
            )

        else:
            # Если кнопка не распознана
            await update.message.reply_text(
                "❓ Команда не распознана. Выберите действие из меню:",
                reply_markup=self.get_main_menu(user_id),
            )
    # ==================== ФОНОВЫЕ ЗАДАЧИ ====================

    async def auto_check_all_users(self, context: ContextTypes.DEFAULT_TYPE):
        """Автоматическая проверка почты для всех пользователей"""
        if not user_manager.users:
            return

        for user_id in list(user_manager.users.keys()):
            try:
                user_data = user_manager.get_user_data(int(user_id))
                if not user_data:
                    continue

                # Проверяем, включена ли автопроверка
                autocheck_enabled = user_data.get("autocheck_enabled", True)
                if not autocheck_enabled:
                    continue

                # Проверяем, включены ли уведомления
                notifications_enabled = user_data.get("notifications_enabled", True)
                if not notifications_enabled:
                    continue

                await self._check_user_emails(
                    int(user_id),
                    lambda message, **kwargs: context.bot.send_message(
                        chat_id=int(user_id), text=message, **kwargs
                    ),
                    notify_no_emails=False,
                )
            except Exception as e:
                logger.error(f"Ошибка автопроверки для пользователя {user_id}: {e}")
                continue


    async def send_event_reminders(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет напоминания о событиях"""
        reminders = event_manager.get_events_for_reminder()

        for user_id, event, days_until in reminders:
            try:
                # Проверяем настройки пользователя
                user_data = user_manager.get_user_data(user_id)
                if not user_data:
                    continue

                reminder_days = user_data.get("reminder_days", [7, 3, 1, 0])

                # Проверяем, нужно ли отправлять напоминание для этого количества дней
                if days_until not in reminder_days:
                    continue

                event_date_str = event.get("date", event.get("original_date", ""))
                if not event_date_str:
                    continue

                event_date = None
                for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                    try:
                        event_date = datetime.strptime(event_date_str, fmt)
                        break
                    except ValueError:
                        continue

                if not event_date:
                    continue

                event_date_formatted = event_date.strftime("%d.%m.%Y")

                if days_until == 0:
                    message = (
                        f"🎉 <b>СЕГОДНЯ!</b>\n"
                        f"Событие: {event['title']}\n"
                        f"Дата: {event_date_formatted}\n\n"
                        f"Не забудь про это событие сегодня!"
                    )
                else:
                    message = (
                        f"🔔 <b>Напоминание</b>\n"
                        f"Событие: {event['title']}\n"
                        f"Дата: {event_date_formatted}\n"
                        f"Осталось: {days_until} дней\n\n"
                        f"У тебя есть время подготовиться!"
                    )

                await context.bot.send_message(
                    chat_id=user_id, text=message, parse_mode="HTML"
                )
                event_manager.mark_reminder_sent(user_id, event["id"])

            except Exception as e:
                logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

    # ==================== СЛУЖЕБНЫЕ КОМАНДЫ ====================

    async def delete_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет данные пользователя"""
        user_id = update.message.from_user.id

        confirm_keyboard = ReplyKeyboardMarkup(
            [["✅ Да, удалить все данные"], ["❌ Нет, отмена"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await update.message.reply_text(
            "⚠️ <b>Внимание! Это действие необратимо!</b>\n\n"
            "Вы уверены, что хотите удалить все ваши данные?\n"
            "Это удалит:\n"
            "• Ваши почтовые данные\n"
            "• Все сохраненные события\n"
            "• Настройки бота\n\n"
            "<b>Продолжить?</b>",
            parse_mode="HTML",
            reply_markup=confirm_keyboard,
        )

        context.user_data["awaiting_delete_confirmation"] = True

    async def handle_delete_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает подтверждение удаления"""
        user_id = update.message.from_user.id
        choice = update.message.text

        if choice == "✅ Да, удалить все данные":
            if user_manager.delete_user(user_id):
                if user_id in event_manager.events:
                    del event_manager.events[user_id]
                    event_manager.save_events()

                await update.message.reply_text(
                    "✅ Все ваши данные успешно удалены.\n"
                    "Для новой настройки используйте /start",
                    reply_markup=ReplyKeyboardRemove(),
                )
            else:
                await update.message.reply_text(
                    "❌ Ошибка удаления данных или данных нет",
                    reply_markup=self.get_main_menu(user_id),
                )

        elif choice == "❌ Нет, отмена":
            await update.message.reply_text(
                "Удаление отменено.", reply_markup=self.get_main_menu(user_id)
            )

        if "awaiting_delete_confirmation" in context.user_data:
            del context.user_data["awaiting_delete_confirmation"]

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет диалог"""
        user_id = update.message.from_user.id
        
        # Очищаем все флаги
        if "awaiting_start_choice" in context.user_data:
            del context.user_data["awaiting_start_choice"]
        if "awaiting_reregister_confirmation" in context.user_data:
            del context.user_data["awaiting_reregister_confirmation"]
        if "awaiting_delete_confirmation" in context.user_data:
            del context.user_data["awaiting_delete_confirmation"]
        
        await update.message.reply_text(
            "❌ Настройка отменена.", reply_markup=self.get_main_menu(user_id)
        )
        return ConversationHandler.END

    # ==================== НАСТРОЙКА ОБРАБОТЧИКОВ ====================

    def setup_handlers(self):
        """Настраивает обработчики команд"""
        # Обработчик диалога регистрации
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", self.start),
                MessageHandler(filters.Regex("^📝 Начать настройку$"), self.start),
            ],
            states={
                LOGIN: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_login)
                ],
                IMAP_SERVER: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND, self.get_imap_server
                    )
                ],
                IMAP_PORT: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_imap_port)
                ],
                PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)
                ],
                CONFIRMATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirmation)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
            allow_reentry=True,
            per_message=False,  # ВАЖНО: не создавать новый разговор для каждого сообщения
        )

        # Обработчик изменения интервала
        interval_handler = ConversationHandler(
            entry_points=[
                MessageHandler(
                    filters.Regex("^⏰ Интервал проверки$"), self.change_check_interval
                )
            ],
            states={
                CHANGE_INTERVAL: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_interval_change)
                ],
            },
            fallbacks=[
                MessageHandler(
                    filters.Regex("^⬅️ Назад в настройки$"), self.cancel
                )
            ],
        )

        # Команды (высокий приоритет)
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("check", self.check_email))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("status", self.show_statistics))
        self.application.add_handler(CommandHandler("help", self.show_help))
        self.application.add_handler(CommandHandler("about", self.show_about))
        self.application.add_handler(CommandHandler("delete", self.delete_data))
        self.application.add_handler(CommandHandler("cancel", self.cancel))

        # Conversation handlers
        self.application.add_handler(conv_handler)
        self.application.add_handler(interval_handler)

        # Callback query handler для уведомлений
        self.application.add_handler(
            CallbackQueryHandler(self.handle_notification_callback)
        )

        # Обработчик кнопок меню (самый низкий приоритет)
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_menu_button)
        )

    def setup_jobs(self):
        """Настраивает фоновые задачи"""
        # Автоматическая проверка почты каждые 10 секунд
        self.application.job_queue.run_repeating(
            self.auto_check_all_users,
            interval=10,
            first=5,
        )

        # Проверка напоминаний о событиях каждые 1 час
        self.application.job_queue.run_repeating(
            self.send_event_reminders,
            interval=3600,
            first=10,
        )

    def run(self):
        """Запускает бота"""
        print("=" * 50)
        print("🤖 УМНЫЙ ПОЧТОВЫЙ АССИСТЕНТ")
        print("=" * 50)
        print("🔄 Автопроверка почты: каждые 10 секунд")
        print("📅 Календарь событий: автоматическое извлечение дат")
        print("🔔 Напоминания: за 7, 3 и 1 день до события")
        print("🤖 AI анализ: включен (Gemini)")
        print("=" * 50)
        print("🚀 Бот запускается...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = EmailBot()
    bot.run()
