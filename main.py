import os
import re
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

import asyncpg
import httpx
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
)
from aiogram.client.default import DefaultBotProperties

# =========================
# Конфиг
# =========================

@dataclass
class Config:
    bot_token: str
    database_url: str
    alert_threshold_percent: float = 5.0
    poll_interval_seconds: int = 60          # как часто чекать свои кошельки
    whale_poll_interval_seconds: int = 60    # как часто чекать китов

    @classmethod
    def from_env(cls) -> "Config":
        token = os.getenv("BOT_TOKEN")
        db_url = os.getenv("DATABASE_URL")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set")
        if not db_url:
            raise RuntimeError("DATABASE_URL is not set")

        alert = float(os.getenv("ALERT_THRESHOLD_PERCENT", "5.0"))
        poll = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
        whale_poll = int(os.getenv("WHALE_POLL_INTERVAL_SECONDS", "60"))
        return cls(
            bot_token=token,
            database_url=db_url,
            alert_threshold_percent=alert,
            poll_interval_seconds=poll,
            whale_poll_interval_seconds=whale_poll,
        )


# =========================
# Глобальные объекты
# =========================

config: Optional[Config] = None
bot: Optional[Bot] = None
dp: Dispatcher = Dispatcher()
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

DATA_API_BASE = "https://data-api.polymarket.com"

LANG_DEFAULT = "en"

# режим добавления кошелька по кнопкам:
# user_add_mode[user_id] = "wallet" или "whale"
user_add_mode: Dict[int, str] = {}

WALLET_REGEX = re.compile(r"0x[a-fA-F0-9]{40}", re.IGNORECASE)

ALTER_TG_USERS_LANG_SQL = "ALTER TABLE tg_users ADD COLUMN IF NOT EXISTS lang TEXT;"

# =========================
# Утилиты
# =========================

def extract_wallet_address(text: str) -> Optional[str]:
    """
    Вытаскиваем 0x-адрес из произвольного текста / ссылки.
    """
    if not text:
        return None
    m = WALLET_REGEX.search(text)
    return m.group(0) if m else None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def language_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru")],
        ]
    )


def main_menu_keyboard(lang: str) -> ReplyKeyboardMarkup:
    """
    Основная клавиатура под полем ввода.
    """
    if lang == "ru":
        keyboard = [
            [
                KeyboardButton(text="➕ Мой кошелёк"),
                KeyboardButton(text="➕ Кит"),
            ],
            [
                KeyboardButton(text="📊 Мои кошельки"),
                KeyboardButton(text="📈 Состояние"),
            ],
            [KeyboardButton(text="⬅ Назад")],
        ]
    else:
        keyboard = [
            [
                KeyboardButton(text="➕ My wallet"),
                KeyboardButton(text="➕ Whale"),
            ],
            [
                KeyboardButton(text="📊 My wallets"),
                KeyboardButton(text="📈 Status"),
            ],
            [KeyboardButton(text="⬅ Back")],
        ]

    kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=keyboard)
    return kb


def get_main_text(lang: str) -> str:
    if lang == "ru":
        return (
            "Привет! Я трекаю твой Polymarket профиль 🧠\n\n"
            "Что я умею:\n"
            "• слать алерты при движении позиций на ±5%\n"
            "• отслеживать китов и их новые сделки\n"
            "• показывать текущее состояние кошелька/китов\n\n"
            "Кнопки внизу:\n"
            "• «➕ Мой кошелёк» — добавить свой профиль Polymarket\n"
            "• «➕ Кит» — добавить кошелёк кита\n"
            "• «📊 Мои кошельки» — список всех\n"
            "• «📈 Состояние» — подробное состояние кошельков\n"
        )
    else:
        return (
            "Hi! I track your Polymarket profile 🧠\n\n"
            "What I can do:\n"
            "• send alerts when your positions move ±5%\n"
            "• track whales and their new trades\n"
            "• show current status of your wallets\n\n"
            "Buttons below:\n"
            "• “➕ My wallet” — add your Polymarket profile\n"
            "• “➕ Whale” — add whale wallet\n"
            "• “📊 My wallets” — list of wallets\n"
            "• “📈 Status” — detailed status of wallets\n"
        )


# =========================
# Инициализация БД
# =========================

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS tg_users (
    id BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now(),
    lang TEXT
);

CREATE TABLE IF NOT EXISTS wallets (
    id SERIAL PRIMARY KEY,
    tg_user_id BIGINT REFERENCES tg_users(id) ON DELETE CASCADE,
    address TEXT NOT NULL,
    label TEXT,
    is_whale BOOLEAN NOT NULL DEFAULT FALSE,
    alerts_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    whale_alerts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS position_snapshots (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE,
    condition_id TEXT NOT NULL,
    title TEXT,
    outcome TEXT,
    last_percent_pnl DOUBLE PRECISION,
    last_cur_price DOUBLE PRECISION,
    last_alert_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (wallet_id, condition_id)
);

CREATE TABLE IF NOT EXISTS activity_markers (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE,
    last_seen_timestamp BIGINT
);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id SERIAL PRIMARY KEY,
    wallet_id INTEGER REFERENCES wallets(id) ON DELETE CASCADE,
    taken_at TIMESTAMPTZ NOT NULL,
    total_value NUMERIC NOT NULL
);
"""


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
        # добавляем колонку lang, если её ещё нет
        await conn.execute(ALTER_TG_USERS_LANG_SQL)


async def ensure_user(pool: asyncpg.Pool, tg_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tg_users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            tg_id,
        )


async def get_user_lang(user_id: int) -> str:
    assert db_pool is not None
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT lang FROM tg_users WHERE id=$1", user_id)
    lang = row["lang"] if row and row["lang"] else None
    return lang or LANG_DEFAULT


async def set_user_lang(user_id: int, lang: str) -> None:
    assert db_pool is not None
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET lang=$1 WHERE id=$2",
            lang,
            user_id,
        )


# =========================
# Polymarket Data-API client
# =========================

async def pm_get_positions(address: str) -> List[Dict[str, Any]]:
    """
    GET /positions?user=...
    Возвращает список позиций с PnL, ценой, названием рынка и т.д.
    """
    assert http_client is not None
    resp = await http_client.get(
        f"{DATA_API_BASE}/positions",
        params={"user": address, "sizeThreshold": 0},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


async def pm_get_value(address: str) -> Optional[float]:
    """
    GET /value?user=...
    Общая стоимость позиций по кошельку.
    """
    assert http_client is not None
    resp = await http_client.get(
        f"{DATA_API_BASE}/value",
        params={"user": address},
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data:
        return float(data[0].get("value", 0.0))
    return None


async def pm_get_activity_trades(address: str, since_ts: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    GET /activity?user=...&type=TRADE
    История ончейн-активности, тут берём только сделки (TRADE).
    """
    assert http_client is not None
    params: Dict[str, Any] = {
        "user": address,
        "limit": 100,
        "type": "TRADE",
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC",
    }
    resp = await http_client.get(
        f"{DATA_API_BASE}/activity",
        params=params,
        timeout=20.0,
    )
    resp.raise_for_status()
    trades = resp.json()
    if since_ts is None:
        return trades
    return [t for t in trades if int(t.get("timestamp", 0)) > since_ts]


# =========================
# Резолв ссылки / текста в 0x-кошелёк
# =========================

async def resolve_wallet_or_profile(text: str) -> Optional[str]:
    """
    Понимает:
    - голый 0x-адрес
    - ссылку с 0x-адресом (polymarket.com/wallet/0x..., profile/...)
    - ссылку вида polymarket.com/@username (вытаскиваем адрес со страницы)
    """
    if not text:
        return None

    # 1) если прямо есть 0x-адрес — берём его
    addr = extract_wallet_address(text)
    if addr:
        return addr

    # 2) ищем ссылку вида polymarket.com/@username
    m = re.search(
        r"(https?://)?(www\.)?polymarket\.com/@([A-Za-z0-9_\-\.]+)",
        text,
    )
    if not m:
        return None

    url = m.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    assert http_client is not None
    try:
        resp = await http_client.get(url, timeout=20.0)
        resp.raise_for_status()
        html = resp.text
        addr_from_html = extract_wallet_address(html)
        return addr_from_html
    except Exception:
        return None


# =========================
# Хэлперы для работы с wallets в БД
# =========================

async def save_wallet(
    tg_user_id: int,
    address: str,
    label: Optional[str],
    is_whale: bool,
) -> str:
    """
    Добавляет кошелёк или кита в БД.
    Возвращает строку-статус: "exists", "wallet_added", "whale_added".
    """
    assert db_pool is not None
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM wallets
            WHERE tg_user_id=$1 AND address=$2 AND is_whale=$3
            """,
            tg_user_id,
            address,
            is_whale,
        )
        if row:
            return "exists"

        if is_whale:
            w_id = await conn.fetchval(
                """
                INSERT INTO wallets (tg_user_id, address, label, is_whale, whale_alerts_enabled)
                VALUES ($1, $2, $3, TRUE, TRUE)
                RETURNING id
                """,
                tg_user_id,
                address,
                label,
            )
            # инициализируем маркер активности
            await conn.execute(
                "INSERT INTO activity_markers (wallet_id, last_seen_timestamp) VALUES ($1, $2)",
                w_id,
                0,
            )
            return "whale_added"
        else:
            await conn.execute(
                """
                INSERT INTO wallets (tg_user_id, address, label, is_whale, alerts_enabled)
                VALUES ($1, $2, $3, FALSE, TRUE)
                """,
                tg_user_id,
                address,
                label,
            )
            return "wallet_added"


# =========================
# Хэндлеры Telegram
# =========================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    # проверяем, выбран ли язык
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT lang FROM tg_users WHERE id=$1", message.from_user.id)
    lang = row["lang"] if row and row["lang"] else None

    if not lang:
        await message.answer(
            "Choose your language / Выберите язык",
            reply_markup=language_inline_keyboard(),
        )
        return

    text = get_main_text(lang)
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@dp.callback_query(F.data.startswith("set_lang:"))
async def cb_set_lang(callback: CallbackQuery):
    lang = callback.data.split(":", 1)[1]
    if lang not in ("en", "ru"):
        await callback.answer()
        return

    await set_user_lang(callback.from_user.id, lang)
    text = get_main_text(lang)
    kb = main_menu_keyboard(lang)

    try:
        await callback.message.edit_text(
            "✅ Language set" if lang == "en" else "✅ Язык сохранён"
        )
    except Exception:
        pass

    await bot.send_message(callback.message.chat.id, text, reply_markup=kb)
    await callback.answer("OK")


@dp.message(F.text.in_(["⬅ Back", "⬅ Назад"]))
async def btn_back(message: Message):
    lang = await get_user_lang(message.from_user.id)
    text = get_main_text(lang)
    await message.answer(text, reply_markup=main_menu_keyboard(lang))


@dp.message(Command("add_wallet"))
async def cmd_add_wallet(message: Message):
    """
    /add_wallet адрес_или_ссылка [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)
    lang = await get_user_lang(message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        if lang == "ru":
            msg = "Формат: <code>/add_wallet адрес_или_ссылка [label]</code>"
        else:
            msg = "Format: <code>/add_wallet address_or_link [label]</code>"
        await message.reply(msg, parse_mode=ParseMode.HTML)
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
        await message.reply(msg, parse_mode=ParseMode.HTML)
        return

    status = await save_wallet(message.from_user.id, address, label, is_whale=False)

    if status == "exists":
        msg = "Этот кошелёк уже добавлен 👍" if lang == "ru" else "This wallet is already added 👍"
    else:
        msg = (
            f"Кошелёк <code>{address}</code> добавлен ✅"
            if lang == "ru"
            else f"Wallet <code>{address}</code> added ✅"
        )

    await message.reply(msg, parse_mode=ParseMode.HTML)


@dp.message(Command("add_whale"))
async def cmd_add_whale(message: Message):
    """
    /add_whale адрес_или_ссылка [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)
    lang = await get_user_lang(message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        if lang == "ru":
            msg = "Формат: <code>/add_whale адрес_или_ссылка [label]</code>"
        else:
            msg = "Format: <code>/add_whale address_or_link [label]</code>"
        await message.reply(msg, parse_mode=ParseMode.HTML)
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
        await message.reply(msg, parse_mode=ParseMode.HTML)
        return

    status = await save_wallet(message.from_user.id, address, label, is_whale=True)

    if status == "exists":
        msg = "Этот кит уже есть в списке 🐳" if lang == "ru" else "This whale is already in the list 🐳"
    else:
        msg = (
            f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам."
            if lang == "ru"
            else f"Whale <code>{address}</code> added 🐳, I'll send alerts about its trades."
        )

    await message.reply(msg, parse_mode=ParseMode.HTML)


@dp.message(Command("wallets"))
async def cmd_wallets(message: Message):
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)
    lang = await get_user_lang(message.from_user.id)

    async with db_pool.acquire() as conn:
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
        if lang == "ru":
            msg = (
                "У тебя ещё нет кошельков.\n"
                "Нажми «➕ Мой кошелёк» или «➕ Кит» и отправь ссылку на профиль Polymarket."
            )
        else:
            msg = (
                "You don't have any wallets yet.\n"
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

    await message.reply("\n".join(lines), parse_mode=ParseMode.HTML)


# =========================
# STATE / STATUS (по кошелькам)
# =========================

async def show_wallet_state(
    msg: Message,
    tg_user_id: int,
    page: int = 0,
    edit: bool = False,
):
    """Показывает состояние одного кошелька с пагинацией по кошелькам."""
    assert db_pool is not None

    lang = await get_user_lang(tg_user_id)

    async with db_pool.acquire() as conn:
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

    # Имя аккаунта: label или сокращённый адрес
    account_name = label or f"{address[:6]}...{address[-4:]}"

    # тянем данные с Polymarket
    try:
        positions = await pm_get_positions(address)
    except Exception:
        positions = []

    try:
        portfolio_value = await pm_get_value(address)
    except Exception:
        portfolio_value = None

    active_positions = positions  # API отдаёт только активные, считаем их так
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
        if active_positions:
            lines.append("Открытые позиции:")
        else:
            lines.append("Открытых позиций нет.")
    else:
        lines.append(f"{icon} Wallet {page + 1}/{n}\n")
        lines.append(f"Account name: <b>{account_name}</b>")
        lines.append(f"Address: <code>{address}</code>")
        lines.append(f"Active positions: {active_count}")
        lines.append(f"Portfolio: <b>{portfolio_str}</b>")
        lines.append(f"Profit/Loss: <b>{pnl_str}</b>\n")
        if active_positions:
            lines.append("Open positions:")
        else:
            lines.append("No open positions.")

    for p in active_positions:
        title = p.get("title") or ("Без названия" if lang == "ru" else "Untitled market")
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

        # Формат:
        # Maduro out in 2025 - YES value 215 (+15.39$) - 7.69%
        if lang == "ru":
            line = (
                f"{title} - {outcome} value {value_f:.2f} USDC "
                f"({sign_cash}{cash_f:.2f}$) - {sign_pct}{pct_f:.2f}%"
            )
        else:
            line = (
                f"{title} - {outcome} value {value_f:.2f} USDC "
                f"({sign_cash}{cash_f:.2f}$) - {sign_pct}{pct_f:.2f}%"
            )
        lines.append(line)

    text = "\n".join(lines)

    next_index = (page + 1) % n
    prev_index = (page - 1) % n

    back_text = "⬅ Назад" if lang == "ru" else "⬅ Back"

    inline_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="◀", callback_data=f"st:{prev_index}"),
                InlineKeyboardButton(text=f"{page + 1}/{n}", callback_data="st_nop"),
                InlineKeyboardButton(text="▶", callback_data=f"st:{next_index}"),
            ],
            [InlineKeyboardButton(text=back_text, callback_data="st_back")],
        ]
    )

    if edit:
        await msg.edit_text(text, reply_markup=inline_kb, parse_mode=ParseMode.HTML)
    else:
        await msg.answer(text, reply_markup=inline_kb, parse_mode=ParseMode.HTML)


@dp.message(Command("state"))
async def cmd_state(message: Message):
    await ensure_user(db_pool, message.from_user.id)  # type: ignore[arg-type]
    await show_wallet_state(message, message.from_user.id, page=0, edit=False)


@dp.callback_query(F.data == "st_nop")
async def cb_state_nop(callback: CallbackQuery):
    # просто ничего не делаем, чтобы middle button не ругался
    await callback.answer()


@dp.callback_query(F.data == "st_back")
async def cb_state_back(callback: CallbackQuery):
    lang = await get_user_lang(callback.from_user.id)
    text = get_main_text(lang)
    # убираем инлайн-клавиатуру у старого сообщения
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await bot.send_message(callback.message.chat.id, text, reply_markup=main_menu_keyboard(lang))
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


# =========================
# PNL команда (как было)
# =========================

@dp.message(Command("pnl"))
async def cmd_pnl(message: Message):
    """
    /pnl [period]
    period: 1d, 7d, 30d
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)
    lang = await get_user_lang(message.from_user.id)

    parts = (message.text or "").split()
    period_str = parts[1] if len(parts) > 1 else "7d"

    if period_str not in ("1d", "7d", "30d"):
        if lang == "ru":
            msg = "Допустимые периоды: 1d, 7d, 30d\nПример: <code>/pnl 7d</code>"
        else:
            msg = "Allowed periods: 1d, 7d, 30d\nExample: <code>/pnl 7d</code>"
        await message.reply(msg, parse_mode=ParseMode.HTML)
        return

    days = int(period_str[:-1])
    now = now_utc()
    from_time = now - timedelta(days=days)

    async with db_pool.acquire() as conn:
        wallets = await conn.fetch(
            "SELECT id, address, label FROM wallets WHERE tg_user_id=$1 AND is_whale=FALSE",
            message.from_user.id,
        )
        if not wallets:
            msg = (
                "Нет своих кошельков. Добавь через «➕ Мой кошелёк»."
                if lang == "ru"
                else "No personal wallets. Add one via “➕ My wallet”."
            )
            await message.reply(msg)
            return

        text_lines = [f"PNL {period_str}:"]
        for w in wallets:
            wid = w["id"]
            first = await conn.fetchrow(
                """
                SELECT total_value, taken_at
                FROM equity_snapshots
                WHERE wallet_id=$1 AND taken_at >= $2
                ORDER BY taken_at ASC
                LIMIT 1
                """,
                wid,
                from_time,
            )
            last = await conn.fetchrow(
                """
                SELECT total_value, taken_at
                FROM equity_snapshots
                WHERE wallet_id=$1
                ORDER BY taken_at DESC
                LIMIT 1
                """,
                wid,
            )
            if not first or not last:
                text_lines.append(
                    f"• <code>{w['address']}</code>: "
                    f"{'недостаточно данных для периода' if lang == 'ru' else 'not enough data for this period'}"
                )
                continue

            start_val = float(first["total_value"])
            end_val = float(last["total_value"])
            delta = end_val - start_val
            pct = (delta / start_val * 100) if start_val != 0 else 0.0

            label = f" ({w['label']})" if w["label"] else ""
            sign = "+" if delta >= 0 else ""
            text_lines.append(
                f"• <code>{w['address']}</code>{label}: "
                f"{sign}{delta:.2f} USDC ({sign}{pct:.2f}%)"
            )

    await message.reply("\n".join(text_lines), parse_mode=ParseMode.HTML)


# =========================
# Кнопки-клавиатура (без команд)
# =========================

@dp.message(F.text.in_(["➕ Мой кошелёк", "➕ My wallet"]))
async def btn_my_wallet(message: Message):
    await ensure_user(db_pool, message.from_user.id)  # type: ignore[arg-type]
    lang = await get_user_lang(message.from_user.id)
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
    await ensure_user(db_pool, message.from_user.id)  # type: ignore[arg-type]
    lang = await get_user_lang(message.from_user.id)
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


@dp.message(F.text.in_(["📈 Состояние", "📈 Status"]))
async def btn_state(message: Message):
    await cmd_state(message)


@dp.message(F.text)
async def handle_free_text(message: Message):
    """
    Обрабатываем свободный текст:
    - если пользователь в режиме добавления кошелька/кита — пытаемся зарезолвить ссылку.
    """
    if (message.text or "").startswith("/"):
        return

    lang = await get_user_lang(message.from_user.id)
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
    status = await save_wallet(message.from_user.id, address, label, is_whale=is_whale)

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

    await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard(lang))
    user_add_mode.pop(message.from_user.id, None)


# =========================
# Фоновые задачи
# =========================

async def monitor_positions():
    """
    Периодически:
    - тянем позиции по каждому своему кошельку
    - сравниваем percentPnl с предыдущим значением
    - если |delta| >= threshold -> шлём алерт
    - сохраняем снапшот equity для PnL
    """
    assert db_pool is not None
    assert config is not None

    while True:
        try:
            async with db_pool.acquire() as conn:
                wallets = await conn.fetch(
                    """
                    SELECT w.id, w.address, w.tg_user_id, w.label
                    FROM wallets w
                    WHERE w.is_whale=FALSE AND w.alerts_enabled=TRUE
                    """
                )

            for w in wallets:
                address = w["address"]
                wallet_id = w["id"]
                tg_id = w["tg_user_id"]
                label = w["label"]

                # Позиции
                try:
                    positions = await pm_get_positions(address)
                except Exception:
                    continue

                # Снапшот equity
                try:
                    total_value = await pm_get_value(address)
                except Exception:
                    total_value = None

                if total_value is not None:
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO equity_snapshots (wallet_id, taken_at, total_value)
                            VALUES ($1, $2, $3)
                            """,
                            wallet_id,
                            now_utc(),
                            total_value,
                        )

                # Проверка позиций
                async with db_pool.acquire() as conn:
                    for p in positions:
                        cond_id = p.get("conditionId")
                        title = p.get("title")
                        outcome = p.get("outcome")
                        cur_pct = p.get("percentPnl")
                        cur_price = p.get("curPrice")

                        if cond_id is None or cur_pct is None:
                            continue

                        row = await conn.fetchrow(
                            """
                            SELECT last_percent_pnl
                            FROM position_snapshots
                            WHERE wallet_id=$1 AND condition_id=$2
                            """,
                            wallet_id,
                            cond_id,
                        )
                        should_alert = False
                        if row is None:
                            should_alert = False  # первая запись — без алерта
                        else:
                            prev_pct = row["last_percent_pnl"]
                            if prev_pct is not None:
                                delta = float(cur_pct) - float(prev_pct)
                                if abs(delta) >= config.alert_threshold_percent:
                                    should_alert = True

                        # Обновляем снапшот
                        await conn.execute(
                            """
                            INSERT INTO position_snapshots (
                                wallet_id, condition_id, title, outcome,
                                last_percent_pnl, last_cur_price, last_alert_at, updated_at
                            )
                            VALUES ($1, $2, $3, $4, $5, $6,
                                    CASE WHEN $7 THEN now() ELSE last_alert_at END,
                                    now())
                            ON CONFLICT (wallet_id, condition_id)
                            DO UPDATE SET
                                title=EXCLUDED.title,
                                outcome=EXCLUDED.outcome,
                                last_percent_pnl=EXCLUDED.last_percent_pnl,
                                last_cur_price=EXCLUDED.last_cur_price,
                                last_alert_at=CASE
                                    WHEN $7 THEN now()
                                    ELSE position_snapshots.last_alert_at
                                END,
                                updated_at=now()
                            """,
                            wallet_id,
                            cond_id,
                            title,
                            outcome,
                            float(cur_pct),
                            float(cur_price) if cur_price is not None else None,
                            should_alert,
                        )

                        if should_alert and bot is not None:
                            label_text = f" ({label})" if label else ""
                            sign = "+" if float(cur_pct) >= 0 else ""
                            text = (
                                "⚠️ Движение по позиции\n\n"
                                f"Кошелёк: <code>{address}</code>{label_text}\n"
                                f"Рынок: <b>{title}</b>\n"
                                f"Исход: <code>{outcome}</code>\n"
                                f"Текущий PnL: {sign}{float(cur_pct):.2f}%\n"
                            )
                            try:
                                await bot.send_message(
                                    tg_id,
                                    text,
                                    parse_mode=ParseMode.HTML,
                                )
                            except Exception:
                                pass

        except Exception:
            pass

        await asyncio.sleep(config.poll_interval_seconds)


async def monitor_whales():
    """
    Периодически:
    - берём всех китов с включёнными whale_alerts
    - тянем /activity?user=...&type=TRADE
    - ищем новые сделки по timestamp
    - шлём алерты
    """
    assert db_pool is not None
    assert config is not None

    while True:
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT w.id, w.address, w.label, w.tg_user_id,
                           COALESCE(am.last_seen_timestamp, 0) as last_ts,
                           am.id as marker_id
                    FROM wallets w
                    LEFT JOIN activity_markers am ON am.wallet_id = w.id
                    WHERE w.is_whale=TRUE AND w.whale_alerts_enabled=TRUE
                    """
                )

            for r in rows:
                wallet_id = r["id"]
                address = r["address"]
                label = r["label"]
                tg_id = r["tg_user_id"]
                last_ts = int(r["last_ts"] or 0)
                marker_id = r["marker_id"]

                try:
                    trades = await pm_get_activity_trades(address, since_ts=last_ts)
                except Exception:
                    continue

                if not trades:
                    continue

                trades_sorted = sorted(trades, key=lambda t: int(t.get("timestamp", 0)))
                max_ts = last_ts

                for t in trades_sorted:
                    ts = int(t.get("timestamp", 0))
                    if ts <= last_ts:
                        continue
                    max_ts = max(max_ts, ts)

                    title = t.get("title")
                    outcome = t.get("outcome")
                    side = t.get("side")
                    usdc_size = t.get("usdcSize")
                    price = t.get("price")
                    slug = t.get("slug")
                    event_slug = t.get("eventSlug")

                    label_text = f" ({label})" if label else ""
                    url = (
                        f"https://polymarket.com/event/{event_slug}/{slug}"
                        if slug and event_slug
                        else ""
                    )

                    text_lines = [
                        "🐳 Новая сделка кита",
                        f"Кошелёк: <code>{address}</code>{label_text}",
                        f"Рынок: <b>{title}</b>",
                        f"Сторона: <b>{side}</b> по исходу <code>{outcome}</code>",
                    ]
                    if usdc_size is not None:
                        try:
                            usdc_f = float(usdc_size)
                            text_lines.append(f"Объём: <b>{usdc_f:.2f} USDC</b>")
                        except Exception:
                            pass
                    if price is not None:
                        try:
                            price_f = float(price)
                            text_lines.append(f"Цена: {price_f:.3f}")
                        except Exception:
                            pass
                    if url:
                        text_lines.append(f"\n<a href=\"{url}\">Открыть рынок</a>")

                    if bot is not None:
                        try:
                            await bot.send_message(
                                tg_id,
                                "\n".join(text_lines),
                                parse_mode=ParseMode.HTML,
                                disable_web_page_preview=True,
                            )
                        except Exception:
                            pass

                if max_ts > last_ts:
                    async with db_pool.acquire() as conn:
                        if marker_id:
                            await conn.execute(
                                "UPDATE activity_markers SET last_seen_timestamp=$1 WHERE id=$2",
                                max_ts,
                                marker_id,
                            )
                        else:
                            await conn.execute(
                                "INSERT INTO activity_markers (wallet_id, last_seen_timestamp) VALUES ($1, $2)",
                                wallet_id,
                                max_ts,
                            )

        except Exception:
            pass

        await asyncio.sleep(config.whale_poll_interval_seconds)


# =========================
# HTTP health-check сервер для Koyeb
# =========================

async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8000"))  # Koyeb пробрасывает порт в env
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# =========================
# Точка входа
# =========================

async def main():
    global config, bot, db_pool, http_client

    config = Config.from_env()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    db_pool = await asyncpg.create_pool(dsn=config.database_url)
    http_client = httpx.AsyncClient(timeout=20.0)

    await init_db(db_pool)

    # поднимаем HTTP-сервер для health-check'ов Koyeb
    await start_health_server()

    # запускаем фоновые таски
    asyncio.create_task(monitor_positions())
    asyncio.create_task(monitor_whales())

    # стартуем long polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await http_client.aclose()
        await db_pool.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
