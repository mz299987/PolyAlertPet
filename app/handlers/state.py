from typing import List, Dict, Any

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from app import core
from app.db import ensure_user, get_user_lang
from app.keyboards import main_menu_keyboard, get_main_text
from app.polymarket import pm_get_positions, pm_get_value, pm_get_active_markets

dp = core.dp


async def show_wallet_state(
    msg: Message,
    tg_user_id: int,
    page: int = 0,
    edit: bool = False,
):
    """Показывает состояние одного кошелька с пагинацией по кошелькам."""
    assert core.db_pool is not None

    lang = await get_user_lang(core.db_pool, tg_user_id)

    async with core.db_pool.acquire() as conn:
        wallets = await conn.fetch(
            """
            SELECT id, address, label, is_whale
            FROM wallets
            WHERE tg_user_id=$1
            ORDER BY is_whale, created_at
            """,
            tg_user_id,
        )

    if not wallets:
        if lang == "ru":
            text = (
                "У тебя пока нет кошельков.\n"
                "Нажми «➕ Мой кошелёк» или «➕ Кит» и отправь ссылку на профиль Polymarket."
            )
        else:
            text = (
                "You don't have any wallets yet.\n"
                "Press “➕ My wallet” or “➕ Whale” and send a Polymarket profile link."
            )
        if edit:
            await msg.edit_text(text)
        else:
            await msg.answer(text, reply_markup=main_menu_keyboard(lang))
        return

    n = len(wallets)
    page = page % n
    w = wallets[page]
    address = w["address"]
    label = w["label"]
    is_whale = w["is_whale"]
    icon = "🐳" if is_whale else "👤"

    account_name = label or f"{address[:6]}...{address[-4:]}"

    try:
        positions = await pm_get_positions(address)
    except Exception:
        positions = []

    try:
        portfolio_value = await pm_get_value(address)
    except Exception:
        portfolio_value = None

    try:
        active_markets = await pm_get_active_markets(address)
    except Exception:
        active_markets = []

    active_positions = positions
    active_count = len(active_positions)

    total_pnl = 0.0
    for p in active_positions:
        try:
            total_pnl += float(p.get("cashPnl") or 0.0)
        except Exception:
            pass

    portfolio_str = f"{portfolio_value:.2f} USDC" if portfolio_value is not None else "n/a"
    sign_pnl = "+" if total_pnl >= 0 else ""
    pnl_str = f"{sign_pnl}{total_pnl:.2f} USDC"

    lines: List[str] = []

    if lang == "ru":
        lines.append(f"{icon} Кошелёк {page + 1}/{n}\n")
        lines.append(f"Имя аккаунта: <b>{account_name}</b>")
        lines.append(f"Адрес: <code>{address}</code>")
        lines.append(f"Количество активных позиций: {active_count}")
        lines.append(f"Portfolio: <b>{portfolio_str}</b>")
        lines.append(f"Profit/Loss: <b>{pnl_str}</b>\n")
        
        # Открытые позиции
        if active_positions:
            lines.append("Открытые позиции:")
            for p in active_positions:
                title = p.get("title") or p.get("marketTitle") or "Без названия"
                outcome = p.get("outcome") or "?"
                value_raw = p.get("value") or p.get("positionValue") or p.get("positionValueUsd")
                try:
                    value_f = float(value_raw) if value_raw is not None else 0.0
                except Exception:
                    value_f = 0.0

                cash_raw = p.get("cashPnl")
                pct_raw = p.get("percentPnl")
                try:
                    cash_f = float(cash_raw) if cash_raw is not None else 0.0
                except Exception:
                    cash_f = 0.0
                try:
                    pct_f = float(pct_raw) if pct_raw is not None else 0.0
                except Exception:
                    pct_f = 0.0

                sign_cash = "+" if cash_f >= 0 else ""
                sign_pct = "+" if pct_f >= 0 else ""

                line = (
                    f"{title} - {outcome} value {value_f:.2f} USDC "
                    f"({sign_cash}{cash_f:.2f}$) - {sign_pct}{pct_f:.2f}%"
                )
                lines.append(line)
        else:
            lines.append("Открытых позиций нет.")
        
        lines.append("")
        
        # Активные события
        if active_markets:
            lines.append("Активные события:")
            for market in active_markets:
                market_title = market.get("title", "Без названия")
                positions_count = len(market.get("positions", []))
                lines.append(f"• {market_title} ({positions_count} позиций)")
        else:
            lines.append("Активных событий нет.")
    else:
        lines.append(f"{icon} Wallet {page + 1}/{n}\n")
        lines.append(f"Account name: <b>{account_name}</b>")
        lines.append(f"Address: <code>{address}</code>")
        lines.append(f"Active positions: {active_count}")
        lines.append(f"Portfolio: <b>{portfolio_str}</b>")
        lines.append(f"Profit/Loss: <b>{pnl_str}</b>\n")
        
        # Open positions
        if active_positions:
            lines.append("Open positions:")
            for p in active_positions:
                title = p.get("title") or p.get("marketTitle") or "Untitled market"
                outcome = p.get("outcome") or "?"
                value_raw = p.get("value") or p.get("positionValue") or p.get("positionValueUsd")
                try:
                    value_f = float(value_raw) if value_raw is not None else 0.0
                except Exception:
                    value_f = 0.0

                cash_raw = p.get("cashPnl")
                pct_raw = p.get("percentPnl")
                try:
                    cash_f = float(cash_raw) if cash_raw is not None else 0.0
                except Exception:
                    cash_f = 0.0
                try:
                    pct_f = float(pct_raw) if pct_raw is not None else 0.0
                except Exception:
                    pct_f = 0.0

                sign_cash = "+" if cash_f >= 0 else ""
                sign_pct = "+" if pct_f >= 0 else ""

                line = (
                    f"{title} - {outcome} value {value_f:.2f} USDC "
                    f"({sign_cash}{cash_f:.2f}$) - {sign_pct}{pct_f:.2f}%"
                )
                lines.append(line)
        else:
            lines.append("No open positions.")
        
        lines.append("")
        
        # Active events
        if active_markets:
            lines.append("Active events:")
            for market in active_markets:
                market_title = market.get("title", "Untitled market")
                positions_count = len(market.get("positions", []))
                lines.append(f"• {market_title} ({positions_count} positions)")
        else:
            lines.append("No active events.")

    text = "\n".join(lines)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    next_index = (page + 1) % n
    prev_index = (page - 1) % n
    back_text = "⬅ Назад" if lang == "ru" else "⬅ Back"
    change_wallet_text = "📋 Сменить кошелек" if lang == "ru" else "📋 Change wallet"

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀", callback_data=f"st:{prev_index}"),
                InlineKeyboardButton(text=f"{page + 1}/{n}", callback_data="st_nop"),
                InlineKeyboardButton(text="▶", callback_data=f"st:{next_index}"),
            ],
            [InlineKeyboardButton(text=change_wallet_text, callback_data="st_change_wallet")],
            [InlineKeyboardButton(text=back_text, callback_data="st_back")],
        ]
    )

    if edit:
        await msg.edit_text(text, reply_markup=inline_kb, parse_mode="HTML")
    else:
        await msg.answer(text, reply_markup=inline_kb, parse_mode="HTML")


@dp.message(Command("state"))
async def cmd_state(message: Message):
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    await show_wallet_state(message, message.from_user.id, page=0, edit=False)


@dp.callback_query(F.data == "st_nop")
async def cb_state_nop(callback: CallbackQuery):
    await callback.answer()


@dp.callback_query(F.data == "st_back")
async def cb_state_back(callback: CallbackQuery):
    assert core.db_pool is not None
    lang = await get_user_lang(core.db_pool, callback.from_user.id)
    text = get_main_text(lang)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await core.bot.send_message(  # type: ignore[arg-type]
        callback.message.chat.id,
        text,
        reply_markup=main_menu_keyboard(lang),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("st:"))
async def cb_state_page(callback: CallbackQuery):
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer()
        return

    await show_wallet_state(callback.message, callback.from_user.id, page=page, edit=True)
    await callback.answer()


@dp.callback_query(F.data == "st_change_wallet")
async def cb_change_wallet(callback: CallbackQuery):
    """Обработка кнопки смены кошелька"""
    assert core.db_pool is not None
    
    lang = await get_user_lang(core.db_pool, callback.from_user.id)
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    async with core.db_pool.acquire() as conn:
        wallets = await conn.fetch(
            """
            SELECT id, address, label, is_whale
            FROM wallets
            WHERE tg_user_id=$1
            ORDER BY is_whale, created_at
            """,
            callback.from_user.id,
        )
    
    if not wallets:
        if lang == "ru":
            text = "У тебя нет добавленных кошельков."
        else:
            text = "You don't have any wallets added."
        await callback.answer(text, show_alert=True)
        return
    
    # Создаем кнопки для выбора кошелька
    keyboard = []
    for i, wallet in enumerate(wallets):
        address = wallet["address"]
        label = wallet["label"]
        is_whale = wallet["is_whale"]
        
        icon = "🐳" if is_whale else "👤"
        wallet_name = label or f"{address[:6]}...{address[-4:]}"
        
        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} {wallet_name}", 
                callback_data=f"st_select:{i}"
            )
        ])
    
    # Кнопка назад
    back_text = "⬅ Назад" if lang == "ru" else "⬅ Back"
    keyboard.append([InlineKeyboardButton(text=back_text, callback_data="st_back")])
    
    inline_kb = InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    if lang == "ru":
        text = "Выбери кошелёк для просмотра:"
    else:
        text = "Select a wallet to view:"
    
    await callback.message.edit_text(text, reply_markup=inline_kb)
    await callback.answer()


@dp.callback_query(F.data.startswith("st_select:"))
async def cb_select_wallet(callback: CallbackQuery):
    """Обработка выбора конкретного кошелька"""
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        await callback.answer()
        return

    await show_wallet_state(callback.message, callback.from_user.id, page=page, edit=True)
    await callback.answer()


@dp.message(F.text.in_(["📈 Состояние", "📈 Status"]))
async def btn_state(message: Message):
    await cmd_state(message)
