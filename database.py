import asyncpg
from typing import List, Dict, Any, Optional


class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None
    
    async def connect(self):
        """Подключение к базе данных"""
        self.pool = await asyncpg.create_pool(self.dsn)
        await self.init_tables()
    
    async def close(self):
        """Закрытие соединения"""
        if self.pool:
            await self.pool.close()
    
    async def init_tables(self):
        """Инициализация таблиц"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    language VARCHAR(10) DEFAULT 'ru',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    address VARCHAR(42) NOT NULL,
                    name VARCHAR(100),
                    is_whale BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, address)
                )
            """)
    
    async def ensure_user(self, user_id: int) -> bool:
        """Создает пользователя если не существует"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                INSERT INTO users (id) VALUES ($1) 
                ON CONFLICT (id) DO NOTHING
                RETURNING id
            """, user_id)
            return result is not None
    
    async def get_user_language(self, user_id: int) -> str:
        """Получает язык пользователя"""
        async with self.pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT language FROM users WHERE id = $1
            """, user_id)
            return result['language'] if result else 'ru'
    
    async def set_user_language(self, user_id: int, language: str):
        """Устанавливает язык пользователя"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET language = $1 WHERE id = $2
            """, language, user_id)
    
    async def add_wallet(self, user_id: int, address: str, name: Optional[str] = None, is_whale: bool = False) -> bool:
        """Добавляет кошелек"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO wallets (user_id, address, name, is_whale) 
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (user_id, address) DO UPDATE SET
                    name = EXCLUDED.name, is_whale = EXCLUDED.is_whale
                """, user_id, address, name, is_whale)
                return True
            except Exception:
                return False
    
    async def get_user_wallets(self, user_id: int) -> List[Dict[str, Any]]:
        """Получает все кошельки пользователя"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT id, address, name, is_whale, created_at
                FROM wallets 
                WHERE user_id = $1 
                ORDER BY created_at
            """, user_id)
            return [dict(row) for row in rows]
    
    async def delete_wallet(self, user_id: int, wallet_id: int) -> bool:
        """Удаляет кошелек"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM wallets WHERE id = $1 AND user_id = $2
            """, wallet_id, user_id)
            return "DELETE" in result