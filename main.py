import os
import re
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

import asyncpg
import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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


# =========================
# Утилиты
# =========================

WALLET_REGEX = re.compile(r"0x[a-fA-F0-9]{40}")


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
    :contentReference[oaicite:1]{index=1}
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
    Общая стоимость позиций по кошельку. :contentReference[oaicite:2]{index=2}
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
    :contentReference[oaicite:3]{index=3}
    """
    assert http_client is not None
    params: Dict[str, Any] = {
        "user": address,
        "limit": 100,
        "type": "TRADE",
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC",
    }
    # Можно использовать start/end, но для MVP просто фильтруем по timestamp на клиенте
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
# Хэндлеры Telegram
# =========================

@dp.message(Command("start"))
async def cmd_start(message: Message):
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)
    text = (
        "Привет! Я трекаю твой Polymarket профиль 🧠\n\n"
        "Доступные команды:\n"
        "/add_wallet <адрес|ссылка> [label] — добавить свой кошелёк\n"
        "/add_whale <адрес|ссылка> [label] — добавить кита для отслеживания\n"
        "/wallets — показать все кошельки\n"
        "/pnl <period> — PnL за период (1d, 7d, 30d)\n\n"
        "После добавления кошельков я буду:\n"
        "• слать алерты при движении позиции на ±5% (по умолчанию)\n"
        "• слать алерты по сделкам китов.\n"
    )
    await message.answer(text)


@dp.message(Command("add_wallet"))
async def cmd_add_wallet(message: Message):
    """
    /add_wallet <адрес или ссылка> [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply("Формат: <code>/add_wallet адрес_или_ссылка [label]</code>", parse_mode=ParseMode.HTML)
        return

    addr_candidate = " ".join(parts[1:2])
    label = " ".join(parts[2:]) if len(parts) > 2 else None

    address = extract_wallet_address(addr_candidate)
    if not address:
        await message.reply("Не вижу 0x-адрес в сообщении. Пришли что-то вроде:\n"
                            "<code>/add_wallet 0x1234...abcd main</code>", parse_mode=ParseMode.HTML)
        return

    async with db_pool.acquire() as conn:
        # Уже есть?
        row = await conn.fetchrow(
            "SELECT id FROM wallets WHERE tg_user_id=$1 AND address=$2 AND is_whale=FALSE",
            message.from_user.id,
            address,
        )
        if row:
            await message.reply("Этот кошелёк уже добавлен как твой 👍")
            return

        await conn.execute(
            """
            INSERT INTO wallets (tg_user_id, address, label, is_whale, alerts_enabled)
            VALUES ($1, $2, $3, FALSE, TRUE)
            """,
            message.from_user.id,
            address,
            label,
        )

    await message.reply(f"Кошелёк <code>{address}</code> добавлен ✅", parse_mode=ParseMode.HTML)


@dp.message(Command("add_whale"))
async def cmd_add_whale(message: Message):
    """
    /add_whale <адрес или ссылка> [label]
    """
    assert db_pool is not None
    await ensure_user(db_pool, message.from_user.id)

    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.reply("Формат: <code>/add_whale адрес_или_ссылка [label]</code>", parse_mode=ParseMode.HTML)
        return

    addr_candidate = " ".join(parts[1:2])
    label = " ".join(parts[2:]) if len(parts) > 2 else None

    address = extract_wallet_address(addr_candidate)
    if not address:
        await message.reply("Не вижу 0x-адрес. Пришли что-то вроде:\n"
                            "<code>/add_whale 0x1234...abcd MegaWhale</code>", parse_mode=ParseMode.HTML)
        return

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id FROM wallets WHERE tg_user_id=$1 AND address=$2 AND is_whale=TRUE",
            message.from_user.id,
            address,
        )
        if row:
            await message.reply("Этот кит уже есть в списке 🐳")
            return

        w_id = await conn.fetchval(
            """
            INSERT INTO wallets (tg_user_id, address, label, is_whale, whale_alerts_enabled)
            VALUES ($1, $2, $3, TRUE, TRUE)
            RETURNING id
            """,
            message.from_user.id,
            address,
            label,
        )
        # Инициализируем маркер активности
        await conn.execute(
            "INSERT INTO activity_markers (wallet_id, last_seen_timestamp) VALUES ($1, $2)",
            w_id,
            0,
        )

    await message.reply(f"Кит <code>{address}</code> добавлен 🐳, буду слать алерты по его сделкам.",
                        parse_mode=ParseMode.HTML)


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
        await message.reply("У тебя ещё нет кошельков. Добавь через /add_wallet или /add_whale.")
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
        await message.reply("Допустимые периоды: 1d, 7d, 30d\nПример: <code>/pnl 7d</code>",
                            parse_mode=ParseMode.HTML)
        return

    days = int(period_str[:-1])
    now = now_utc()
    from_time = now - timedelta(days=days)  # type: ignore[name-defined]  # добавим импорт ниже

    async with db_pool.acquire() as conn:
        # Берём первый и последний снапшоты equity для каждого НЕ-кита кошелька
        wallets = await conn.fetch(
            "SELECT id, address, label FROM wallets WHERE tg_user_id=$1 AND is_whale=FALSE",
            message.from_user.id,
        )
        if not wallets:
            await message.reply("Нет своих кошельков. Добавь через /add_wallet.")
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
                f"• <code>{w['address']}</code>{label}: {sign}{delta:.2f} USDC ({sign}{pct:.2f}%)"
            )

    await message.reply("\n".join(text_lines), parse_mode=ParseMode.HTML)


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
                except Exception as e:
                    # Можно логировать, но для MVP просто пропускаем
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
                                await bot.send_message(tg_id, text, parse_mode=ParseMode.HTML)
                            except Exception:
                                pass

        except Exception:
            # Можно залогировать, но для MVP просто молча переживаем ошибку
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

                # Новые сделки сортируем по timestamp asc, чтобы сообщения шли по порядку
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
                    url = f"https://polymarket.com/event/{event_slug}/{slug}" if slug and event_slug else ""

                    text_lines = [
                        "🐳 Новая сделка кита",
                        f"Кошелёк: <code>{address}</code>{label_text}",
                        f"Рынок: <b>{title}</b>",
                        f"Сторона: <b>{side}</b> по исходу <code>{outcome}</code>",
                    ]
                    if usdc_size is not None:
                        text_lines.append(f"Объём: <b>{float(usdc_size):.2f} USDC</b>")
                    if price is not None:
                        text_lines.append(f"Цена: {float(price):.3f}")
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
# Точка входа
# =========================

from datetime import timedelta  # нужно для /pnl


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

    # Запускаем фоновые таски
    asyncio.create_task(monitor_positions())
    asyncio.create_task(monitor_whales())

    # Стартуем long polling
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await http_client.aclose()
        await db_pool.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
