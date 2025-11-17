import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from httpx import AsyncClient

from newapp.config import Config
from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.handlers import start, wallets, status


class PolymarketBot:
    """Главный класс бота"""
    
    def __init__(self, config: Config):
        self.config = config
        self.bot: Bot = None
        self.dp: Dispatcher = None
        self.db: Database = None
        self.http_client: AsyncClient = None
        self.polymarket: PolymarketAPI = None
        
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
        
        # Подключение к базе данных
        await self.db.connect()
        self.logger.info("✅ База данных подключена")
        
        # Регистрация зависимостей
        self.dp["db"] = self.db
        self.dp["polymarket"] = self.polymarket
        
        # Регистрация роутеров
        self.dp.include_router(start.router)
        self.dp.include_router(wallets.router)
        self.dp.include_router(status.router)
        
        self.logger.info("✅ Бот настроен")
    
    async def start(self):
        """Запуск бота"""
        try:
            self.logger.info("🚀 Запуск бота...")
            await self.dp.start_polling(
                self.bot,
                allowed_updates=self.dp.resolve_used_update_types()
            )
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