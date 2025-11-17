from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.keyboards import Keyboards

router = Router()


@router.message(F.text.in_(["➕ Мой кошелёк", "➕ My Wallet"]))
async def cmd_add_wallet(message: Message, db: Database):
    """Добавление обычного кошелька"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = (
            "📥 Добавление кошелька\n\n"
            "Отправьте адрес кошелька (0x...) или ссылку на профиль Polymarket.\n"
            "Примеры:\n"
            "• 0x742d35Cc6634C0532925a3b8DfB8b8B8B8B8B8B8\n"
            "• https://polymarket.com/@username"
        )
    else:
        text = (
            "📥 Add Wallet\n\n"
            "Send wallet address (0x...) or Polymarket profile link.\n"
            "Examples:\n"
            "• 0x742d35Cc6634C0532925a3b8DfB8b8B8B8B8B8B8\n"
            "• https://polymarket.com/@username"
        )
    
    await message.answer(text)


@router.message(F.text.in_(["➕ Кит", "➕ Whale"]))
async def cmd_add_whale(message: Message, db: Database):
    """Добавление кошелька кита"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = (
            "🐳 Добавление кита\n\n"
            "Отправьте адрес кошелька кита (0x...) или ссылку на профиль.\n"
            "Вы будете получать уведомления о сделках кита."
        )
    else:
        text = (
            "🐳 Add Whale\n\n"
            "Send whale wallet address (0x...) or profile link.\n"
            "You'll receive notifications about whale trades."
        )
    
    await message.answer(text)


@router.message(F.text.in_(["📊 Мои кошельки", "📊 My Wallets"]))
async def cmd_my_wallets(message: Message, db: Database):
    """Показ списка кошельков"""
    wallets = await db.get_user_wallets(message.from_user.id)
    language = await db.get_user_language(message.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "У вас пока нет добавленных кошельков."
        else:
            text = "You don't have any wallets added yet."
        await message.answer(text)
        return
    
    if language == "ru":
        text = "📋 Ваши кошельки:"
    else:
        text = "📋 Your wallets:"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_wallet_list(wallets, language)
    )


@router.message(Command("addwallet"))
async def cmd_add_wallet_text(message: Message, db: Database, polymarket: PolymarketAPI):
    """Обработка текста с адресом кошелька"""
    text = message.text.strip()
    language = await db.get_user_language(message.from_user.id)
    
    # Извлекаем адрес из текста
    address = polymarket.extract_address_from_text(text)
    
    if not address:
        if language == "ru":
            await message.answer("❌ Не удалось распознать адрес кошелька. Попробуйте еще раз.")
        else:
            await message.answer("❌ Could not recognize wallet address. Please try again.")
        return
    
    # Определяем тип кошелька (кит или обычный) по контексту
    is_whale = any(word in text.lower() for word in ["whale", "кит", "whales", "киты"])
    
    # Добавляем кошелек
    success = await db.add_wallet(message.from_user.id, address, is_whale=is_whale)
    
    if success:
        if language == "ru":
            if is_whale:
                await message.answer(f"✅ Кит {address} успешно добавлен!")
            else:
                await message.answer(f"✅ Кошелёк {address} успешно добавлен!")
        else:
            if is_whale:
                await message.answer(f"✅ Whale {address} successfully added!")
            else:
                await message.answer(f"✅ Wallet {address} successfully added!")
    else:
        if language == "ru":
            await message.answer("❌ Ошибка при добавлении кошелька.")
        else:
            await message.answer("❌ Error adding wallet.")


@router.callback_query(F.data.startswith("select_wallet_"))
async def cb_select_wallet(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """Обработка выбора кошелька из списка"""
    wallet_index = int(callback.data.split("_")[-1])
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    if not wallets or wallet_index >= len(wallets):
        await callback.answer("Wallet not found")
        return
    
    wallet = wallets[wallet_index]
    await show_wallet_status(callback, wallet, wallet_index, db, polymarket)


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
        lines.append(f"Portfolio: {portfolio_value:.2f} USDC" if portfolio_value else "Portfolio: n/a")
        
        total_pnl = polymarket.calculate_total_pnl(positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Profit/Loss: {pnl_sign}{total_pnl:.2f} USDC")
        lines.append("")
        
        if positions:
            lines.append("📊 Открытые позиции:")
            for position in positions:
                lines.append(polymarket.format_position_info(position))
        else:
            lines.append("Нет открытых позиций")
        
        lines.append("")
        
        if active_markets:
            lines.append("🎯 Активные события:")
            for market in active_markets:
                lines.append(f"• {market['title']} ({len(market['positions'])} позиций)")
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
            for position in positions:
                lines.append(polymarket.format_position_info(position))
        else:
            lines.append("No open positions")
        
        lines.append("")
        
        if active_markets:
            lines.append("🎯 Active Events:")
            for market in active_markets:
                lines.append(f"• {market['title']} ({len(market['positions'])} positions)")
        else:
            lines.append("No active events")
    
    text = "\n".join(lines)
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_wallet_selection(wallets, wallet_index, language)
    )
    await callback.answer()