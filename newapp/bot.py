import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from httpx import AsyncClient

from newapp.config import Config
from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.cache import Cache
from newapp.security import Security
from newapp.notifications import NotificationManager

# Импортируем роутеры напрямую
from newapp.handlers.start import router as start_router
from newapp.handlers.wallets import router as wallets_router
from newapp.handlers.status import router as status_router
from newapp.handlers.analytics import router as analytics_router
from newapp.handlers.settings import router as settings_router
from newapp.handlers.betting import router as betting_router
from newapp.handlers.reports import router as reports_router


class PolymarketBot:
    """Главный класс бота"""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.db: Database = None
        self.http_client: AsyncClient = None
        self.polymarket: PolymarketAPI = None
        self.cache: Cache = None
        self.security: Security = None
        self.notifications: NotificationManager = None
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.logger = logging.getLogger(__name__)
    
    async def setup(self):
        """Настройка бота"""
        self.logger.info("🔄 Настройка бота...")
        
        # Инициализация компонентов
        self.bot = Bot(
            token=self.config.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        self.dp = Dispatcher()
        self.db = Database(self.config.database_url)
        self.http_client = AsyncClient(timeout=30.0)
        self.polymarket = PolymarketAPI(self.http_client)
        
        self.cache = Cache()
        self.security = Security(self.config.rate_limit_per_minute)
        self.notifications = NotificationManager(self.bot, self.db, self.polymarket)
        
        # Подключение к базе данных
        await self.db.connect()
        self.logger.info("✅ База данных подключена")
        
        # Инициализация кэша
        await self.cache.initialize()
        self.logger.info("✅ Кэш инициализирован")
        
        # Регистрация зависимостей
        self.dp["db"] = self.db
        self.dp["polymarket"] = self.polymarket
        self.dp["cache"] = self.cache
        self.dp["security"] = self.security
        self.dp["notifications"] = self.notifications
        
        # Регистрация роутеров
        self.dp.include_router(start_router)
        self.dp.include_router(wallets_router)
        self.dp.include_router(status_router)
        self.dp.include_router(analytics_router)
        self.dp.include_router(settings_router)
        self.dp.include_router(betting_router)
        self.dp.include_router(reports_router)
        
        # Импортируем и регистрируем недостающие обработчики
        try:
            from newapp.handlers.missing_handlers import router as missing_handlers_router
            self.dp.include_router(missing_handlers_router)
        except ImportError as e:
            self.logger.warning(f"Не удалось загрузить дополнительные обработчики: {e}")
        
        self.logger.info("✅ Бот настроен")
    
    async def start_health_server(self):
        """Запуск health-сервера для Koyeb"""
        async def health_handler(request):
            return web.Response(text="OK")
        
        app = web.Application()
        app.router.add_get("/", health_handler)
        app.router.add_get("/health", health_handler)
        
        runner = web.AppRunner(app)
        await runner.setup()
        
        port = int(os.getenv("PORT", "8000"))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        
        self.logger.info(f"✅ Health-сервер запущен на порту {port}")
        return runner
    
    async def start(self):
        """Запуск бота"""
        try:
            # Запускаем health-сервер
            health_runner = await self.start_health_server()
            
            self.logger.info("🚀 Запуск бота...")
            
            # Попытка запуска с обработкой конфликта
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    await self.dp.start_polling(
                        self.bot,
                        allowed_updates=self.dp.resolve_used_update_types(),
                        timeout=10
                    )
                    break
                except Exception as e:
                    if "Conflict" in str(e) and attempt < max_retries - 1:
                        self.logger.warning(f"⚠️ Конфликт с другим ботом, попытка {attempt + 1}/{max_retries}")
                        await asyncio.sleep(5)
                    else:
                        raise
                        
        except Exception as e:
            self.logger.error(f"❌ Ошибка при запуске бота: {e}")
            raise
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Корректное завершение работы"""
        self.logger.info("🛑 Завершение работы...")

        if self.http_client:
            await self.http_client.aclose()
            self.logger.info("✅ HTTP клиент закрыт")
        
        if self.db:
            await self.db.close()
            self.logger.info("✅ База данных отключена")
        
        if self.bot:
            await self.bot.session.close()
            self.logger.info("✅ Сессия бота закрыта")
    
    async def run(self):
        """Главный метод запуска"""
        try:
            await self.setup()
            await self.start()
        except KeyboardInterrupt:
            self.logger.info("⏹️ Остановка по запросу пользователя")
        except Exception as e:
            self.logger.error(f"💥 Критическая ошибка: {e}")
            raise


async def main():
    """Точка входа"""
    try:
        # Загрузка конфигурации
        config = Config.from_env()
        
        # Создание и запуск бота
        bot = PolymarketBot(config)
        await bot.run()
        
    except Exception as e:
        print(f"❌ Не удалось запустить бота: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
