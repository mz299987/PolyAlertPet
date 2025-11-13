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

# режим добавления кошелька по кнопкам:
# user_add_mode[user_id] = "wallet" или "whale"
user_add_mode: Dict[int, str] = {}

# =========================
# Утилиты
# =========================

WALLET_REGEX = re.compile(r"0x[a-fA-F0-9]{40}", re.IGNORECASE)


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


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Основная клавиатура под полем ввода.
    """
    kb = ReplyKeyboardMarkup(
        resize_keyboard=True,
        keyboard=[
            [
                KeyboardButton(text="➕ Мой кошелёк"),
                KeyboardButton(text="➕ Кит"),
            ],
            [
                KeyboardButton(text="📊 Мои кошельки"),
                KeyboardButton(text="📈 Состояние"),
            ],
        ],
    )
    return kb


# =========================
# Инициализация БД
# =========================

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS tg_users (
    id BIGINT PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT now()
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


async def ensure_user(pool: asyncpg.Pool, tg_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tg_users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            tg_id,
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
    text = (
        "Привет! Я трекаю твой Polymarket профиль 🧠\n\n"
        "Что я умею:\n"
        "• слать алерты при движении позиций на ±5%\n"
        "• отслеживать китов и их новые сделки\n"
        "• показывать текущее состояние кошелька/китов\n\n"
        "Используй кнопки внизу:\n"
        "• «➕ Мой кошелёк» — добавь свой профиль Polymarket\n"
        "• «➕ Кит» — добавь кошелёк кита\n"
        "• «📊 Мои кошельки» — список всех\n"
        "• «📈 Состояние» — текущий equity и топ рынки\n\n"
        "Также доступны команды:\n"
        "/add_wallet адрес_или_ссылка [label]\n"
        "/add_whale адрес_или_ссылка [label]\n"
        "/wallets — список кошельков\n"
        "/pnl period — PnL за период (1d, 7d, 30d)\n"
        "/state — текущее состояние кошельков\n"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@dp.message(Command("add_wallet"))
async def cmd_add_wallet(message: Message):
    """
    /add_wallet адрес_или_ссылка [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.reply(
            "Формат: <code>/add_wallet адрес_или_ссылка [label]</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    addr_candidate = parts[1]
    label = parts[2] if len(parts) > 2 else None

    address = await resolve_wallet_or_profile(addr_candidate)
    if not address:
        await message.reply(
            "Не смог найти 0x-адрес в сообщении.\n"
            "Пришли что-то вроде:\n"
            "<code>/add_wallet https://polymarket.com/@username main</code>\n"
            "или\n"
            "<code>/add_wallet 0x1234...abcd main</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    status = await save_wallet(message.from_user.id, address, label, is_whale=False)

    if status == "exists":
        await message.reply("Этот кошелёк уже добавлен как твой 👍")
    else:
        await message.reply(
            f"Кошелёк <code>{address}</code> добавлен ✅",
            parse_mode=ParseMode.HTML,
        )


@dp.message(Command("add_whale"))
async def cmd_add_whale(message: Message):
    """
    /add_whale адрес_или_ссылка [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.reply(
            "Формат: <code>/add_whale адрес_или_ссылка [label]</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    addr_candidate = parts[1]
    label = parts[2] if len(parts) > 2 else None

    address = await resolve_wallet_or_profile(addr_candidate)
    if not address:
        await message.reply(
            "Не смог найти 0x-адрес.\n"
            "Пришли ссылку на профиль Polymarket или 0x-адрес.\n"
            "Например:\n"
            "<code>/add_whale https://polymarket.com/@bigwhale MegaWhale</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    status = await save_wallet(message.from_user.id, address, label, is_whale=True)

    if status == "exists":
        await message.reply("Этот кит уже есть в списке 🐳")
    else:
        await message.reply(
            f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам.",
            parse_mode=ParseMode.HTML,
        )


@dp.message(Command("wallets"))
async def cmd_wallets(message: Message):
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

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
        await message.reply(
            "У тебя ещё нет кошельков.\n"
            "Нажми «➕ Мой кошелёк» или «➕ Кит» и отправь ссылку на профиль Polymarket."
        )
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


async def build_state_text(tg_user_id: int) -> str:
    """
    Формирует текстовое состояние всех кошельков пользователя: equity + топ рынки.
    """
    assert db_pool is not None

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
        return (
            "У тебя пока нет кошельков.\n"
            "Нажми «➕ Мой кошелёк» или «➕ Кит» и отправь ссылку на профиль Polymarket."
        )

    lines: List[str] = ["📈 Текущее состояние кошельков:\n"]

    for w in wallets:
        address = w["address"]
        label = w["label"]
        is_whale = w["is_whale"]
        icon = "🐳" if is_whale else "👤"
        label_text = f" ({label})" if label else ""

        # тянем данные с Polymarket
        try:
            value = await pm_get_value(address)
        except Exception:
            value = None

        try:
            positions = await pm_get_positions(address)
        except Exception:
            positions = []

        value_str = f"{value:.2f} USDC" if value is not None else "n/a"
        lines.append(f"{icon} <code>{address}</code>{label_text}")
        lines.append(f"Equity: <b>{value_str}</b>")

        if positions:
            lines.append(f"Позиции: {len(positions)}")

            # сортируем по абсолютному cashPnl, чтобы показать самые важные
            def pnl_key(p: Dict[str, Any]) -> float:
                try:
                    return abs(float(p.get("cashPnl") or 0.0))
                except Exception:
                    return 0.0

            top_positions = sorted(positions, key=pnl_key, reverse=True)[:3]

            if top_positions:
                lines.append("Топ рынки:")
                for p in top_positions:
                    title = p.get("title") or "Без названия"
                    outcome = p.get("outcome") or "?"
                    cash_pnl = p.get("cashPnl")
                    percent_pnl = p.get("percentPnl")
                    try:
                        cash_pnl_f = float(cash_pnl) if cash_pnl is not None else 0.0
                    except Exception:
                        cash_pnl_f = 0.0
                    try:
                        pct_f = float(percent_pnl) if percent_pnl is not None else 0.0
                    except Exception:
                        pct_f = 0.0

                    sign_cash = "+" if cash_pnl_f >= 0 else ""
                    sign_pct = "+" if pct_f >= 0 else ""
                    lines.append(
                        f"• <b>{title}</b> ({outcome}) — "
                        f"{sign_pct}{pct_f:.2f}% ({sign_cash}{cash_pnl_f:.2f} USDC)"
                    )
        else:
            lines.append("Позиции: 0")

        lines.append("")  # пустая строка между кошельками

    return "\n".join(lines).strip()


@dp.message(Command("state"))
async def cmd_state(message: Message):
    text = await build_state_text(message.from_user.id)
    await message.answer(text, parse_mode=ParseMode.HTML)


@dp.message(Command("pnl"))
async def cmd_pnl(message: Message):
    """
    /pnl [period]
    period: 1d, 7d, 30d
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    parts = (message.text or "").split()
    period_str = parts[1] if len(parts) > 1 else "7d"

    if period_str not in ("1d", "7d", "30d"):
        await message.reply(
            "Допустимые периоды: 1d, 7d, 30d\nПример: <code>/pnl 7d</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    days = int(period_str[:-1])
    now = now_utc()
    from_time = now - timedelta(days=days)

    async with db_pool.acquire() as conn:
        # Берём первый и последний снапшоты equity для каждого НЕ-кита кошелька
        wallets = await conn.fetch(
            "SELECT id, address, label FROM wallets WHERE tg_user_id=$1 AND is_whale=FALSE",
            message.from_user.id,
        )
        if not wallets:
            await message.reply("Нет своих кошельков. Добавь через «➕ Мой кошелёк».")
            return

        text_lines = [f"PNL за {period_str}:"]
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
                    f"• <code>{w['address']}</code>: недостаточно данных для периода"
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

@dp.message(F.text == "➕ Мой кошелёк")
async def btn_my_wallet(message: Message):
    await ensure_user(db_pool, message.from_user.id)  # type: ignore[arg-type]
    user_add_mode[message.from_user.id] = "wallet"
    await message.answer(
        "Ок, добавляем твой кошелёк 👤\n\n"
        "Пришли ссылку на профиль Polymarket или 0x-адрес.\n"
        "Поддерживаю форматы:\n"
        "• https://polymarket.com/@username\n"
        "• https://polymarket.com/profile/...\n"
        "• https://polymarket.com/wallet/0x...\n"
        "• просто 0x-адрес",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(F.text == "➕ Кит")
async def btn_whale(message: Message):
    await ensure_user(db_pool, message.from_user.id)  # type: ignore[arg-type]
    user_add_mode[message.from_user.id] = "whale"
    await message.answer(
        "Ок, добавляем кита 🐳\n\n"
        "Пришли ссылку на профиль Polymarket этого кита или его 0x-адрес.",
        reply_markup=main_menu_keyboard(),
    )


@dp.message(F.text == "📊 Мои кошельки")
async def btn_wallets(message: Message):
    await cmd_wallets(message)


@dp.message(F.text == "📈 Состояние")
async def btn_state(message: Message):
    await cmd_state(message)


@dp.message(F.text)
async def handle_free_text(message: Message):
    """
    Обрабатываем свободный текст:
    - если пользователь в режиме добавления кошелька/кита — пытаемся зарезолвить ссылку.
    """
    # игнорируем команды вида /start, /add_wallet и т.д.
    if (message.text or "").startswith("/"):
        return

    mode = user_add_mode.get(message.from_user.id)
    if mode not in ("wallet", "whale"):
        # пока ничего хитрого не делаем, просто подсказываем
        await message.answer(
            "Если хочешь добавить кошелёк, нажми «➕ Мой кошелёк» или «➕ Кит», "
            "а потом отправь ссылку на профиль Polymarket или 0x-адрес 😉",
            reply_markup=main_menu_keyboard(),
        )
        return

    # пытаемся резолвнуть ссылку/текст в 0x-адрес
    address = await resolve_wallet_or_profile(message.text or "")
    if not address:
        await message.answer(
            "Не смог найти 0x-адрес в этом сообщении 😔\n"
            "Отправь ещё раз ссылку на профиль Polymarket или чистый 0x-адрес.",
            reply_markup=main_menu_keyboard(),
        )
        return

    label = None
    is_whale = mode == "whale"
    status = await save_wallet(message.from_user.id, address, label, is_whale=is_whale)

    if is_whale:
        if status == "exists":
            await message.answer(
                "Этот кит уже есть в списке 🐳",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await message.answer(
                f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам.",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(),
            )
    else:
        if status == "exists":
            await message.answer(
                "Этот кошелёк уже добавлен как твой 👍",
                reply_markup=main_menu_keyboard(),
            )
        else:
            await message.answer(
                f"Кошелёк <code>{address}</code> добавлен ✅",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(),
            )

    # сбрасываем режим добавления
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
            # можно логировать, но для MVP просто молча переживаем ошибку
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

                # новые сделки сортируем по timestamp asc, чтобы сообщения шли по порядку
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

                # Обновляем маркер
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
