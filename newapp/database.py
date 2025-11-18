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
    
            # Таблица для Safe кошельков пользователей
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_safe_wallets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    safe_address VARCHAR(42) NOT NULL UNIQUE,
                    original_address VARCHAR(42) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
            # Таблица для хранения ставок
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_bets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    safe_address VARCHAR(42) NOT NULL,
                    market_id VARCHAR(100) NOT NULL,
                    outcome INTEGER NOT NULL,
                    amount DECIMAL(18, 6) NOT NULL,
                    transaction_hash VARCHAR(66),
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
            # Миграция: переименовываем столбец tg_user_id в user_id если он существует
            await conn.execute("""
                DO $$ 
                BEGIN 
                    IF EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name = 'wallets' AND column_name = 'tg_user_id') THEN
                        ALTER TABLE wallets RENAME COLUMN tg_user_id TO user_id;
                    END IF;
                END $$;
            """)
    
            # Миграция: добавляем столбец name если он отсутствует
            await conn.execute("""
                DO $$ 
                BEGIN 
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name = 'wallets' AND column_name = 'name') THEN
                        ALTER TABLE wallets ADD COLUMN name VARCHAR(100);
                    END IF;
                END $$;
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
    
    async def get_user_safe_wallet(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает Safe кошелек пользователя"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT safe_address, original_address, is_active, created_at
                FROM user_safe_wallets 
                WHERE user_id = $1 AND is_active = TRUE
                ORDER BY created_at DESC 
                LIMIT 1
            """, user_id)
            return dict(row) if row else None
    
    async def save_user_safe_wallet(self, user_id: int, safe_address: str, original_address: str) -> bool:
        """Сохраняет Safe кошелек пользователя"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO user_safe_wallets (user_id, safe_address, original_address)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (safe_address) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    original_address = EXCLUDED.original_address,
                    is_active = TRUE
                """, user_id, safe_address, original_address)
                return True
            except Exception:
                return False
    
    async def save_user_bet(self, user_id: int, safe_address: str, market_id: str, 
                           outcome: int, amount: float, transaction_hash: str) -> bool:
        """Сохраняет запись о ставке пользователя"""
        async with self.pool.acquire() as conn:
            try:
                await conn.execute("""
                    INSERT INTO user_bets (user_id, safe_address, market_id, outcome, amount, transaction_hash)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, safe_address, market_id, outcome, amount, transaction_hash)
                return True
            except Exception:
                return False
    
    async def get_user_bets(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает историю ставок пользователя"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT market_id, outcome, amount, transaction_hash, status, created_at
                FROM user_bets 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
            """, user_id, limit)
            return [dict(row) for row in rows]
    
    async def update_bet_status(self, transaction_hash: str, status: str) -> bool:
        """Обновляет статус ставки"""
        async with self.pool.acquire() as conn:
            result = await conn.execute("""
                UPDATE user_bets 
                SET status = $1 
                WHERE transaction_hash = $2
            """, status, transaction_hash)
            return "UPDATE" in result
