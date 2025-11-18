"""
Обработчики для недостающих кнопок и функций
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.keyboards import Keyboards

missing_handlers_router = Router()


# Обработчики для меню ставок
@router.message(F.text.in_(["💰 Ставки", "💰 Betting"]))
async def cmd_betting(message: Message, db: Database):
    """Меню ставок"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "💰 <b>Ставки на Polymarket</b>\n\nВыберите действие:"
    else:
        text = "💰 <b>Polymarket Betting</b>\n\nChoose an action:"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_betting_menu(language)
    )


@router.callback_query(F.data == "place_bet")
async def cb_place_bet(callback: CallbackQuery, db: Database):
    """Сделать ставку"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🎯 <b>Сделать ставку</b>\n\nФункция в разработке. Скоро вы сможете делать ставки напрямую через бота!"
    else:
        text = "🎯 <b>Place Bet</b>\n\nFeature in development. Soon you'll be able to place bets directly through the bot!"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "available_markets")
async def cb_available_markets(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """Доступные рынки"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем доступные рынки (заглушка)
    if language == "ru":
        text = "📊 <b>Доступные рынки</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Данные обновляются каждые 5 минут"
    else:
        text = "📊 <b>Available Markets</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Data updates every 5 minutes"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "bet_history")
async def cb_bet_history(callback: CallbackQuery, db: Database):
    """История ставок"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем историю ставок пользователя
    bets = await db.get_user_bets(callback.from_user.id, limit=5)
    
    if language == "ru":
        text = "📋 <b>История ставок</b>\n\n"
        if bets:
            for i, bet in enumerate(bets, 1):
                text += f"{i}. {bet['market_id'][:20]} - {bet['amount']} USDC - {bet['status']}\n"
        else:
            text += "У вас пока нет ставок."
    else:
        text = "📋 <b>Bet History</b>\n\n"
        if bets:
            for i, bet in enumerate(bets, 1):
                text += f"{i}. {bet['market_id'][:20]} - {bet['amount']} USDC - {bet['status']}\n"
        else:
            text += "You don't have any bets yet."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "my_safe_wallet")
async def cb_my_safe_wallet(callback: CallbackQuery, db: Database):
    """Мой Safe кошелек"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем Safe кошелек пользователя
    safe_wallet = await db.get_user_safe_wallet(callback.from_user.id)
    
    if language == "ru":
        text = "🛡️ <b>Мой Safe кошелек</b>\n\n"
        if safe_wallet:
            text += f"Адрес: {safe_wallet['safe_address']}\n"
            text += f"Оригинальный: {safe_wallet['original_address']}\n"
            text += f"Статус: {'Активен' if safe_wallet['is_active'] else 'Неактивен'}"
        else:
            text += "У вас нет настроенного Safe кошелька.\n"
            text += "Для использования ставок необходимо настроить Safe кошелек."
    else:
        text = "🛡️ <b>My Safe Wallet</b>\n\n"
        if safe_wallet:
            text += f"Address: {safe_wallet['safe_address']}\n"
            text += f"Original: {safe_wallet['original_address']}\n"
            text += f"Status: {'Active' if safe_wallet['is_active'] else 'Inactive'}"
        else:
            text += "You don't have a Safe wallet configured.\n"
            text += "To use betting features, you need to set up a Safe wallet."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


# Обработчики для меню кошельков
@router.callback_query(F.data == "my_wallet")
async def cb_my_wallet(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """Мой кошелек"""
    wallets = await db.get_user_wallets(callback.from_user.id)
    language = await db.get_user_language(callback.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков."
        else:
            text = "❌ You don't have any wallets added."
        await callback.message.edit_text(text)
        return
    
    # Показываем первый кошелек
    await show_wallet_status(callback, wallets[0], 0, db, polymarket)


@router.callback_query(F.data == "whales")
async def cb_whales(callback: CallbackQuery, db: Database):
    """Кошельки китов"""
    language = await db.get_user_language(callback.from_user.id)
    
    # Получаем только кошельки китов
    all_wallets = await db.get_user_wallets(callback.from_user.id)
    whale_wallets = [w for w in all_wallets if w.get('is_whale')]
    
    if language == "ru":
        text = "🐳 <b>Кошельки китов</b>\n\n"
        if whale_wallets:
            text += f"У вас отслеживается {len(whale_wallets)} китов:\n"
            for whale in whale_wallets:
                name = whale['name'] or f"{whale['address'][:6]}...{whale['address'][-4:]}"
                text += f"• {name}\n"
        else:
            text += "У вас нет добавленных китов.\n"
            text += "Добавьте кошельки китов для отслеживания крупных сделок."
    else:
        text = "🐳 <b>Whale Wallets</b>\n\n"
        if whale_wallets:
            text += f"You are tracking {len(whale_wallets)} whales:\n"
            for whale in whale_wallets:
                name = whale['name'] or f"{whale['address'][:6]}...{whale['address'][-4:]}"
                text += f"• {name}\n"
        else:
            text += "You don't have any whales added.\n"
            text += "Add whale wallets to track large trades."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "add_wallet")
async def cb_add_wallet(callback: CallbackQuery, db: Database):
    """Добавить кошелек"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "📥 <b>Добавление кошелька</b>\n\n"
        text += "Отправьте адрес кошелька (0x...) или ссылку на профиль Polymarket.\n"
        text += "Примеры:\n"
        text += "• 0x742d35Cc6634C0532925a3b8DfB8b8B8B8B8B8B8\n"
        text += "• https://polymarket.com/@username"
    else:
        text = "📥 <b>Add Wallet</b>\n\n"
        text += "Send wallet address (0x...) or Polymarket profile link.\n"
        text += "Examples:\n"
        text += "• 0x742d35Cc6634C0532925a3b8DfB8b8B8B8B8B8B8\n"
        text += "• https://polymarket.com/@username"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "delete_wallet")
async def cb_delete_wallet(callback: CallbackQuery, db: Database):
    """Удалить кошелек"""
    language = await db.get_user_language(callback.from_user.id)
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "❌ У вас нет кошельков для удаления."
        else:
            text = "❌ You don't have any wallets to delete."
        await callback.message.edit_text(text)
        return
    
    if language == "ru":
        text = "🗑️ <b>Удаление кошелька</b>\n\n"
        text += "Выберите кошелек для удаления:"
    else:
        text = "🗑️ <b>Delete Wallet</b>\n\n"
        text += "Select wallet to delete:"
    
    # Создаем клавиатуру для выбора кошелька
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    for i, wallet in enumerate(wallets):
        name = wallet['name'] or f"{wallet['address'][:6]}...{wallet['address'][-4:]}"
        buttons.append([
            InlineKeyboardButton(
                text=name,
                callback_data=f"delete_wallet_{wallet['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад" if language == "ru" else "⬅️ Back",
            callback_data="back_to_settings"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delete_wallet_"))
async def cb_confirm_delete_wallet(callback: CallbackQuery, db: Database):
    """Подтверждение удаления кошелька"""
    wallet_id = int(callback.data.split("_")[-1])
    language = await db.get_user_language(callback.from_user.id)
    
    # Удаляем кошелек
    success = await db.delete_wallet(callback.from_user.id, wallet_id)
    
    if success:
        if language == "ru":
            text = "✅ Кошелек успешно удален!"
        else:
            text = "✅ Wallet successfully deleted!"
    else:
        if language == "ru":
            text = "❌ Ошибка при удалении кошелька."
        else:
            text = "❌ Error deleting wallet."
    
    await callback.message.edit_text(text)
    await callback.answer(text)


# Обработчики для настроек
@router.callback_query(F.data == "notification_settings")
async def cb_notification_settings(callback: CallbackQuery, db: Database):
    """Настройки уведомлений"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🔔 <b>Настройки уведомлений</b>\n\n"
        text += "Выберите типы уведомлений которые хотите получать:"
    else:
        text = "🔔 <b>Notification Settings</b>\n\n"
        text += "Select notification types you want to receive:"
    
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
        text += "Выберите предпочитаемый язык:"
    else:
        text = "🌐 <b>Language Settings</b>\n\n"
        text += "Select your preferred language:"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_language_selection()
    )
    await callback.answer()


@router.callback_query(F.data == "security_settings")
async def cb_security_settings(callback: CallbackQuery, db: Database):
    """Настройки безопасности"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "🛡️ <b>Настройки безопасности</b>\n\n"
        text += "• Защита от спама: включена\n"
        text += "• Лимит запросов: 30/мин\n"
        text += "• Шифрование данных: включено"
    else:
        text = "🛡️ <b>Security Settings</b>\n\n"
        text += "• Spam protection: enabled\n"
        text += "• Rate limit: 30/min\n"
        text += "• Data encryption: enabled"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery, db: Database):
    """Помощь"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "ℹ️ <b>Помощь</b>\n\n"
        text += "<b>Основные команды:</b>\n"
        text += "• /start - начать работу\n"
        text += "• /addwallet [адрес] - добавить кошелек\n"
        text += "• /search [запрос] - поиск рынков\n\n"
        text += "<b>Поддержка:</b>\n"
        text += "По вопросам работы бота обращайтесь к администратору."
    else:
        text = "ℹ️ <b>Help</b>\n\n"
        text += "<b>Basic commands:</b>\n"
        text += "• /start - start bot\n"
        text += "• /addwallet [address] - add wallet\n"
        text += "• /search [query] - search markets\n\n"
        text += "<b>Support:</b>\n"
        text += "For bot support contact administrator."
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_to_settings(language)
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_settings")
async def cb_back_to_settings(callback: CallbackQuery, db: Database):
    """Возврат в настройки"""
    language = await db.get_user_language(callback.from_user.id)
    
    if language == "ru":
        text = "⚙️ <b>Настройки</b>\n\nВыберите настройку:"
    else:
        text = "⚙️ <b>Settings</b>\n\nChoose a setting:"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_settings_menu_updated(language)
    )
    await callback.answer()


# Вспомогательная функция для показа статуса кошелька
async def show_wallet_status(callback: CallbackQuery, wallet: dict, wallet_index: int, db: Database, polymarket: PolymarketAPI):
    """Показывает статус кошелька"""
    language = await db.get_user_language(callback.from_user.id)
    address = wallet["address"]
    
    # Получаем данные с Polymarket
    positions = await polymarket.get_wallet_positions(address)
    portfolio_value = await polymarket.get_wallet_value(address)
    active_markets = await polymarket.get_active_markets(address)
    
    # Формируем текст
    wallet_name = wallet["name"] or f"{address[:6]}...{address[-4:]}"
    icon = "🐳" if wallet["is_whale"] else "👤"
    
    if language == "ru":
        lines = [f"{icon} Кошелёк: {wallet_name}"]
        lines.append(f"Адрес: {address}")
        lines.append(f"Активных позиций: {len(positions)}")
        lines.append(f"Портфель: {portfolio_value:.2f} USDC" if portfolio_value else "Портфель: недоступно")
        
        total_pnl = polymarket.calculate_total_pnl(positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Прибыль/Убыток: {pnl_sign}{total_pnl:.2f} USDC")
        lines.append("")
        
        if positions:
            lines.append("📊 Открытые позиции:")
            for position in positions[:5]:  # Показываем только первые 5
                lines.append(polymarket.format_position_info(position))
            if len(positions) > 5:
                lines.append(f"... и еще {len(positions) - 5} позиций")
        else:
            lines.append("Нет открытых позиций")
        
        lines.append("")
        
        if active_markets:
            lines.append("🎯 Активные события:")
            for market in active_markets[:3]:  # Показываем только первые 3
                lines.append(f"• {market['title']} ({len(market['positions'])} позиций)")
            if len(active_markets) > 3:
                lines.append(f"... и еще {len(active_markets) - 3} событий")
        else:
            lines.append("Нет активных событий")
    else:
        lines = [f"{icon} Wallet: {wallet_name}"]
        lines.append(f"Address: {address}")
        lines.append(f"Active positions: {len(positions)}")
        lines.append(f"Portfolio: {portfolio_value:.2f} USDC" if portfolio_value else "Portfolio: n/a")
        
        total_pnl = polymarket.calculate_total_pnl(positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Profit/Loss: {pnl_sign}{total_pnl:.2f} USDC")
        lines.append("")
        
        if positions:
            lines.append("📊 Open Positions:")
            for position in positions[:5]:
                lines.append(polymarket.format_position_info(position))
            if len(positions) > 5:
                lines.append(f"... and {len(positions) - 5} more positions")
        else:
            lines.append("No open positions")
        
        lines.append("")
        
        if active_markets:
            lines.append("🎯 Active Events:")
            for market in active_markets[:3]:
                lines.append(f"• {market['title']} ({len(market['positions'])} positions)")
            if len(active_markets) > 3:
                lines.append(f"... and {len(active_markets) - 3} more events")
        else:
            lines.append("No active events")
    
    text = "\n".join(lines)
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_wallet_selection([wallet], wallet_index, language)
    )
    await callback.answer()
