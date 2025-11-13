from typing import Optional
from datetime import datetime, timezone

import asyncpg
import httpx
from aiogram import Dispatcher
from dataclasses import dataclass

from .config import Config


# глобальное состояние, к которому обращаются другие модули
config: Optional[Config] = None
bot: Optional["Bot"] = None  # тип Bot импортируется в main.py при создании
db_pool: Optional[asyncpg.Pool] = None
http_client: Optional[httpx.AsyncClient] = None

# основной Dispatcher для aiogram
dp: Dispatcher = Dispatcher()

# язык по умолчанию
LANG_DEFAULT = "en"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
