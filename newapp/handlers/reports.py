"""
Обработчики для отчетов и аналитики с актуальными данными
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import Dict, Any
import logging

from newapp.database import Database
from newapp.analytics_api import PolymarketAnalyticsAPI, AnalyticsManager
from newapp.keyboards import Keyboards

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "overall_status")
async def overall_status_handler(callback: CallbackQuery, db: Database):
    """Общее состояние портфеля с актуальными данными"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    # Получаем кошельки пользователя
    wallets = await db.get_user_wallets(user_id)
    if not wallets:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков.\nСначала добавьте кошелек в разделе '👛 Кошельки'"
        else:
            text = "❌ You don't have any wallets added.\nFirst add a wallet in the '👛 Wallets' section"
        
        await callback.message.edit_text(text)
        await callback.answer()
        return
    
    # Простая реализация - используем первый кошелек
    wallet_address = wallets[0]["address"]
    
    if language == "ru":
        text = f"📈 <b>Общее состояние портфеля</b>\n\n"
        text += f"👛 Кошелек: <code>{wallet_address}</code>\n"
        text += f"💰 Добавлено кошельков: <b>{len(wallets)}</b>\n"
        text += f"🐳 Китов отслеживается: <b>{sum(1 for w in wallets if w.get('is_whale'))}</b>\n\n"
        text += "ℹ️ Для получения детальной информации обновите данные кошелька"
    else:
        text = f"📈 <b>Overall Portfolio Status</b>\n\n"
        text += f"👛 Wallet: <code>{wallet_address}</code>\n"
        text += f"💰 Wallets added: <b>{len(wallets)}</b>\n"
        text += f"🐳 Whales tracked: <b>{sum(1 for w in wallets if w.get('is_whale'))}</b>\n\n"
        text += "ℹ️ Refresh wallet data for detailed information"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "detailed_analytics")
async def detailed_analytics_handler(callback: CallbackQuery, db: Database):
    """Детальная аналитика портфеля"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    if language == "ru":
        text = "📊 <b>Детальная аналитика портфеля</b>\n\n"
        text += "⚠️ Функция в разработке\n"
        text += "Скоро вы сможете получить детальную аналитику вашего портфеля"
    else:
        text = "📊 <b>Detailed Portfolio Analytics</b>\n\n"
        text += "⚠️ Feature in development\n"
        text += "Detailed portfolio analytics will be available soon"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "top_markets")
async def top_markets_handler(callback: CallbackQuery):
    """Топ рынков по объему с актуальными данными"""
    language = "ru"  # Временная заглушка
    
    if language == "ru":
        text = "🔥 <b>Топ рынков по объему торгов</b>\n\n"
        text += "⚠️ Функция в разработке\n"
        text += "Скоро вы сможете видеть актуальные данные о топ рынках"
    else:
        text = "🔥 <b>Top Markets by Trading Volume</b>\n\n"
        text += "⚠️ Feature in development\n"
        text += "Real-time market data will be available soon"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "volatility")
async def volatility_handler(callback: CallbackQuery, db: Database):
    """Анализ волатильности портфеля"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    if language == "ru":
        text = "📉 <b>Анализ волатильности портфеля</b>\n\n"
        text += "⚠️ Функция в разработке\n"
        text += "Скоро вы сможете анализировать волатильность вашего портфеля"
    else:
        text = "📉 <b>Portfolio Volatility Analysis</b>\n\n"
        text += "⚠️ Feature in development\n"
        text += "Portfolio volatility analysis will be available soon"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "back_to_reports")
async def back_to_reports_handler(callback: CallbackQuery, db: Database):
    """Возврат в меню отчетов"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    keyboard = Keyboards.get_reports_menu(language)
    
    if language == "ru":
        text = "📊 <b>Отчеты и аналитика</b>\n\nВыберите тип отчета:"
    else:
        text = "📊 <b>Reports & Analytics</b>\n\nChoose report type:"
    
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
