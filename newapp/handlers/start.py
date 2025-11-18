from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery

from newapp.database import Database
from newapp.keyboards import Keyboards

router = Router()


@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message, db: Database):
    """Обработка команды /start с выбором языка"""
    await db.ensure_user(message.from_user.id)
    
    # Показываем выбор языка (по умолчанию английский)
    text = "🌐 <b>Welcome to Polymarket Tracker!</b>\n\n"
    text += "Please select your preferred language:\n"
    text += "🇷🇺 Русский\n"
    text += "🇺🇸 English"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_language_selection_start()
    )


@router.callback_query(F.data.startswith("lang_start_"))
async def cb_set_language_start(callback: CallbackQuery, db: Database):
    """Обработка выбора языка при старте"""
    language = callback.data.split("_")[2]
    await db.set_user_language(callback.from_user.id, language)
    
    # Показываем подробное объяснение работы бота
    if language == "ru":
        text = "👋 <b>Добро пожаловать в Polymarket Tracker!</b>\n\n"
        text += "<b>Как работает бот:</b>\n"
        text += "📊 <b>Отслеживание портфеля</b>\n"
        text += "• Добавляйте кошельки для мониторинга позиций\n"
        text += "• Получайте актуальную информацию о стоимости\n"
        text += "• Анализируйте прибыль и убытки\n\n"
        
        text += "🔔 <b>Уведомления</b>\n"
        text += "• Изменения портфеля более 10% или $100\n"
        text += "• Крупные сделки китов (более $1000)\n"
        text += "• Новые события на рынке\n\n"
        
        text += "📈 <b>Аналитика</b>\n"
        text += "• Графики распределения активов\n"
        text += "• Топ рынков по объему\n"
        text += "• Анализ волатильности\n\n"
        
        text += "⚙️ <b>Настройки</b>\n"
        text += "• Управление уведомлениями\n"
        text += "• Смена языка\n"
        text += "• Настройки безопасности\n\n"
        
        text += "<b>Быстрый старт:</b>\n"
        text += "1. Нажмите '➕ Мой кошелёк'\n"
        text += "2. Отправьте адрес кошелька (0x...)\n"
        text += "3. Начните отслеживать свои позиции!"
    else:
        text = "👋 <b>Welcome to Polymarket Tracker!</b>\n\n"
        text += "<b>How the bot works:</b>\n"
        text += "📊 <b>Portfolio Tracking</b>\n"
        text += "• Add wallets to monitor positions\n"
        text += "• Get real-time portfolio value\n"
        text += "• Analyze profit and loss\n\n"
        
        text += "🔔 <b>Notifications</b>\n"
        text += "• Portfolio changes over 10% or $100\n"
        text += "• Large whale trades (over $1000)\n"
        text += "• New market events\n\n"
        
        text += "📈 <b>Analytics</b>\n"
        text += "• Asset distribution charts\n"
        text += "• Top markets by volume\n"
        text += "• Volatility analysis\n\n"
        
        text += "⚙️ <b>Settings</b>\n"
        text += "• Notification management\n"
        text += "• Language settings\n"
        text += "• Security settings\n\n"
        
        text += "<b>Quick Start:</b>\n"
        text += "1. Click '➕ My Wallet'\n"
        text += "2. Send your wallet address (0x...)\n"
        text += "3. Start tracking your positions!"
    
    await callback.message.edit_text(
        text
    )
    
    # Отправляем главное меню как новое сообщение
    if language == "ru":
        text = "👋 <b>Добро пожаловать в Polymarket Tracker!</b>\n\nВыберите раздел из меню ниже 👇"
    else:
        text = "👋 <b>Welcome to Polymarket Tracker!</b>\n\nChoose a section from the menu below 👇"
    
    await callback.message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )
    await callback.answer()


@router.message(F.text.in_(["⬅️ Назад", "⬅️ Back"]))
async def cmd_back(message: Message, db: Database):
    """Обработка кнопки Назад"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "Главное меню"
    else:
        text = "Main menu"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )


@router.callback_query(F.data == "back_to_menu")
async def cb_back_to_menu(callback: CallbackQuery, db: Database):
    """Обработка кнопки Назад из инлайн-клавиатуры"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "👋 <b>Добро пожаловать в Polymarket Tracker!</b>\n\nВыберите раздел из меню ниже 👇"
    else:
        text = "👋 <b>Welcome to Polymarket Tracker!</b>\n\nChoose a section from the menu below 👇"
    
    await callback.message.edit_text(
        text,
        reply_markup=None
    )
    
    await callback.message.answer(
        text,
        reply_markup=Keyboards.get_main_menu(language)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lang_"))
async def cb_set_language(callback: CallbackQuery, db: Database):
    """Обработка выбора языка из настроек"""
    language = callback.data.split("_")[1]
    await db.set_user_language(callback.from_user.id, language)
    
    if language == "ru":
        text = "✅ Язык изменен на русский"
    else:
        text = "✅ Language changed to English"
    
    await callback.message.edit_text(text)
    await callback.answer(text)


@router.message(F.text.contains("👛 Кошельки") | F.text.contains("👛 Wallets"))
async def show_wallets_menu(message: Message, db: Database):
    """Показывает меню кошельков"""
    user_id = message.from_user.id
    language = await db.get_user_language(user_id)
    
    keyboard = Keyboards.get_wallets_menu(language)
    
    if language == "ru":
        text = "👛 <b>Управление кошельками</b>\n\nВыберите действие:"
    else:
        text = "👛 <b>Wallet Management</b>\n\nChoose an action:"
    
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text.contains("📊 Отчеты") | F.text.contains("📊 Reports"))
async def show_reports_menu(message: Message, db: Database):
    """Показывает меню отчетов"""
    user_id = message.from_user.id
    language = await db.get_user_language(user_id)
    
    keyboard = Keyboards.get_reports_menu(language)
    
    if language == "ru":
        text = "📊 <b>Отчеты и аналитика</b>\n\nВыберите тип отчета:"
    else:
        text = "📊 <b>Reports & Analytics</b>\n\nChoose report type:"
    
    await message.answer(text, reply_markup=keyboard)


@router.message(F.text.contains("⚙️ Настройки") | F.text.contains("⚙️ Settings"))
async def show_settings_menu(message: Message, db: Database):
    """Показывает меню настроек"""
    user_id = message.from_user.id
    language = await db.get_user_language(user_id)
    
    keyboard = Keyboards.get_settings_menu_updated(language)
    
    if language == "ru":
        text = "⚙️ <b>Настройки</b>\n\nВыберите настройку:"
    else:
        text = "⚙️ <b>Settings</b>\n\nChoose a setting:"
    
    await message.answer(text, reply_markup=keyboard)
