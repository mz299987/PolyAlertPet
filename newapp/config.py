import os
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Config:
    """Конфигурация приложения"""
    bot_token: str
    database_url: str
    cache_ttl: int = 300
    sync_interval: int = 300
    notification_threshold: float = 1000.0
    rate_limit_per_minute: int = 30
    admin_ids: List[int] = field(default_factory=list)
    port: int = 8000
    max_wallets_per_user: int = 10
    background_sync_interval: int = 300  # 5 минут
    
    @classmethod
    def from_env(cls) -> "Config":
        """Создает конфигурацию из переменных окружения"""
        bot_token = os.getenv("BOT_TOKEN")
        database_url = os.getenv("DATABASE_URL")
        port = int(os.getenv("PORT", "8000"))
        
        # Получаем ID администраторов из переменной окружения
        admin_ids_str = os.getenv("ADMIN_IDS", "")
        admin_ids = [int(x.strip()) for x in admin_ids_str.split(",") if x.strip()]
        
        if not bot_token:
            raise ValueError("BOT_TOKEN is required")
        if not database_url:
            raise ValueError("DATABASE_URL is required")
            
        return cls(
            bot_token=bot_token,
            database_url=database_url,
            admin_ids=admin_ids,
            port=port
        )
