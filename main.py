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
    health_runner = None
    try:
        # СНАЧАЛА запускаем health-сервер
        health_runner = await start_health_server()
        print("✅ Health-сервер запущен")

        # читаем конфиг из ENV
        cfg = Config.from_env()
        core.config = cfg
        
        print("✅ Конфигурация загружена")

        # создаём Bot, пул БД и HTTP-клиент и кладём в core
        core.bot = Bot(
            token=cfg.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        
        print("✅ Бот создан")
        
        # Подключение к БД
        core.db_pool = await asyncpg.create_pool(dsn=cfg.database_url)
        print("✅ Подключение к БД успешно")
        
        core.http_client = httpx.AsyncClient(timeout=20.0)
        print("✅ HTTP-клиент создан")

        # инициализация БД
        await init_db(core.db_pool)
        print("✅ БД инициализирована")

        # регистрируем все хэндлеры (импорт модулей handlers/*)
        register_handlers()
        print("✅ Хэндлеры зарегистрированы")

        # фоновые задачи
        asyncio.create_task(monitor_positions())
        asyncio.create_task(monitor_whales())
        print("✅ Фоновые задачи запущены")

        print("🚀 Запускаем бота...")
        
        # запускаем long polling
        await core.dp.start_polling(
            core.bot, allowed_updates=core.dp.resolve_used_update_types()
        )
        
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        print("🛑 Останавливаем бота...")
        # Закрываем health-сервер
        if health_runner:
            await health_runner.cleanup()
        if core.http_client:
            await core.http_client.aclose()
        if core.db_pool:
            await core.db_pool.close()
        if core.bot:
            await core.bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
