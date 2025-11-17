"""Модуль системы уведомлений для бота Polymarket
Оповещения о крупных сделках, изменениях портфеля и новых событиях
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from aiogram import Bot
import logging

logger = logging.getLogger(__name__)

class NotificationManager:
    """Менеджер уведомлений"""
    def __init__(self, bot: Bot, db, polymarket):
        self.bot = bot
        self.db = db
        self.polymarket = polymarket
        self.notification_cache: Dict[str, datetime] = {}
        self.last_portfolio_check: Dict[int, Dict[str, float]] = {}  # user_id: {address: value}
    
    async def send_notification(self, user_id: int, message: str, notification_type: str = "info"):
        """Отправляет уведомление пользователю"""
        try:
            # Проверяем кэш, чтобы избежать спама
            cache_key = f"{user_id}:{notification_type}:{hash(message)}"
            if cache_key in self.notification_cache:
                if datetime.now() - self.notification_cache[cache_key] < timedelta(minutes=5):
                    return False
            
            await self.bot.send_message(user_id, message)
            
            # Сохраняем в кэш
            self.notification_cache[cache_key] = datetime.now()
            
            logger.info(f"✅ Уведомление отправлено пользователю {user_id}: {notification_type}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления пользователю {user_id}: {e}")
            return False
    
    async def check_portfolio_changes(self, user_id: int):
        """Проверяет изменения портфеля пользователя"""
        try:
            wallets = await self.db.get_user_wallets(user_id)
            
            for wallet in wallets:
                address = wallet["address"]
                current_value = await self.polymarket.get_wallet_value(address)
                
                if current_value is None:
                    continue
                
                # Получаем предыдущее значение
                prev_value = self.last_portfolio_check.get(user_id, {}).get(address, 0)
                
                if prev_value > 0:  # Если есть предыдущее значение для сравнения
                    change = current_value - prev_value
                    change_percent = (change / prev_value) * 100 if prev_value > 0 else 0
                    
                    # Отправляем уведомление при значительных изменениях
                    if abs(change) > 100 or abs(change_percent) > 10:
                        wallet_name = wallet.get("name") or f"{address[:6]}...{address[-4:]}"
                        
                        if change > 0:
                            message = f"📈 <b>Рост портфеля</b>\n"
                            message += f"Кошелек: {wallet_name}\n"
                            message += f"Изменение: +{change:.2f} USDC (+{change_percent:.1f}%)"
                        else:
                            message = f"📉 <b>Снижение портфеля</b>\n"
                            message += f"Кошелек: {wallet_name}\n"
                            message += f"Изменение: {change:.2f} USDC ({change_percent:.1f}%)"
                        
                        await self.send_notification(user_id, message, "portfolio_change")
                
                # Обновляем кэш
                if user_id not in self.last_portfolio_check:
                    self.last_portfolio_check[user_id] = {}
                self.last_portfolio_check[user_id][address] = current_value
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки изменений портфеля для пользователя {user_id}: {e}")
    
    async def check_whale_trades(self, user_id: int, threshold: float = 1000.0):
        """Проверяет крупные сделки китов"""
        try:
            # Получаем только кошельки китов
            whale_wallets = [w for w in await self.db.get_user_wallets(user_id) if w["is_whale"]]
            
            for wallet in whale_wallets:
                address = wallet["address"]
                positions = await self.polymarket.get_wallet_positions(address)
                
                for position in positions:
                    # Проверяем размер позиции
                    value = float(position.get("value") or 0)
                    
                    if value >= threshold:
                        market_title = position.get("title") or position.get("marketTitle") or "Unknown"
                        outcome = position.get("outcome") or "?"
                        
                        wallet_name = wallet.get("name") or f"{address[:6]}...{address[-4:]}"
                        
                        message = f"🐳 <b>Крупная сделка кита</b>\n"
                        message += f"Кошелек: {wallet_name}\n"
                        message += f"Событие: {market_title}\n"
                        message += f"Исход: {outcome}\n"
                        message += f"Сумма: {value:.2f} USDC"
                        
                        await self.send_notification(user_id, message, "whale_trade")
                        
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сделок китов для пользователя {user_id}: {e}")
    
    async def send_group_notification(self, admin_ids: List[int], message: str, notification_type: str = "admin"):
        """Отправляет групповое уведомление администраторам"""
        success_count = 0
        
        for admin_id in admin_ids:
            if await self.send_notification(admin_id, message, notification_type):
                success_count += 1
        
        logger.info(f"📢 Групповое уведомление отправлено {success_count}/{len(admin_ids)} администраторам")
        return success_count
    
    async def background_monitoring(self, config):
        """Фоновая проверка уведомлений"""
        while True:
            try:
                # Очищаем старый кэш уведомлений
                self._cleanup_notification_cache()
                
                await asyncio.sleep(config.sync_interval)  # Интервал из конфигурации
                
            except Exception as e:
                logger.error(f"❌ Ошибка в фоновом мониторинге: {e}")
                await asyncio.sleep(60)  # Ждем минуту при ошибке
    
    def _cleanup_notification_cache(self):
        """Очищает старые записи из кэша уведомлений"""
        now = datetime.now()
        keys_to_remove = []
        
        for key, timestamp in self.notification_cache.items():
            if now - timestamp > timedelta(hours=1):  # Удаляем записи старше часа
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.notification_cache[key]
    
    async def send_welcome_notification(self, user_id: int, language: str = "ru"):
        """Отправляет приветственное уведомление"""
        if language == "ru":
            message = "👋 <b>Добро пожаловать в Polymarket Tracker!</b>\n\n"
            message += "Теперь вы будете получать уведомления о:\n"
            message += "• 📈 Изменениях портфеля\n"
            message += "• 🐳 Сделках китов (>$1000)\n"
            message += "• 🔥 Новых событиях\n\n"
            message += "Настройте уведомления в меню ⚙️ Настройки"
        else:
            message = "👋 <b>Welcome to Polymarket Tracker!</b>\n\n"
            message += "You will now receive notifications about:\n"
            message += "• 📈 Portfolio changes\n"
            message += "• 🐳 Whale trades (>$1000)\n"
            message += "• 🔥 New events\n\n"
            message += "Configure notifications in ⚙️ Settings menu"
        
        await self.send_notification(user_id, message, "welcome")
    
    async def send_error_notification(self, user_id: int, error_message: str, language: str = "ru"):
        """Отправляет уведомление об ошибке"""
        if language == "ru":
            message = f"⚠️ <b>Произошла ошибка</b>\n\n{error_message}\n\n"
            message += "Попробуйте позже или обратитесь в поддержку."
        else:
            message = f"⚠️ <b>An error occurred</b>\n\n{error_message}\n\n"
            message += "Please try again later or contact support."
        
        await self.send_notification(user_id, message, "error")

class BackgroundTasks:
    """Фоновые задачи для синхронизации"""
    
    def __init__(self, db, polymarket):
        self.db = db
        self.polymarket = polymarket
        self.is_running = False
    
    async def start(self):
        """Запуск фоновых задач"""
        self.is_running = True
        asyncio.create_task(self._sync_loop())
    
    async def stop(self):
        """Остановка фоновых задач"""
        self.is_running = False
    
    async def _sync_loop(self):
        """Цикл синхронизации"""
        while self.is_running:
            try:
                # Синхронизация каждые 5 минут
                await asyncio.sleep(300)
                await self._sync_data()
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)  # Пауза при ошибке
    
    async def _sync_data(self):
        """Синхронизация данных"""
        try:
            # Здесь будет логика синхронизации данных пользователей
            logger.info("Background sync started")
        except Exception as e:
            logger.error(f"Error syncing data: {e}")
