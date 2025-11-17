from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.keyboards import Keyboards

router = Router()


@router.message(F.text.in_(["📈 Состояние", "📈 Status"]))
async def cmd_status(message: Message, db: Database, polymarket: PolymarketAPI):
    """Показ состояния портфеля"""
    wallets = await db.get_user_wallets(message.from_user.id)
    language = await db.get_user_language(message.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "У вас пока нет добавленных кошельков."
        else:
            text = "You don't have any wallets added yet."
        await message.answer(text)
        return
    
    # Показываем первый кошелек
    await show_wallet_status_message(message, wallets[0], 0, db, polymarket)


@router.callback_query(F.data.startswith("wallet_"))
async def cb_change_wallet(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """Смена кошелька (навигация)"""
    wallet_index = int(callback.data.split("_")[1])
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    if not wallets or wallet_index >= len(wallets):
        await callback.answer("Wallet not found")
        return
    
    wallet = wallets[wallet_index]
    await show_wallet_status_callback(callback, wallet, wallet_index, db, polymarket)


@router.callback_query(F.data == "change_wallet")
async def cb_select_wallet_menu(callback: CallbackQuery, db: Database):
    """Показ меню выбора кошелька"""
    wallets = await db.get_user_wallets(callback.from_user.id)
    language = await db.get_user_language(callback.from_user.id)
    
    if not wallets:
        await callback.answer("No wallets")
        return
    
    if language == "ru":
        text = "📋 Выберите кошелёк:"
    else:
        text = "📋 Select a wallet:"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_wallet_list(wallets, language)
    )
    await callback.answer()


async def show_wallet_status_message(message: Message, wallet: dict, wallet_index: int, db: Database, polymarket: PolymarketAPI):
    """Показывает статус кошелька для сообщения"""
    language = await db.get_user_language(message.from_user.id)
    wallets = await db.get_user_wallets(message.from_user.id)
    
    text = await generate_wallet_status_text(wallet, language, polymarket)
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_wallet_selection(wallets, wallet_index, language)
    )


async def show_wallet_status_callback(callback: CallbackQuery, wallet: dict, wallet_index: int, db: Database, polymarket: PolymarketAPI):
    """Показывает статус кошелька для callback"""
    language = await db.get_user_language(callback.from_user.id)
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    text = await generate_wallet_status_text(wallet, language, polymarket)
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_wallet_selection(wallets, wallet_index, language)
    )
    await callback.answer()


async def generate_wallet_status_text(wallet: dict, language: str, polymarket: PolymarketAPI) -> str:
    """Генерирует текст статуса кошелька"""
    address = wallet["address"]
    
    # Получаем данные с Polymarket
    positions = await polymarket.get_wallet_positions(address)
    portfolio_value = await polymarket.get_wallet_value(address)
    active_markets = await polymarket.get_active_markets(address)
    
    # Форматируем данные
    wallet_name = wallet["name"] or f"{address[:6]}...{address[-4:]}"
    icon = "🐳" if wallet["is_whale"] else "👤"
    
    if language == "ru":
        lines = [f"{icon} <b>Кошелёк: {wallet_name}</b>"]
        lines.append(f"Адрес: <code>{address}</code>")
        lines.append(f"Количество активных позиций: <b>{len(positions)}</b>")
        
        if portfolio_value is not None:
            lines.append(f"Portfolio: <b>{portfolio_value:.2f} USDC</b>")
        else:
            lines.append("Portfolio: <b>n/a</b>")
        
        total_pnl = polymarket.calculate_total_pnl(positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Profit/Loss: <b>{pnl_sign}{total_pnl:.2f} USDC</b>")
        lines.append("")
        
        if positions:
            lines.append("<b>📊 Открытые позиции:</b>")
            for i, position in enumerate(positions[:10]):  # Ограничиваем для читаемости
                lines.append(polymarket.format_position_info(position))
            if len(positions) > 10:
                lines.append(f"... и еще {len(positions) - 10} позиций")
        else:
            lines.append("<i>Нет открытых позиций</i>")
        
        lines.append("")
        
        if active_markets:
            lines.append("<b>🎯 Активные события:</b>")
            for market in active_markets[:5]:  # Ограничиваем для читаемости
                lines.append(f"• {market['title']} ({len(market['positions'])} позиций)")
            if len(active_markets) > 5:
                lines.append(f"... и еще {len(active_markets) - 5} событий")
        else:
            lines.append("<i>Нет активных событий</i>")
    else:
        lines = [f"{icon} <b>Wallet: {wallet_name}</b>"]
        lines.append(f"Address: <code>{address}</code>")
        lines.append(f"Active positions: <b>{len(positions)}</b>")
        
        if portfolio_value is not None:
            lines.append(f"Portfolio: <b>{portfolio_value:.2f} USDC</b>")
        else:
            lines.append("Portfolio: <b>n/a</b>")
        
        total_pnl = polymarket.calculate_total_pnl(positions)
        pnl_sign = "+" if total_pnl >= 0 else ""
        lines.append(f"Profit/Loss: <b>{pnl_sign}{total_pnl:.2f} USDC</b>")
        lines.append("")
        
        if positions:
            lines.append("<b>📊 Open Positions:</b>")
            for i, position in enumerate(positions[:10]):
                lines.append(polymarket.format_position_info(position))
            if len(positions) > 10:
                lines.append(f"... and {len(positions) - 10} more positions")
        else:
            lines.append("<i>No open positions</i>")
        
        lines.append("")
        
        if active_markets:
            lines.append("<b>🎯 Active Events:</b>")
            for market in active_markets[:5]:
                lines.append(f"• {market['title']} ({len(market['positions'])} positions)")
            if len(active_markets) > 5:
                lines.append(f"... and {len(active_markets) - 5} more events")
        else:
            lines.append("<i>No active events</i>")
    
    return "\n".join(lines)