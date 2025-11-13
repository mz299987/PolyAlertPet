from typing import Dict

from aiogram import F
from aiogram.filters import Command
from aiogram.types import Message

from app import core
from app.db import ensure_user, get_user_lang, save_wallet
from app.keyboards import main_menu_keyboard
from app.polymarket import resolve_wallet_or_profile

dp = core.dp

# режим добавления кошелька по кнопкам:
# user_add_mode[user_id] = "wallet" или "whale"
user_add_mode: Dict[int, str] = {}


@dp.message(Command("add_wallet"))
async def cmd_add_wallet(message: Message):
    """
    /add_wallet address_or_link [label]
    """
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    lang = await get_user_lang(core.db_pool, message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        msg = (
            "Формат: <code>/add_wallet адрес_или_ссылка [label]</code>"
            if lang == "ru"
            else "Format: <code>/add_wallet address_or_link [label]</code>"
        )
        await message.reply(msg, parse_mode="HTML")
        return

    addr_candidate = parts[1]
    label = parts[2] if len(parts) > 2 else None

    address = await resolve_wallet_or_profile(addr_candidate)
    if not address:
        if lang == "ru":
            msg = (
                "Не смог найти 0x-адрес в сообщении.\n"
                "Пришли что-то вроде:\n"
                "<code>/add_wallet https://polymarket.com/@username main</code>\n"
                "или\n"
                "<code>/add_wallet 0x1234...abcd main</code>"
            )
        else:
            msg = (
                "Could not find 0x address in message.\n"
                "Send something like:\n"
                "<code>/add_wallet https://polymarket.com/@username main</code>\n"
                "or\n"
                "<code>/add_wallet 0x1234...abcd main</code>"
            )
        await message.reply(msg, parse_mode="HTML")
        return

    status = await save_wallet(core.db_pool, message.from_user.id, address, label, is_whale=False)

    if status == "exists":
        msg = "Этот кошелёк уже добавлен 👍" if lang == "ru" else "This wallet is already added 👍"
    else:
        msg = (
            f"Кошелёк <code>{address}</code> добавлен ✅"
            if lang == "ru"
            else f"Wallet <code>{address}</code> added ✅"
        )
    await message.reply(msg, parse_mode="HTML")


@dp.message(Command("add_whale"))
async def cmd_add_whale(message: Message):
    """
    /add_whale address_or_link [label]
    """
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    lang = await get_user_lang(core.db_pool, message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        msg = (
            "Формат: <code>/add_whale адрес_или_ссылка [label]</code>"
            if lang == "ru"
            else "Format: <code>/add_whale address_or_link [label]</code>"
        )
        await message.reply(msg, parse_mode="HTML")
        return

    addr_candidate = parts[1]
    label = parts[2] if len(parts) > 2 else None

    address = await resolve_wallet_or_profile(addr_candidate)
    if not address:
        if lang == "ru":
            msg = (
                "Не смог найти 0x-адрес.\n"
                "Пришли ссылку на профиль Polymarket или 0x-адрес.\n"
                "Например:\n"
                "<code>/add_whale https://polymarket.com/@bigwhale MegaWhale</code>"
            )
        else:
            msg = (
                "Could not find 0x address.\n"
                "Send Polymarket profile link or 0x address.\n"
                "For example:\n"
                "<code>/add_whale https://polymarket.com/@bigwhale MegaWhale</code>"
            )
        await message.reply(msg, parse_mode="HTML")
        return

    status = await save_wallet(core.db_pool, message.from_user.id, address, label, is_whale=True)

    if status == "exists":
        msg = "Этот кит уже есть в списке 🐳" if lang == "ru" else "This whale is already in the list 🐳"
    else:
        msg = (
            f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам."
            if lang == "ru"
            else f"Whale <code>{address}</code> added 🐳, I'll send alerts about its trades."
        )
    await message.reply(msg, parse_mode="HTML")


@dp.message(Command("wallets"))
async def cmd_wallets(message: Message):
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    lang = await get_user_lang(core.db_pool, message.from_user.id)

    async with core.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, address, label, is_whale, alerts_enabled, whale_alerts_enabled
            FROM wallets
            WHERE tg_user_id=$1
            ORDER BY created_at
            """,
            message.from_user.id,
        )

    if not rows:
        msg = (
            "У тебя ещё нет кошельков.\n"
            "Нажми «➕ Мой кошелёк» или «➕ Кит» и отправь ссылку на профиль Polymarket."
            if lang == "ru"
            else "You don't have any wallets yet.\n"
                 "Press “➕ My wallet” or “➕ Whale” and send your Polymarket profile link."
        )
        await message.reply(msg)
        return

    lines = []
    for r in rows:
        kind = "🐳" if r["is_whale"] else "👤"
        flags = []
        if r["alerts_enabled"] and not r["is_whale"]:
            flags.append("price-alerts:on")
        if r["whale_alerts_enabled"] and r["is_whale"]:
            flags.append("whale-alerts:on")
        flags_text = ", ".join(flags) if flags else "no alerts"
        label = f" ({r['label']})" if r["label"] else ""
        lines.append(f"{kind} <code>{r['address']}</code>{label} — {flags_text}")

    await message.reply("\n".join(lines), parse_mode="HTML")


# кнопки

@dp.message(F.text.in_(["➕ Мой кошелёк", "➕ My wallet"]))
async def btn_my_wallet(message: Message):
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    lang = await get_user_lang(core.db_pool, message.from_user.id)
    user_add_mode[message.from_user.id] = "wallet"

    if lang == "ru":
        text = (
            "Ок, добавляем твой кошелёк 👤\n\n"
            "Пришли ссылку на профиль Polymarket или 0x-адрес.\n"
            "Поддерживаю форматы:\n"
            "• https://polymarket.com/@username\n"
            "• https://polymarket.com/profile/...\n"
            "• https://polymarket.com/wallet/0x...\n"
            "• просто 0x-адрес"
        )
    else:
        text = (
            "Okay, let's add your wallet 👤\n\n"
            "Send a Polymarket profile link or 0x address.\n"
            "Supported formats:\n"
            "• https://polymarket.com/@username\n"
            "• https://polymarket.com/profile/...\n"
            "• https://polymarket.com/wallet/0x...\n"
            "• plain 0x address"
        )

    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.in_(["➕ Кит", "➕ Whale"]))
async def btn_whale(message: Message):
    assert core.db_pool is not None
    await ensure_user(core.db_pool, message.from_user.id)
    lang = await get_user_lang(core.db_pool, message.from_user.id)
    user_add_mode[message.from_user.id] = "whale"

    if lang == "ru":
        text = (
            "Ок, добавляем кита 🐳\n\n"
            "Пришли ссылку на профиль Polymarket этого кита или его 0x-адрес."
        )
    else:
        text = (
            "Okay, let's add a whale 🐳\n\n"
            "Send this whale's Polymarket profile link or its 0x address."
        )

    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@dp.message(F.text.in_(["📊 Мои кошельки", "📊 My wallets"]))
async def btn_wallets(message: Message):
    await cmd_wallets(message)


@dp.message(F.text)
async def handle_free_text(message: Message):
    """
    Если юзер в режиме добавления кошелька/кита — резолвим ссылку.
    Иначе даём подсказку.
    """
    if (message.text or "").startswith("/"):
        return

    assert core.db_pool is not None
    lang = await get_user_lang(core.db_pool, message.from_user.id)
    mode = user_add_mode.get(message.from_user.id)

    if mode not in ("wallet", "whale"):
        if lang == "ru":
            text = (
                "Если хочешь добавить кошелёк, нажми «➕ Мой кошелёк» или «➕ Кит», "
                "а потом отправь ссылку на профиль Polymarket или 0x-адрес 😉"
            )
        else:
            text = (
                "If you want to add a wallet, press “➕ My wallet” or “➕ Whale”, "
                "then send a Polymarket profile link or 0x address 😉"
            )
        await message.answer(text, reply_markup=main_menu_keyboard(lang))
        return

    address = await resolve_wallet_or_profile(message.text or "")
    if not address:
        if lang == "ru":
            text = (
                "Не смог найти 0x-адрес в этом сообщении 😔\n"
                "Отправь ещё раз ссылку на профиль Polymarket или чистый 0x-адрес."
            )
        else:
            text = (
                "Could not find 0x address in this message 😔\n"
                "Send the Polymarket profile link or plain 0x address again."
            )
        await message.answer(text, reply_markup=main_menu_keyboard(lang))
        return

    label = None
    is_whale = mode == "whale"
    status = await save_wallet(core.db_pool, message.from_user.id, address, label, is_whale=is_whale)

    if is_whale:
        if status == "exists":
            text = "Этот кит уже есть в списке 🐳" if lang == "ru" else "This whale is already in the list 🐳"
        else:
            text = (
                f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам."
                if lang == "ru"
                else f"Whale <code>{address}</code> added 🐳, I'll send alerts about its trades."
            )
    else:
        if status == "exists":
            text = "Этот кошелёк уже добавлен как твой 👍" if lang == "ru" else "This wallet is already added 👍"
        else:
            text = (
                f"Кошелёк <code>{address}</code> добавлен ✅"
                if lang == "ru"
                else f"Wallet <code>{address}</code> added ✅"
            )

    await message.answer(text, parse_mode="HTML", reply_markup=main_menu_keyboard(lang))
    user_add_mode.pop(message.from_user.id, None)
