import logging
import html
from datetime import datetime
from typing import Dict, Optional
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

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
LOGIN, PASSWORD, CONFIRMATION = range(3)


class EmailBot:
    def __init__(self):
        self.application = Application.builder().token(Config.TELEGRAM_TOKEN).build()
        self.setup_handlers()
        self.setup_jobs()

    # ==================== МЕНЮ И КНОПКИ ====================

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

    def get_check_interval_menu(self):
        """Меню выбора интервала проверки"""
        return ReplyKeyboardMarkup(
            [
                ["⏱ 10 секунд", "⏱ 30 секунд"],
                ["⏱ 1 минута", "⏱ 5 минут"],
                ["⏱ 10 минут", "⏱ 30 минут"],
                ["⬅️ Назад в настройки"],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    def get_reminders_menu(self):
        """Меню настроек напоминаний"""
        return ReplyKeyboardMarkup(
            [
                ["🔔 Включить напоминания", "🔕 Выключить напоминания"],
                ["🕐 За 1 день", "🕑 За 3 дня"],
                ["🕒 За 7 дней", "🕓 За 14 дней"],
                ["⬅️ Назад в настройки"],
            ],
            resize_keyboard=True,
            one_time_keyboard=False,
        )

    def get_confirmation_menu(self):
        """Меню подтверждения"""
        return ReplyKeyboardMarkup(
            [["✅ Да, сохранить", "🔄 Ввести заново"], ["❌ Отмена"]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    def get_autocheck_menu(self):
        """Меню автопроверки"""
        return ReplyKeyboardMarkup(
            [
                ["✅ Включить автопроверку", "❌ Выключить автопроверку"],
                ["🕐 Каждые 10 сек", "🕑 Каждые 30 сек"],
                ["🕒 Каждые 1 мин", "🕓 Каждые 5 мин"],
                ["⬅️ Назад"],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

    # ==================== ОСНОВНЫЕ КОМАНДЫ ====================

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Начинает диалог с пользователем"""
        user = update.message.from_user
        context.user_data["user_id"] = user.id

        # Проверяем, есть ли уже данные пользователя
        existing_data = user_manager.get_user_data(user.id)

        if existing_data:
            # Пользователь уже зарегистрирован - показываем главное меню
            await update.message.reply_text(
                f"👋 Добро пожаловать, {user.first_name}!\n\n"
                f"✅ Ваш почтовый ящик: {existing_data['login']}\n"
                f"🔄 Автопроверка: активна (каждые 10 секунд)\n\n"
                f"Выберите действие:",
                parse_mode="HTML",
                reply_markup=self.get_main_menu(user.id),
            )
            return ConversationHandler.END
        else:
            # Пользователь не зарегистрирован - начинаем регистрацию
            await update.message.reply_text(
                f"👋 Привет, {user.first_name}!\n\n"
                "🤖 Я - умный почтовый ассистент с искусственным интеллектом!\n\n"
                "📧 <b>Что я умею:</b>\n"
                "• Автоматически проверять вашу почту\n"
                "• Анализировать письма с помощью AI\n"
                "• Создавать умные напоминания\n"
                "• Находить даты и события в письмах\n"
                "• Отправлять уведомления о новых письмах\n\n"
                "🔐 <b>Безопасность:</b>\n"
                "Ваши данные шифруются и хранятся безопасно.\n\n"
                "📝 <b>Для начала работы введите ваш email логин:</b>",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove(),
            )
            return LOGIN

    async def get_login(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает логин от пользователя"""
        login = update.message.text.strip()

        # Простая валидация email
        if "@" not in login:
            await update.message.reply_text(
                "❌ Это не похоже на email адрес. Пожалуйста, введи корректный email:"
            )
            return LOGIN

        context.user_data["login"] = login

        await update.message.reply_text(
            f"✅ Логин <b>{login}</b> сохранен.\n\n"
            "🔑 Теперь введите пароль от вашей почты:",
            parse_mode="HTML",
            reply_markup=ReplyKeyboardRemove(),
        )
        return PASSWORD

    async def get_password(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Получает пароль от пользователя"""
        password = update.message.text
        context.user_data["password"] = password

        # Показываем частично скрытый пароль для подтверждения
        hidden_password = (
            password[:2] + "*" * (len(password) - 2) if len(password) > 2 else "**"
        )

        await update.message.reply_text(
            f"📋 <b>Проверьте введенные данные:</b>\n\n"
            f"📧 <b>Email:</b> {context.user_data['login']}\n"
            f"🔑 <b>Пароль:</b> {hidden_password}\n\n"
            f"✅ <b>Все верно?</b>",
            parse_mode="HTML",
            reply_markup=self.get_confirmation_menu(),
        )
        return CONFIRMATION

    async def confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> int:
        """Обрабатывает подтверждение от пользователя"""
        choice = update.message.text
        user_id = context.user_data.get("user_id")

        if choice == "✅ Да, сохранить":
            login = context.user_data["login"]
            password = context.user_data["password"]

            await update.message.reply_text(
                "🔐 Подключаюсь к почтовому серверу...",
                reply_markup=ReplyKeyboardRemove(),
            )

            # Пробуем подключиться к почте
            email_client = EmailClient(
                login, password, Config.IMAP_SERVER, Config.IMAP_PORT
            )
            if email_client.connect():
                email_client.disconnect()

                # Сохраняем данные пользователя
                if user_manager.add_user(user_id, login, password):
                    await update.message.reply_text(
                        f"🎉 <b>Поздравляю! Настройка завершена!</b>\n\n"
                        f"✅ <b>Почта:</b> {login}\n"
                        f"🔄 <b>Автопроверка:</b> каждые 10 секунд\n"
                        f"📅 <b>Календарь:</b> автоматическое извлечение дат\n"
                        f"🤖 <b>AI анализ:</b> включен\n\n"
                        f"🚀 <b>Теперь вы можете:</b>\n"
                        f"• Проверить почту вручную\n"
                        f"• Просмотреть найденные события\n"
                        f"• Настроить интервал проверки\n"
                        f"• Управлять напоминаниями\n\n"
                        f"<b>Выберите действие:</b>",
                        parse_mode="HTML",
                        reply_markup=self.get_main_menu(user_id),
                    )
                else:
                    await update.message.reply_text(
                        "❌ Ошибка сохранения данных. Попробуйте снова.",
                        reply_markup=self.get_main_menu(user_id),
                    )
            else:
                await update.message.reply_text(
                    "❌ Не удалось подключиться к почтовому серверу.\n\n"
                    "Возможные причины:\n"
                    "• Неправильный логин или пароль\n"
                    "• IMAP не включен в настройках почты\n"
                    "• Требуется пароль приложения (если включена 2FA)\n\n"
                    "Попробуйте снова /start",
                    reply_markup=self.get_main_menu(user_id),
                )

            return ConversationHandler.END

        elif choice == "🔄 Ввести заново":
            await update.message.reply_text(
                "Введите ваш email логин:", reply_markup=ReplyKeyboardRemove()
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

    # ==================== ОБРАБОТЧИКИ КНОПОК МЕНЮ ====================

    async def handle_menu_button(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает нажатия кнопок в меню"""
        user_id = update.message.from_user.id
        text = update.message.text

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
                "✅ Автопроверка включена! Буду проверять почту автоматически.",
                reply_markup=self.get_main_menu(user_id),
            )

        elif text == "❌ Выключить автопроверку":
            await update.message.reply_text(
                "❌ Автопроверка выключена. Используйте ручную проверку.",
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
                "Для изменения данных почты введите новый email логин:",
                reply_markup=ReplyKeyboardRemove(),
            )
            context.user_data["changing_data"] = True
            return LOGIN

        elif text == "⏰ Интервал проверки":
            await update.message.reply_text(
                "⏰ <b>Выберите интервал автоматической проверки:</b>",
                parse_mode="HTML",
                reply_markup=self.get_check_interval_menu(),
            )

        elif text == "🔔 Напоминания":
            await update.message.reply_text(
                "🔔 <b>Настройка напоминаний:</b>\n\n"
                "Выберите когда напоминать о событиях:",
                parse_mode="HTML",
                reply_markup=self.get_reminders_menu(),
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

        elif text == "⬅️ Назад в настройки":
            await update.message.reply_text(
                "⚙️ Настройки бота:",
                parse_mode="HTML",
                reply_markup=self.get_settings_menu(),
            )

        elif text == "⬅️ Назад":
            await update.message.reply_text(
                "Главное меню:", reply_markup=self.get_main_menu(user_id)
            )

        # Обработка интервалов проверки
        elif text in [
            "⏱ 10 секунд",
            "⏱ 30 секунд",
            "⏱ 1 минута",
            "⏱ 5 минут",
            "⏱ 10 минут",
            "⏱ 30 минут",
        ]:
            interval_text = text.split(" ")[1]
            await update.message.reply_text(
                f"✅ Интервал проверки установлен: {interval_text}",
                reply_markup=self.get_settings_menu(),
            )

        # Обработка напоминаний
        elif text in ["🔔 Включить напоминания", "🔕 Выключить напоминания"]:
            status = "включены" if "Включить" in text else "выключены"
            await update.message.reply_text(
                f"✅ Напоминания {status}", reply_markup=self.get_reminders_menu()
            )

        elif text in ["🕐 За 1 день", "🕑 За 3 дня", "🕒 За 7 дней", "🕓 За 14 дней"]:
            days = text.split(" ")[1]
            await update.message.reply_text(
                f"✅ Напоминания будут отправляться за {days} дня до события",
                reply_markup=self.get_reminders_menu(),
            )

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

        # Возвращаем меню
        await update.message.reply_text(
            "Выберите следующее действие:", reply_markup=self.get_main_menu(user_id)
        )

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
                Config.IMAP_SERVER,
                Config.IMAP_PORT,
            )

            emails = email_client.get_unread_emails(limit=5)

            if not emails:
                if notify_no_emails:
                    await reply_function("📭 Новых писем нет")
                email_client.disconnect()
                return True

            # Кэш для хранения полных текстов писем (в памяти на время сессии)
            if not hasattr(self, 'email_cache'):
                self.email_cache = {}
        
            for email_data in emails:
                try:
                    # Сохраняем в кэш
                    self.email_cache[email_data['id']] = email_data
                
                    # Анализируем письмо с помощью Gemini
                    analysis = gemini_client.analyze_email_for_reminder(
                        email_data["subject"], email_data["body"]
                    )

                    extracted_data = gemini_client.extract_dates_and_links(
                        email_data["subject"], email_data["body"]
                    )

                    events_added = event_manager.add_event_from_email(
                        user_id, email_data["subject"], email_data["body"]
                    )

                    # Экранируем специальные символы
                    email_from = html.escape(email_data["from"])
                    email_subject = html.escape(email_data["subject"])
                    email_date = html.escape(str(email_data["date"]))
                    analysis_escaped = html.escape(analysis)

                    # Формируем сообщение
                    message = (
                        f"📧 <b>От:</b> {email_from}\n"
                        f"📬 <b>Тема:</b> {email_subject}\n"
                        f"🕒 <b>Дата письма:</b> {email_date}\n"
                        f"🔍 <b>Анализ:</b>\n{analysis_escaped}\n"
                    )

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

                    # Получаем кнопки для письма
                    reply_markup = self._get_email_buttons(email_data, user_data)

                    await reply_function(
                        message, 
                        parse_mode="HTML",
                        reply_markup=reply_markup
                    )

                except Exception as e:
                    logger.error(f"Ошибка при обработке письма: {e}")
                    await reply_function(
                        f"❌ Ошибка при обработке письма: {email_data.get('subject', 'Без темы')}"
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
                "📅 У тебя пока нет предстоящих событий на ближайшие 30 дней.",
                reply_markup=self.get_main_menu(user_id),
            )
            return

        message = "📅 <b>Твои предстоящие события:</b>\n\n"
        for event in events:
            try:
                event_date_str = event.get("date", event.get("original_date", ""))
                if not event_date_str:
                    continue

                # Пробуем разные форматы дат
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
                reminder_status = "🔔" if event.get("reminder_sent") else "🔕"

                if days_left == 0:
                    days_text = "⏰ <b>СЕГОДНЯ!</b>"
                elif days_left == 1:
                    days_text = "🚨 <b>Завтра!</b>"
                elif days_left < 0:
                    days_text = f"❌ Просрочено ({abs(days_left)} дн. назад)"
                else:
                    days_text = f"⏳ Через {days_left} дн."

                message += f"{reminder_status} <b>{event_date_formatted}</b> - {event['title'][:50]}\n"
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
        total_users = len(user_manager.users)

        await update.message.reply_text(
            f"📊 <b>Ваша статистика:</b>\n\n"
            f"📧 <b>Почта:</b> {user_data['login']}\n"
            f"📅 <b>Всего событий:</b> {events_count}\n"
            f"🎯 <b>Предстоящие (7 дней):</b> {upcoming_events}\n"
            f"🔄 <b>Автопроверка:</b> каждые 10 секунд\n"
            f"🤖 <b>AI анализ:</b> включен\n"
            f"👥 <b>Всего пользователей бота:</b> {total_users}\n\n"
            f"<i>Статистика обновляется автоматически</i>",
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
            "⚙️ <b>Настройки:</b>\n"
            "• ✏️ <b>Изменить данные</b> - изменить логин/пароль\n"
            "• ⏰ <b>Интервал проверки</b> - настроить частоту проверки\n"
            "• 🔔 <b>Напоминания</b> - управление уведомлениями\n\n"
            "🔐 <b>Безопасность:</b>\n"
            "• Ваши данные шифруются и хранятся безопасно\n"
            "• Пароли никогда не передаются в открытом виде\n\n"
            "🤖 <b>AI функции:</b>\n"
            "• Автоматический анализ писем\n"
            "• Извлечение дат и событий\n"
            "• Определение срочности\n"
            "• Поиск важных ссылок\n\n"
            "📞 <b>Поддержка:</b>\n"
            "Для связи с разработчиком используйте команду /feedback"
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
            "Версия: 2.0\n"
            "Разработчик: Anvarjon\n\n"
            "🚀 <b>Возможности:</b>\n"
            "• Интеграция с iRedMail\n"
            "• AI анализ через Gemini\n"
            "• Автоматический календарь\n"
            "• Умные напоминания\n"
            "• Безопасное хранение\n\n"
            "🔧 <b>Технологии:</b>\n"
            "• Python 3.13\n"
            "• Telegram Bot API\n"
            "• Google Gemini AI\n"
            "• Шифрование AES-256\n\n"
            "⭐ <b>Особенности:</b>\n"
            "• Поддержка нескольких пользователей\n"
            "• Настраиваемые интервалы\n"
            "• Удобное меню\n"
            "• Подробная статистика\n"
            "• Регулярные обновления"
        )

        await update.message.reply_text(
            about_text,
            parse_mode="HTML",
            reply_markup=self.get_main_menu(update.message.from_user.id),
        )

    # ==================== ФОНОВЫЕ ЗАДАЧИ ====================

    async def auto_check_all_users(self, context: ContextTypes.DEFAULT_TYPE):
        """Автоматическая проверка почты для всех пользователей"""
        if not user_manager.users:
            return

        for user_id in list(user_manager.users.keys()):
            try:
                user_data = user_manager.get_user_data(user_id)
                if user_data:
                    # notify_no_emails=False - не отправляем сообщение если писем нет
                    await self._check_user_emails(
                        user_id,
                        lambda message, **kwargs: context.bot.send_message(
                            chat_id=user_id, text=message, **kwargs
                        ),
                        notify_no_emails=False,  # Не уведомляем об отсутствии писем
                    )
            except Exception as e:
                logger.error(f"Ошибка автопроверки для пользователя {user_id}: {e}")
                continue

    async def send_event_reminders(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправляет напоминания о событиях"""
        reminders = event_manager.get_events_for_reminder()

        for user_id, event, days_until in reminders:
            try:
                event_date_str = event.get("date", event.get("original_date", ""))
                if not event_date_str:
                    continue

                # Пробуем разные форматы дат
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
                        f"У тебя есть время подготовиться! 🎯"
                    )

                await context.bot.send_message(
                    chat_id=user_id, text=message, parse_mode="HTML"
                )
                event_manager.mark_reminder_sent(user_id, event["id"])

            except Exception as e:
                logger.error(f"Ошибка отправки напоминания пользователю {user_id}: {e}")

    # ==================== СЛУЖЕБНЫЕ КОМАНДЫ ====================

    async def delete_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаляет данные пользователя (через команду)"""
        user_id = update.message.from_user.id

        # Создаем меню подтверждения удаления
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

        # Ждем подтверждения
        context.user_data["awaiting_delete_confirmation"] = True

    async def handle_delete_confirmation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает подтверждение удаления"""
        user_id = update.message.from_user.id
        choice = update.message.text

        if choice == "✅ Да, удалить все данные":
            if user_manager.delete_user(user_id):
                # Также удаляем события пользователя
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

        # Очищаем флаг
        if "awaiting_delete_confirmation" in context.user_data:
            del context.user_data["awaiting_delete_confirmation"]

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Отменяет диалог"""
        user_id = update.message.from_user.id
        await update.message.reply_text(
            "Настройка отменена.", reply_markup=self.get_main_menu(user_id)
        )
        return ConversationHandler.END

    # ==================== НАСТРОЙКА ОБРАБОТЧИКОВ ====================
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатий на инлайн-кнопки"""
        query = update.callback_query
        await query.answer()
    
        user_id = query.from_user.id
        data = query.data
    
        if data.startswith("fulltext_"):
            email_id = data.replace("fulltext_", "")
        
            # Ищем письмо в кэше
            if hasattr(self, 'email_cache') and email_id in self.email_cache:
                email_data = self.email_cache[email_id]
            
                # Формируем сообщение с полным текстом
                full_text = email_data.get('full_body', email_data.get('body', 'Текст письма не найден'))
            
                # Ограничиваем длину для Telegram (ограничение 4096 символов)
                if len(full_text) > 4000:
                    full_text = full_text[:4000] + "...\n\n[текст сокращен]"
            
                # Экранируем HTML
                full_text_escaped = html.escape(full_text)
            
                message = (
                    f"📧 <b>Полный текст письма:</b>\n\n"
                    f"<b>От:</b> {html.escape(email_data.get('from', 'Неизвестно'))}\n"
                    f"<b>Тема:</b> {html.escape(email_data.get('subject', 'Без темы'))}\n"
                    f"<b>Дата:</b> {html.escape(str(email_data.get('date', '')))}\n\n"
                    f"<code>{full_text_escaped}</code>"
                )
            
                # Кнопки для этого письма
                reply_markup = self._get_email_buttons(email_data, {})
            
                await query.edit_message_text(
                    text=message,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await query.edit_message_text(
                    text="❌ Текст письма больше не доступен в кэше",
                    parse_mode="HTML"
                )

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
                PASSWORD: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.get_password)
                ],
                CONFIRMATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, self.confirmation)
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        
        # Добавляем обработчик инлайн-кнопок
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Добавляем обработчики
        self.application.add_handler(conv_handler)

        # Обработчик кнопок меню
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_menu_button)
        )

        # Обработчик подтверждения удаления
        self.application.add_handler(
            MessageHandler(
                filters.Regex("^(✅ Да, удалить все данные|❌ Нет, отмена)$"),
                self.handle_delete_confirmation,
            )
        )

        # Команды (для совместимости со старыми командами)
        self.application.add_handler(CommandHandler("check", self.check_email))
        self.application.add_handler(CommandHandler("events", self.show_events))
        self.application.add_handler(CommandHandler("status", self.show_statistics))
        self.application.add_handler(CommandHandler("help", self.show_help))
        self.application.add_handler(CommandHandler("about", self.show_about))
        self.application.add_handler(CommandHandler("delete", self.delete_data))

    def setup_jobs(self):
        """Настраивает фоновые задачи"""
        # Автоматическая проверка почты каждые 10 секунд
        self.application.job_queue.run_repeating(
            self.auto_check_all_users,
            interval=10,  # 10 секунд
            first=5,  # Первый запуск через 5 секунд после старта
        )

        # Проверка напоминаний о событиях каждые 1 час
        self.application.job_queue.run_repeating(
            self.send_event_reminders,
            interval=3600,  # 1 час
            first=10,  # Первый запуск через 10 секунд
        )

    # В класс EmailBot добавим метод:


    def _get_email_buttons(
        self, email_data: Dict, user_data: Dict
    ) -> Optional[InlineKeyboardMarkup]:
        """Создает кнопки для письма"""
        buttons = []

        # Пробуем создать прямую ссылку на письмо
        direct_link = None

        # Вариант 1: Используем готовый шаблон из конфигурации
        if Config.WEBMAIL_MESSAGE_URL and email_data.get("uid"):
            direct_link = Config.WEBMAIL_MESSAGE_URL.replace(
                "{uid}", str(email_data["uid"])
            )

        # Вариант 2: Генерируем ссылку в зависимости от типа веб-интерфейса
        elif Config.WEBMAIL_TYPE == "roundcube" and email_data.get("uid"):
            direct_link = f"{Config.WEBMAIL_BASE_URL}/?_task=mail&_action=show&_uid={email_data['uid']}&_mbox=INBOX"

        elif Config.WEBMAIL_TYPE == "squirrelmail" and email_data.get("id"):
            direct_link = f"{Config.WEBMAIL_BASE_URL}/src/read_body.php?mailbox=INBOX&passed_id={email_data['id']}"

        elif Config.WEBMAIL_TYPE == "iredmail" and email_data.get("uid"):
            direct_link = f"{Config.WEBMAIL_BASE_URL}/mail/?_task=mail&_action=show&_uid={email_data['uid']}&_mbox=INBOX"

        # Если есть прямая ссылка, добавляем кнопку
        if direct_link:
            buttons.append([InlineKeyboardButton("📨 Открыть письмо", url=direct_link)])

        # Всегда добавляем кнопку для открытия почтового ящика
        if Config.WEBMAIL_BASE_URL:
            buttons.append(
                [
                    InlineKeyboardButton(
                        "📬 Открыть почтовый ящик", url=Config.WEBMAIL_BASE_URL
                    )
                ]
            )

        # Добавляем кнопку для просмотра полного текста в Telegram
        buttons.append(
            [
                InlineKeyboardButton(
                    "📄 Показать полный текст", callback_data=f"fulltext_{email_data['id']}"
                )
            ]
        )

        if buttons:
            return InlineKeyboardMarkup(buttons)
        return None

    def run(self):
        """Запускает бота""" 
        print("=" * 50)
        print("🤖 УМНЫЙ ПОЧТОВЫЙ АССИСТЕНТ")
        print("=" * 50)
        print("🔄 Автопроверка почты: каждые 10 секунд")
        print("📅 Календарь событий: автоматическое извлечение дат")
        print("🔔 Напоминания: за 7, 3 и 1 день до события")
        print("🤖 AI анализ: включен (Gemini)")
        print("🔐 Безопасность: шифрование AES-256")
        print("=" * 50)
        print("🚀 Бот запускается...")
        self.application.run_polling()


if __name__ == "__main__":
    bot = EmailBot()
    bot.run()
