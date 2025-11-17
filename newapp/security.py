"""Модуль безопасности: валидация, лимиты запросов, аудит действий"""

import re
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class Security:
    """Класс для управления безопасностью и валидацией"""

    def __init__(self, rate_limit_per_minute: int = 30):
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limits: Dict[int, List[float]] = {}  # user_id: [timestamps]
        self.failed_attempts: Dict[int, int] = {}  # user_id: count
        self.last_reset: Dict[int, datetime] = {}  # user_id: last_reset_time
    
    def validate_wallet_address(self, address: str) -> Tuple[bool, str]:
        """Валидация адреса кошелька"""
        # Проверка на 0x-адрес Ethereum
        if re.match(r"^0x[a-fA-F0-9]{40}$", address):
            return True, "Валидный Ethereum адрес"
        
        # Проверка на Polymarket username (не менее 3 символов)
        if re.match(r"^[a-zA-Z0-9_]{3,20}$", address):
            return True, "Валидный Polymarket username"
        
        # Проверка на ENS домен
        if re.match(r"^[a-zA-Z0-9-]+\.eth$", address.lower()):
            return True, "Валидный ENS домен"
        
        return False, "❌ Неверный формат адреса. Используйте 0x-адрес, Polymarket username или ENS домен"
    
    def check_rate_limit(self, user_id: int) -> Tuple[bool, Dict[str, int]]:
        """Проверка лимита запросов пользователя"""
        now = time.time()
        
        # Инициализация записи для пользователя
        if user_id not in self.rate_limits:
            self.rate_limits[user_id] = []
        
        # Удаляем старые запросы (старше 1 минуты)
        self.rate_limits[user_id] = [
            ts for ts in self.rate_limits[user_id] 
            if now - ts < 60
        ]
        
        # Проверяем лимит
        current_requests = len(self.rate_limits[user_id])
        
        if current_requests >= self.rate_limit_per_minute:
            return False, {
                "limit": self.rate_limit_per_minute,
                "remaining": 0,
                "reset_in": int(60 - (now - self.rate_limits[user_id][0]))
            }
        
        # Добавляем текущий запрос
        self.rate_limits[user_id].append(now)
        
        return True, {
            "limit": self.rate_limit_per_minute,
            "remaining": self.rate_limit_per_minute - current_requests - 1,
            "reset_in": int(60 - (now - self.rate_limits[user_id][0])) if self.rate_limits[user_id] else 60
        }
    
    def get_rate_limit_info(self, user_id: int) -> Dict[str, int]:
        """Получает информацию о лимитах пользователя"""
        now = time.time()
        
        if user_id not in self.rate_limits:
            return {
                "limit": self.rate_limit_per_minute,
                "remaining": self.rate_limit_per_minute,
                "reset_in": 0
            }
        
        # Удаляем старые запросы
        self.rate_limits[user_id] = [
            ts for ts in self.rate_limits[user_id] 
            if now - ts < 60
        ]
        
        current_requests = len(self.rate_limits[user_id])
        
        return {
            "limit": self.rate_limit_per_minute,
            "remaining": max(0, self.rate_limit_per_minute - current_requests),
            "reset_in": int(60 - (now - self.rate_limits[user_id][0])) if self.rate_limits[user_id] else 0
        }
    
    def reset_rate_limit(self, user_id: int):
        """Сбрасывает лимит запросов для пользователя"""
        if user_id in self.rate_limits:
            self.rate_limits[user_id] = []
        
        if user_id in self.failed_attempts:
            self.failed_attempts[user_id] = 0
    
    def record_failed_attempt(self, user_id: int, action: str):
        """Записывает неудачную попытку действия"""
        if user_id not in self.failed_attempts:
            self.failed_attempts[user_id] = 0
        
        self.failed_attempts[user_id] += 1
        
        # Логируем аудит
        self._log_audit(user_id, action, "FAILED")
    
    def record_successful_attempt(self, user_id: int, action: str):
        """Записывает успешную попытку действия"""
        if user_id in self.failed_attempts:
            self.failed_attempts[user_id] = 0
        
        # Логируем аудит
        self._log_audit(user_id, action, "SUCCESS")
    
    def _log_audit(self, user_id: int, action: str, status: str):
        """Логирование аудита действий"""
        timestamp = datetime.now().isoformat()
        logger.info(f"[AUDIT] {timestamp} | User {user_id} | {action} | {status}")
    
    def check_wallet_limit(self, current_wallets_count: int, max_wallets: int = 10) -> Tuple[bool, str]:
        """Проверяет лимит кошельков на пользователя"""
        if current_wallets_count >= max_wallets:
            return False, f"❌ Лимит кошельков достигнут ({max_wallets} максимум)"
        
        remaining = max_wallets - current_wallets_count
        return True, f"✅ Можно добавить еще {remaining} кошельков"
    
    def sanitize_input(self, text: str) -> str:
        """Очищает пользовательский ввод от потенциально опасных символов"""
        # Удаляем потенциально опасные символы
        sanitized = re.sub(r'[<>"\'&]', '', text)
        
        # Ограничиваем длину
        if len(sanitized) > 1000:
            sanitized = sanitized[:1000]
        
        return sanitized
    
    def is_admin(self, user_id: int, admin_ids: List[int]) -> bool:
        """Проверяет, является ли пользователь администратором"""
        return user_id in admin_ids
    
    def get_security_report(self, user_id: int) -> Dict[str, any]:
        """Генерирует отчет о безопасности для пользователя"""
        rate_limit_info = self.get_rate_limit_info(user_id)
        failed_attempts = self.failed_attempts.get(user_id, 0)
        
        return {
            "rate_limit": rate_limit_info,
            "failed_attempts": failed_attempts,
            "last_reset": self.last_reset.get(user_id),
            "security_level": self._calculate_security_level(failed_attempts)
        }
    
    def _calculate_security_level(self, failed_attempts: int) -> str:
        """Рассчитывает уровень безопасности"""
        if failed_attempts == 0:
            return "🟢 ВЫСОКИЙ"
        elif failed_attempts <= 3:
            return "🟡 СРЕДНИЙ"
        else:
            return "🔴 НИЗКИЙ"


class InputSanitizer:
    """Санитайзер ввода"""
    
    @staticmethod
    def sanitize_wallet_input(text: str) -> Optional[str]:
        """Очищает ввод для адреса кошелька"""
        if not text:
            return None
        
        # Удаляем пробелы и приводим к нижнему регистру
        text = text.strip().lower()
        
        # Извлекаем адрес из URL
        if 'polymarket.com/@' in text:
            # Извлекаем username из URL
            match = re.search(r'polymarket\.com/@([a-zA-Z0-9_]+)', text)
            if match:
                return match.group(1)
        
        # Извлекаем hex-адрес
        match = re.search(r'0x[a-fA-F0-9]{40}', text)
        if match:
            return match.group(0)
        
        return None
