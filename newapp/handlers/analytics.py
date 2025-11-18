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


@router.callback_query(F.data == "top_markets_analytics")
async def cb_top_markets(callback: CallbackQuery, analytics_api: PolymarketAnalyticsAPI):
    """Топ рынков по объему с реальными данными"""
    language = "ru"  # Временная заглушка для языка
    
    try:
        # Получаем реальные данные с Polymarket API
        top_markets = await analytics_api.get_top_markets_by_volume(10)
        
        if language == "ru":
            text = "🔥 <b>Топ рынков по объему</b>\n\n"
            text += "<i>Актуальные данные с Polymarket</i>\n\n"
            
            if top_markets:
                for i, market in enumerate(top_markets[:5], 1):
                    title = market.get('title', 'Unknown Market')[:35]
                    volume = market.get('volume', 0)
                    
                    # Форматируем объем
                    if volume >= 1000000:
                        volume_text = f"${volume/1000000:.1f}M"
                    elif volume >= 1000:
                        volume_text = f"${volume/1000:.1f}K"
                    else:
                        volume_text = f"${volume:.0f}"
                    
                    text += f"{i}. <b>{title}</b>\n"
                    text += f"   💰 Объем: {volume_text}\n"
                    
                    # Добавляем информацию о ликвидности, если доступна
                    liquidity = market.get("liquidity", 0)
                    if liquidity > 0:
                        if liquidity >= 1000000:
                            liquidity_text = f"${liquidity/1000000:.1f}M"
                        elif liquidity >= 1000:
                            liquidity_text = f"${liquidity/1000:.1f}K"
                        else:
                            liquidity_text = f"${liquidity:.0f}"
                        text += f"   💧 Ликвидность: {liquidity_text}\n"
                    
                    text += "\n"
                
                text += "🔄 Данные обновлены в реальном времени"
            else:
                text += "❌ Не удалось загрузить данные рынков\n"
                text += "Попробуйте позже"
                
        else:
            text = "🔥 <b>Top Markets by Volume</b>\n\n"
            text += "<i>Real-time data from Polymarket</i>\n\n"
            
            if top_markets:
                for i, market in enumerate(top_markets[:5], 1):
                    title = market.get('title', 'Unknown Market')[:35]
                    volume = market.get('volume', 0)
                    
                    # Format volume
                    if volume >= 1000000:
                        volume_text = f"${volume/1000000:.1f}M"
                    elif volume >= 1000:
                        volume_text = f"${volume/1000:.1f}K"
                    else:
                        volume_text = f"${volume:.0f}"
                    
                    text += f"{i}. <b>{title}</b>\n"
                    text += f"   💰 Volume: {volume_text}\n"
                    
                    # Add liquidity info if available
                    liquidity = market.get("liquidity", 0)
                    if liquidity > 0:
                        if liquidity >= 1000000:
                            liquidity_text = f"${liquidity/1000000:.1f}M"
                        elif liquidity >= 1000:
                            liquidity_text = f"${liquidity/1000:.1f}K"
                        else:
                            liquidity_text = f"${liquidity:.0f}"
                        text += f"   💧 Liquidity: {liquidity_text}\n"
                    
                    text += "\n"
                
                text += "🔄 Data updated in real-time"
            else:
                text += "❌ Failed to load market data\n"
                text += "Please try again later"
                
    except Exception as e:
        print(f"Ошибка получения данных рынков: {e}")
        if language == "ru":
            text = "🔥 <b>Топ рынков по объему</b>\n\n"
            text += "❌ Ошибка подключения к API\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = "🔥 <b>Top Markets by Volume</b>\n\n"
            text += "❌ API connection error\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.callback_query(F.data == "volatility_analysis")
async def cb_volatility_analysis(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
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
    
    # Используем первый кошелек для анализа
    wallet_address = wallets[0]["address"]
    
    try:
        # Получаем данные портфеля
        portfolio_data = await analytics_api.get_portfolio_analysis(wallet_address)
        markets = portfolio_data.get("markets", [])
        
        if language == "ru":
            text = "📈 <b>Анализ волатильности</b>\n\n"
            text += f"👛 Кошелек: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n\n"
            
            if markets:
                text += "📊 <b>Волатильность по рынкам:</b>\n\n"
                
                for i, market in enumerate(markets[:3], 1):
                    market_id = market.get("id", "")
                    market_title = market.get("title", "Unknown")[:30]
                    
                    # Получаем анализ волатильности для рынка
                    volatility_data = await analytics_api.get_volatility_analysis(market_id)
                    volatility = volatility_data.get("volatility", 0.0)
                    analysis = volatility_data.get("analysis", "Unknown")
                    
                    # Определяем эмодзи для уровня волатильности
                    if analysis == "High":
                        emoji = "🔴"
                        level_text = "Высокая"
                    elif analysis == "Medium":
                        emoji = "🟡"
                        level_text = "Средняя"
                    else:
                        emoji = "🟢"
                        level_text = "Низкая"
                    
                    text += f"{i}. {market_title}\n"
                    text += f"   {emoji} Волатильность: {volatility:.3f} ({level_text})\n\n"
                
                text += "ℹ️ Волатильность измеряется стандартным отклонением цен"
            else:
                text += "📭 Нет активных позиций для анализа волатильности"
                
        else:
            text = "📈 <b>Volatility Analysis</b>\n\n"
            text += f"👛 Wallet: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n\n"
            
            if markets:
                text += "📊 <b>Market Volatility:</b>\n\n"
                
                for i, market in enumerate(markets[:3], 1):
                    market_id = market.get("id", "")
                    market_title = market.get("title", "Unknown")[:30]
                    
                    # Get volatility analysis for market
                    volatility_data = await polymarket.get_volatility_analysis(market_id)
                    volatility = volatility_data.get("volatility", 0.0)
                    analysis = volatility_data.get("analysis", "Unknown")
                    
                    # Determine emoji for volatility level
                    if analysis == "High":
                        emoji = "🔴"
                        level_text = "High"
                    elif analysis == "Medium":
                        emoji = "🟡"
                        level_text = "Medium"
                    else:
                        emoji = "🟢"
                        level_text = "Low"
                    
                    text += f"{i}. {market_title}\n"
                    text += f"   {emoji} Volatility: {volatility:.3f} ({level_text})\n\n"
                
                text += "ℹ️ Volatility measured by standard deviation of prices"
            else:
                text += "📭 No active positions for volatility analysis"
                
    except Exception as e:
        print(f"Ошибка анализа волатильности: {e}")
        if language == "ru":
            text = "📈 <b>Анализ волатильности</b>\n\n"
            text += "❌ Ошибка подключения к API\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = "📈 <b>Volatility Analysis</b>\n\n"
            text += "❌ API connection error\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(
        text,
        reply_markup=Keyboards.get_back_button(language)
    )
    await callback.answer()


@router.message(F.text.in_(["🔍 Поиск", "🔍 Search"]))
async def cmd_search(message: Message, db: Database):
    """Поиск по рынкам и событиям"""
    language = await db.get_user_language(message.from_user.id)
    
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
async def cmd_search_text(message: Message, polymarket: PolymarketAnalyticsAPI, db: Database):
    """Обработка текстового поиска"""
    query = message.text.replace("/search", "").strip()
    language = await db.get_user_language(message.from_user.id)
    
    if not query:
        if language == "ru":
            await message.answer("❌ Пожалуйста, укажите поисковый запрос")
        else:
            await message.answer("❌ Please provide a search query")
        return
    
    try:
        # Получаем активные рынки и фильтруем по запросу
        active_markets = await polymarket.get_active_markets(50)
        
        matching_markets = []
        for market in active_markets:
            title = market.get("title", "").lower()
            if query.lower() in title:
                matching_markets.append(market)
        
        if language == "ru":
            text = f"🔍 <b>Результаты поиска для: {query}</b>\n\n"
            
            if matching_markets:
                for i, market in enumerate(matching_markets[:5], 1):
                    title = market.get("title", "Unknown Market")[:35]
                    volume = market.get("volume", 0) or market.get("volume24h", 0)
                    
                    # Форматируем объем
                    if volume >= 1000000:
                        volume_text = f"${volume/1000000:.1f}M"
                    elif volume >= 1000:
                        volume_text = f"${volume/1000:.1f}K"
                    else:
                        volume_text = f"${volume:.0f}"
                    
                    text += f"{i}. <b>{title}</b>\n"
                    text += f"   💰 Объем: {volume_text}\n\n"
                
                if len(matching_markets) > 5:
                    text += f"... и еще {len(matching_markets) - 5} результатов"
            else:
                text += "❌ По вашему запросу ничего не найдено\n"
                text += "Попробуйте изменить запрос"
                
        else:
            text = f"🔍 <b>Search results for: {query}</b>\n\n"
            
            if matching_markets:
                for i, market in enumerate(matching_markets[:5], 1):
                    title = market.get("title", "Unknown Market")[:35]
                    volume = market.get("volume", 0) or market.get("volume24h", 0)
                    
                    # Format volume
                    if volume >= 1000000:
                        volume_text = f"${volume/1000000:.1f}M"
                    elif volume >= 1000:
                        volume_text = f"${volume/1000:.1f}K"
                    else:
                        volume_text = f"${volume:.0f}"
                    
                    text += f"{i}. <b>{title}</b>\n"
                    text += f"   💰 Volume: {volume_text}\n\n"
                
                if len(matching_markets) > 5:
                    text += f"... and {len(matching_markets) - 5} more results"
            else:
                text += "❌ No results found for your query\n"
                text += "Try modifying your search"
                
    except Exception as e:
        print(f"Ошибка поиска: {e}")
        if language == "ru":
            text = f"🔍 <b>Результаты поиска для: {query}</b>\n\n"
            text += "❌ Ошибка при выполнении поиска\n"
            text += "Попробуйте позже"
        else:
            text = f"🔍 <b>Search results for: {query}</b>\n\n"
            text += "❌ Search error occurred\n"
            text += "Please try again later"
    
    await message.answer(text)


async def get_user_language(user_id: int) -> str:
    """Вспомогательная функция для получения языка пользователя"""
    # Временная реализация - будет заменена на работу с базой данных
    return "ru"
