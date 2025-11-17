import asyncio
import json
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import hashlib

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class Cache:
    """Класс для работы с локальным кэшем"""
    
    def __init__(self):
        self.local_cache: Dict[str, Any] = {}
        self.local_cache_ttl: Dict[str, datetime] = {}
        
    async def initialize(self):
        """Инициализация кэша"""
        print("✅ Локальный кэш инициализирован")
    
    def _generate_key(self, func_name: str, *args, **kwargs) -> str:
        """Генерирует ключ кэша"""
        key_data = f"{func_name}:{str(args)}:{str(kwargs)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        try:
            # Проверяем локальный кэш
            if key in self.local_cache:
                if datetime.now() < self.local_cache_ttl.get(key, datetime.min):
                    return self.local_cache[key]
                else:
                    # Удаляем просроченный кэш
                    del self.local_cache[key]
                    del self.local_cache_ttl[key]
        except Exception as e:
            print(f"❌ Ошибка получения из кэша {key}: {e}")
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 300):
        """Установка значения в кэш"""
        try:
            # Сохраняем в локальный кэш
            self.local_cache[key] = value
            self.local_cache_ttl[key] = datetime.now() + timedelta(seconds=ttl)
        except Exception as e:
            print(f"❌ Ошибка сохранения в кэш {key}: {e}")
    
    async def delete(self, key: str):
        """Удаление значения из кэша"""
        try:
            # Удаляем из локального кэша
            if key in self.local_cache:
                del self.local_cache[key]
            if key in self.local_cache_ttl:
                del self.local_cache_ttl[key]
        except Exception as e:
            print(f"❌ Ошибка удаления из кэша {key}: {e}")
    
    async def get_user_language(self, user_id: int) -> str:
        """Получает язык пользователя из кэша"""
        cache_key = f"user_lang:{user_id}"
        cached_lang = await self.get(cache_key)
        
        if cached_lang:
            return cached_lang
        
        # Если нет в кэше, возвращаем английский по умолчанию
        return "en"
    
    async def set_user_language(self, user_id: int, language: str):
        """Сохраняет язык пользователя в кэш"""
        cache_key = f"user_lang:{user_id}"
        await self.set(cache_key, language, ttl=3600)  # Кэшируем на 1 час
    
    async def get_market_data(self, market_id: str) -> Optional[Dict]:
        """Получает данные рынка из кэша"""
        cache_key = f"market:{market_id}"
        return await self.get(cache_key)
    
    async def set_market_data(self, market_id: str, data: Dict, ttl: int = 300):
        """Сохраняет данные рынка в кэш"""
        cache_key = f"market:{market_id}"
        await self.set(cache_key, data, ttl=ttl)
    
    async def get_wallet_positions(self, address: str) -> Optional[list]:
        """Получает позиции кошелька из кэша"""
        cache_key = f"wallet_positions:{address}"
        return await self.get(cache_key)
    
    async def set_wallet_positions(self, address: str, positions: list, ttl: int = 60):
        """Сохраняет позиции кошелька в кэш"""
        cache_key = f"wallet_positions:{address}"
        await self.set(cache_key, positions, ttl=ttl)
    
    async def get_top_markets(self) -> Optional[list]:
        """Получает топ рынков из кэша"""
        cache_key = "top_markets"
        return await self.get(cache_key)
    
    async def set_top_markets(self, markets: list, ttl: int = 300):
        """Сохраняет топ рынков в кэш"""
        cache_key = "top_markets"
        await self.set(cache_key, markets, ttl=ttl)
    
    async def clear_user_cache(self, user_id: int):
        """Очищает кэш пользователя"""
        cache_key = f"user_lang:{user_id}"
        await self.delete(cache_key)
    
    async def close(self):
        """Закрытие кэша"""
        self.local_cache.clear()
        self.local_cache_ttl.clear()


def cache_method(ttl: Optional[int] = None):
    """Декоратор для кэширования методов"""
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            cache_manager = getattr(self, 'cache_manager', None)
            if not cache_manager:
                return await func(self, *args, **kwargs)
            
            key = cache_manager._generate_key(func.__name__, *args, **kwargs)
            cached = await cache_manager.get(key)
            
            if cached is not None:
                return cached
            
            result = await func(self, *args, **kwargs)
            await cache_manager.set(key, result, ttl or 300)
            
            return result
        return wrapper
    return decorator
