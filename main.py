import asyncio

import asyncpg
import httpx
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import Config
from app import core
from app.db import init_db
from app.health import start_health_server
from app.background import monitor_positions, monitor_whales
from app.handlers import register_handlers


async def main():
    # читаем конфиг из ENV
    cfg = Config.from_env()
    core.config = cfg

    # создаём Bot, пул БД и HTTP-клиент и кладём в core
    core.bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    core.db_pool = await asyncpg.create_pool(dsn=cfg.database_url)
    core.http_client = httpx.AsyncClient(timeout=20.0)

    # инициализация БД
    await init_db(core.db_pool)

    # регистрируем все хэндлеры (импорт модулей handlers/*)
    register_handlers()

    # health-сервер для Koyeb
    await start_health_server()

    # фоновые задачи
    asyncio.create_task(monitor_positions())
    asyncio.create_task(monitor_whales())

    # запускаем long polling
    try:
        await core.dp.start_polling(
            core.bot, allowed_updates=core.dp.resolve_used_update_types()
        )
    finally:
        await core.http_client.aclose()
        await core.db_pool.close()
        await core.bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
