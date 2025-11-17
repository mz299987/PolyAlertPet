import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Конфигурация приложения"""
    bot_token: str
    database_url: str
    port: int = 8000
    
    @classmethod
    def from_env(cls) -> "Config":
        """Создает конфигурацию из переменных окружения"""
        bot_token = os.getenv("BOT_TOKEN")
        database_url = os.getenv("DATABASE_URL")
        port = int(os.getenv("PORT", "8000"))
        
        if not bot_token:
            raise ValueError("BOT_TOKEN is required")
        if not database_url:
            raise ValueError("DATABASE_URL is required")
            
        return cls(
            bot_token=bot_token,
            database_url=database_url,
            port=port
        )