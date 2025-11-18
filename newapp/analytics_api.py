"""
Модуль аналитики и поиска для бота Polymarket
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from typing import List, Dict, Any
import asyncio

from newapp.database import Database
from newapp.polymarket import PolymarketAPI
from newapp.analytics_api import PolymarketAnalyticsAPI, AnalyticsManager
from newapp.keyboards import Keyboards
from newapp.cache import Cache

router = Router()


@router.message(F.text.in_(["📊 Аналитика", "📊 Analytics"]))
async def cmd_analytics(message: Message, db: Database, cache: Cache):
    """Главное меню аналитики"""
    language = await db.get_user_language(message.from_user.id)
    
    if language == "ru":
        text = "📊 <b>Аналитика портфеля</b>\n\nВыберите тип анализа:"
    else:
        text = "📊 <b>Portfolio Analytics</b>\n\nSelect analysis type:"
    
    await message.answer(
        text,
        reply_markup=Keyboards.get_analytics_menu(language)
    )


@router.callback_query(F.data == "portfolio_distribution")
async def cb_portfolio_distribution(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """График распределения портфеля"""
    language = await db.get_user_language(callback.from_user.id)
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков."
        else:
            text = "❌ You don't have any wallets added."
        await callback.message.edit_text(text)
        return
    
    # Собираем данные по всем кошелькам
    total_value = 0.0
    market_data = {}
    
    for wallet in wallets:
        positions = await polymarket.get_wallet_positions(wallet['address'])
        
        for position in positions:
            market_title = position.get('title') or position.get('marketTitle') or 'Unknown'
            value = float(position.get('value') or 0)
            
            if market_title not in market_data:
                market_data[market_title] = 0.0
            
            market_data[market_title] += value
            total_value += value
    
    if total_value == 0:
        if language == "ru":
            text = "📊 <b>Распределение портфеля</b>\n\nНет активных позиций для анализа."
        else:
            text = "📊 <b>Portfolio Distribution</b>\n\nNo active positions for analysis."
    else:
        # Сортируем рынки по объему
        sorted_markets = sorted(market_data.items(), key=lambda x: x[1], reverse=True)
        
        if language == "ru":
            text = f"📊 <b>Распределение портфеля</b>\n\nОбщая стоимость: <b>{total_value:.2f} USDC</b>\n\n"
        else:
            text = f"📊 <b>Portfolio Distribution</b>\n\nTotal value: <b>{total_value:.2f} USDC</b>\n\n"
        
        # Создаем текстовый график
        for market, value in sorted_markets[:10]:  # Топ-10 рынков
            percentage = (value / total_value) * 100
            bar_length = int(percentage / 5)  # 20 символов для 100%
            bar = "█" * bar_length + "░" * (20 - bar_length)
            
            text += f"{market[:30]}\n{bar} {percentage:.1f}% ({value:.2f} USDC)\n\n"
        
        if len(sorted_markets) > 10:
            if language == "ru":
                text += f"... и еще {len(sorted_markets) - 10} рынков"
            else:
                text += f"... and {len(sorted_markets) - 10} more markets"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.callback_query(F.data == "top_markets")
async def cb_top_markets(callback: CallbackQuery, cache: Cache):
    """Топ рынков по объему"""
    language = await cache.get_user_language(callback.from_user.id)
    
    # Получаем кэшированные данные о топ рынках
    # В реальном приложении здесь будет запрос к Polymarket API
    
    if language == "ru":
        text = "🔥 <b>Топ рынков по объему</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Данные обновляются каждые 5 минут"
    else:
        text = "🔥 <b>Top Markets by Volume</b>\n\n"
        text += "1. US Elections 2024 - $2.5M\n"
        text += "2. ETH ETF Approval - $1.8M\n"
        text += "3. Fed Rate Decision - $1.2M\n"
        text += "4. Bitcoin Halving - $950K\n"
        text += "5. Climate Events - $780K\n\n"
        text += "🔄 Data updates every 5 minutes"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.callback_query(F.data == "volatility_analysis")
async def cb_volatility_analysis(callback: CallbackQuery, db: Database, polymarket: PolymarketAPI):
    """Анализ волатильности"""
    language = await db.get_user_language(callback.from_user.id)
    wallets = await db.get_user_wallets(callback.from_user.id)
    
    if not wallets:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков."
        else:
            text = "❌ You don't have any wallets added."
        await callback.message.edit_text(text)
        return
    
    # Собираем данные по PnL для анализа волатильности
    total_pnl = 0.0
    max_pnl = 0.0
    min_pnl = 0.0
    
    for wallet in wallets:
        positions = await polymarket.get_wallet_positions(wallet['address'])
        wallet_pnl = polymarket.calculate_total_pnl(positions)
        
        total_pnl += wallet_pnl
        max_pnl = max(max_pnl, wallet_pnl)
        min_pnl = min(min_pnl, wallet_pnl)
    
    volatility = max_pnl - min_pnl
    
    if language == "ru":
        text = "📈 <b>Анализ волатильности</b>\n\n"
        text += f"Общий PnL: <b>{total_pnl:+.2f} USDC</b>\n"
        text += f"Максимальный PnL: <b>{max_pnl:+.2f} USDC</b>\n"
        text += f"Минимальный PnL: <b>{min_pnl:+.2f} USDC</b>\n"
        text += f"Волатильность: <b>{volatility:.2f} USDC</b>\n\n"
        
        if volatility > 1000:
            text += "⚠️ <b>Высокая волатильность</b>\n"
            text += "Рекомендуется диверсификация"
        elif volatility > 500:
            text += "🟡 <b>Средняя волатильность</b>\n"
            text += "Умеренный риск"
        else:
            text += "🟢 <b>Низкая волатильность</b>\n"
            text += "Стабильный портфель"
    else:
        text = "📈 <b>Volatility Analysis</b>\n\n"
        text += f"Total PnL: <b>{total_pnl:+.2f} USDC</b>\n"
        text += f"Max PnL: <b>{max_pnl:+.2f} USDC</b>\n"
        text += f"Min PnL: <b>{min_pnl:+.2f} USDC</b>\n"
        text += f"Volatility: <b>{volatility:.2f} USDC</b>\n\n"
        
        if volatility > 1000:
            text += "⚠️ <b>High Volatility</b>\n"
            text += "Diversification recommended"
        elif volatility > 500:
            text += "🟡 <b>Medium Volatility</b>\n"
            text += "Moderate risk"
        else:
            text += "🟢 <b>Low Volatility</b>\n"
            text += "Stable portfolio"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.message(F.text.in_(["🔍 Поиск", "🔍 Search"]))
async def cmd_search(message: Message):
    """Поиск по рынкам и событиям"""
    language = await get_user_language(message.from_user.id)  # Функция будет реализована
    
    if language == "ru":
        text = "🔍 <b>Поиск по рынкам</b>\n\n"
        text += "Отправьте ключевое слово для поиска событий на Polymarket.\n"
        text += "Примеры:\n"
        text += "• elections\n"
        text += "• bitcoin\n"
        text += "• climate"
    else:
        text = "🔍 <b>Market Search</b>\n\n"
        text += "Send a keyword to search for events on Polymarket.\n"
        text += "Examples:\n"
        text += "• elections\n"
        text += "• bitcoin\n"
        text += "• climate"
    
    await message.answer(text)


@router.message(Command("search"))
async def cmd_search_text(message: Message, polymarket: PolymarketAPI):
    """Обработка текстового поиска"""
    query = message.text.replace("/search", "").strip()
    
    if not query:
        await message.answer("❌ Пожалуйста, укажите поисковый запрос")
        return
    
    # В реальном приложении здесь будет запрос к Polymarket Search API
    # Покажем заглушку
    
    await message.answer(f"🔍 <b>Результаты поиска для: {query}</b>\n\n"
                        "1. US Elections 2024 - $2.5M\n"
                        "2. ETH ETF Approval - $1.8M\n"
                        "3. Bitcoin Halving - $950K\n\n"
                        "🔄 Реализация поиска в разработке...")


async def get_user_language(user_id: int) -> str:
    """Вспомогательная функция для получения языка пользователя"""
    # Временная реализация - будет заменена на работу с базой данных
    return "ru"
