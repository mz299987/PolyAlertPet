from typing import Optional

import asyncpg

from .core import LANG_DEFAULT

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


async def ensure_user(pool: asyncpg.Pool, tg_id: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO tg_users (id) VALUES ($1) ON CONFLICT (id) DO NOTHING",
            tg_id,
        )


async def get_user_lang(pool: asyncpg.Pool, user_id: int) -> str:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT lang FROM tg_users WHERE id=$1", user_id)
    lang = row["lang"] if row and row["lang"] else None
    return lang or LANG_DEFAULT


async def set_user_lang(pool: asyncpg.Pool, user_id: int, lang: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE tg_users SET lang=$1 WHERE id=$2",
            lang,
            user_id,
        )


async def save_wallet(
    pool: asyncpg.Pool,
    tg_user_id: int,
    address: str,
    label: Optional[str],
    is_whale: bool,
) -> str:
    """
    Добавляет кошелёк или кита в БД.
    Возвращает: "exists", "wallet_added", "whale_added".
    """
    async with pool.acquire() as conn:
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
