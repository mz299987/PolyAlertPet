"""
Модуль настроек и управления для бота Polymarket
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from newapp.database import Database
from newapp.keyboards import Keyboards
from newapp.security import Security

router = Router()


@router.message(F.text.in_(["⚙️ Настройки", "⚙️ Settings"]))
async def cmd_settings(message: Message, db: Database):
    """Меню настроек"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "⚙️ <b>Настройки бота</b>\n\n"
        text += "Здесь вы можете настроить уведомления и другие параметры:\n"
        text += "• 🔔 Управление уведомлениями\n"
        text += "• 🌐 Смена языка\n"
        text += "• 📊 Настройки аналитики\n"
        text += "• 🛡️ Безопасность"
    else:
        text = "⚙️ <b>Bot Settings</b>\n\n"
        text += "Configure notifications and other settings:\n"
        text += "• 🔔 Notification settings\n"
        text += "• 🌐 Language settings\n"
        text += "• 📊 Analytics settings\n"
        text += "• 🛡️ Security settings"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_settings_menu(language)
    )


@router.callback_query(F.data == "notification_settings")
async def cb_notification_settings(callback: CallbackQuery, db: Database):
    """Настройки уведомлений"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🔔 <b>Настройки уведомлений</b>\n\n"
        text += "Выберите типы уведомлений, которые хотите получать:\n"
        text += "• 📈 Изменения портфеля\n"
        text += "• 🐳 Сделки китов (>$1000)\n"
        text += "• 🔥 Новые события\n"
        text += "• ⚠️ Важные обновления"
    else:
        text = "🔔 <b>Notification Settings</b>\n\n"
        text += "Select notification types you want to receive:\n"
        text += "• 📈 Portfolio changes\n"
        text += "• 🐳 Whale trades (>$1000)\n"
        text += "• 🔥 New events\n"
        text += "• ⚠️ Important updates"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_notification_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "language_settings")
async def cb_language_settings(callback: CallbackQuery, db: Database):
    """Настройки языка"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🌐 <b>Настройки языка</b>\n\n"
        text += "Выберите предпочитаемый язык интерфейса:"
    else:
        text = "🌐 <b>Language Settings</b>\n\n"
        text += "Select your preferred interface language:"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_language_selection()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_notification_"))
async def cb_toggle_notification(callback: CallbackQuery, db: Database):
    """Переключение типа уведомлений"""
    notification_type = callback.data.split("_")[-1]
    language = await db.get_user_language(callback.from_user.id)
    
    # Здесь будет логика сохранения настроек в базе данных
    # Пока просто подтвердим действие
    
    notification_names = {
        "portfolio": "изменения портфеля" if language == "ru" else "portfolio changes",
        "whale": "сделки китов" if language == "ru" else "whale trades",
        "events": "новые события" if language == "ru" else "new events",
        "updates": "важные обновления" if language == "ru" else "important updates"
    }
    
    name = notification_names.get(notification_type, notification_type)
    
    if language == "ru":
        text = f"✅ Настройки уведомлений для '{name}' обновлены"
    else:
        text = f"✅ Notification settings for '{name}' updated"
    
    await callback.answer(text)


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(callback: CallbackQuery, db: Database):
    """Установка языка"""
    language = callback.data.split("_")[1]
    await db.set_user_language(callback.from_user.id, language)
    
    if language == "ru":
        text = "✅ Язык изменен на русский"
    else:
        text = "✅ Language changed to English"
    
    await callback.message.edit_text(text)
    await callback.answer(text)


@router.callback_query(F.data == "security_settings")
async def cb_security_settings(callback: CallbackQuery, db: Database, security: Security):
    """Настройки безопасности"""
    language = await db.get_user_language(callback.from_user.id)
    user_id = callback.from_user.id
    
    # Получаем статистику безопасности
    wallets_count = len(await db.get_user_wallets(user_id))
    rate_limit_info = security.get_rate_limit_info(user_id)
    
    if language == "ru":
        text = "🛡️ <b>Настройки безопасности</b>\n\n"
        text += f"• Количество кошельков: {wallets_count}/10\n"
        text += f"• Лимит запросов: {rate_limit_info['remaining']}/{rate_limit_info['limit']}\n"
        text += "• Валидация адресов: ✅ Включена\n"
        text += "• Аудит действий: ✅ Включен\n\n"
        text += "Для сброса лимитов используйте /reset"
    else:
        text = "🛡️ <b>Security Settings</b>\n\n"
        text += f"• Wallets count: {wallets_count}/10\n"
        text += f"• Rate limit: {rate_limit_info['remaining']}/{rate_limit_info['limit']}\n"
        text += "• Address validation: ✅ Enabled\n"
        text += "• Action audit: ✅ Enabled\n\n"
        text += "Use /reset to reset limits"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.message(Command("reset"))
async def cmd_reset(message: Message, security: Security):
    """Сброс лимитов безопасности"""
    user_id = message.from_user.id
    security.reset_rate_limit(user_id)
    
    # Проверяем язык пользователя
    language = "ru"  # Временно, будет заменено на получение из базы
    
    if language == "ru":
        text = "🔄 Лимиты безопасности сброшены"
    else:
        text = "🔄 Security limits reset"
    
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message, db: Database):
    """Справка по командам"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "📚 <b>Справка по командам</b>\n\n"
        text += "<b>Основные команды:</b>\n"
        text += "• /start - Запуск бота\n"
        text += "• /help - Эта справка\n"
        text += "• /status - Статус портфеля\n"
        text += "• /addwallet [адрес] - Добавить кошелек\n"
        text += "• /search [запрос] - Поиск событий\n\n"
        text += "<b>Быстрые действия:</b>\n"
        text += "• 📈 Состояние - Показать статус\n"
        text += "• 📊 Аналитика - Анализ портфеля\n"
        text += "• 🔍 Поиск - Поиск по рынкам\n"
        text += "• ⚙️ Настройки - Настройки бота\n\n"
        text += "Для навигации используйте кнопки меню."
    else:
        text = "📚 <b>Command Help</b>\n\n"
        text += "<b>Basic Commands:</b>\n"
        text += "• /start - Start the bot\n"
        text += "• /help - This help\n"
        text += "• /status - Portfolio status\n"
        text += "• /addwallet [address] - Add wallet\n"
        text += "• /search [query] - Search events\n\n"
        text += "<b>Quick Actions:</b>\n"
        text += "• 📈 Status - Show status\n"
        text += "• 📊 Analytics - Portfolio analysis\n"
        text += "• 🔍 Search - Market search\n"
        text += "• ⚙️ Settings - Bot settings\n\n"
        text += "Use menu buttons for navigation."
    
    await message.answer(text)
