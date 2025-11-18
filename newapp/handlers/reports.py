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
async def overall_status_handler(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
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
    
    # Используем первый кошелек для анализа
    wallet_address = wallets[0]["address"]
    
    try:
        # Получаем данные портфеля
        portfolio_data = await analytics_api.get_portfolio_analysis(wallet_address)
        
        total_value = portfolio_data.get("total_value", 0.0)
        total_pnl = portfolio_data.get("total_pnl", 0.0)
        market_count = portfolio_data.get("market_count", 0)
        
        if language == "ru":
            text = f"📈 <b>Общее состояние портфеля</b>\n\n"
            text += f"👛 Кошелек: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n"
            text += f"💰 Общая стоимость: <b>{total_value:.2f} USDC</b>\n"
            text += f"📊 Прибыль/убыток: <b>{total_pnl:+.2f} USDC</b>\n"
            text += f"🎯 Активных рынков: <b>{market_count}</b>\n"
            text += f"🐳 Китов отслеживается: <b>{sum(1 for w in wallets if w.get('is_whale'))}</b>\n\n"
            
            if total_pnl > 0:
                text += "🟢 <b>Портфель в плюсе</b>"
            elif total_pnl < 0:
                text += "🔴 <b>Портфель в минусе</b>"
            else:
                text += "⚪ <b>Портфель на нуле</b>"
                
        else:
            text = f"📈 <b>Overall Portfolio Status</b>\n\n"
            text += f"👛 Wallet: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n"
            text += f"💰 Total Value: <b>{total_value:.2f} USDC</b>\n"
            text += f"📊 PnL: <b>{total_pnl:+.2f} USDC</b>\n"
            text += f"🎯 Active Markets: <b>{market_count}</b>\n"
            text += f"🐳 Whales tracked: <b>{sum(1 for w in wallets if w.get('is_whale'))}</b>\n\n"
            
            if total_pnl > 0:
                text += "🟢 <b>Portfolio in profit</b>"
            elif total_pnl < 0:
                text += "🔴 <b>Portfolio in loss</b>"
            else:
                text += "⚪ <b>Portfolio at break-even</b>"
                
    except Exception as e:
        logger.error(f"Ошибка получения данных портфеля: {e}")
        if language == "ru":
            text = f"📈 <b>Общее состояние портфеля</b>\n\n"
            text += f"👛 Кошелек: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n\n"
            text += "⚠️ <b>Временная ошибка подключения</b>\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = f"📈 <b>Overall Portfolio Status</b>\n\n"
            text += f"👛 Wallet: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n\n"
            text += "⚠️ <b>Temporary connection error</b>\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "detailed_analytics")
async def detailed_analytics_handler(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
    """Детальная аналитика портфеля"""
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
    
    # Используем первый кошелек для анализа
    wallet_address = wallets[0]["address"]
    
    try:
        # Получаем детальную аналитику
        portfolio_data = await analytics_api.get_portfolio_analysis(wallet_address)
        
        total_value = portfolio_data.get("total_value", 0.0)
        total_pnl = portfolio_data.get("total_pnl", 0.0)
        markets = portfolio_data.get("markets", [])
        
        if language == "ru":
            text = f"📊 <b>Детальная аналитика портфеля</b>\n\n"
            text += f"👛 Кошелек: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n"
            text += f"💰 Общая стоимость: <b>{total_value:.2f} USDC</b>\n"
            text += f"📊 Прибыль/убыток: <b>{total_pnl:+.2f} USDC</b>\n\n"
            text += f"🎯 <b>Топ рынков по стоимости:</b>\n\n"
            
            if markets:
                for i, market in enumerate(markets[:5], 1):
                    market_value = market.get("total_value", 0.0)
                    market_pnl = market.get("total_pnl", 0.0)
                    percentage = (market_value / total_value * 100) if total_value > 0 else 0
                    
                    text += f"{i}. {market.get('title', 'Unknown')[:30]}\n"
                    text += f"   💰 {market_value:.2f} USDC ({percentage:.1f}%)\n"
                    text += f"   📈 PnL: {market_pnl:+.2f} USDC\n\n"
            else:
                text += "📭 Нет активных позиций"
                
        else:
            text = f"📊 <b>Detailed Portfolio Analytics</b>\n\n"
            text += f"👛 Wallet: <code>{wallet_address[:10]}...{wallet_address[-6:]}</code>\n"
            text += f"💰 Total Value: <b>{total_value:.2f} USDC</b>\n"
            text += f"📊 PnL: <b>{total_pnl:+.2f} USDC</b>\n\n"
            text += f"🎯 <b>Top Markets by Value:</b>\n\n"
            
            if markets:
                for i, market in enumerate(markets[:5], 1):
                    market_value = market.get("total_value", 0.0)
                    market_pnl = market.get("total_pnl", 0.0)
                    percentage = (market_value / total_value * 100) if total_value > 0 else 0
                    
                    text += f"{i}. {market.get('title', 'Unknown')[:30]}\n"
                    text += f"   💰 {market_value:.2f} USDC ({percentage:.1f}%)\n"
                    text += f"   📈 PnL: {market_pnl:+.2f} USDC\n\n"
            else:
                text += "📭 No active positions"
                
    except Exception as e:
        logger.error(f"Ошибка получения детальной аналитики: {e}")
        if language == "ru":
            text = "📊 <b>Детальная аналитика портфеля</b>\n\n"
            text += "⚠️ <b>Временная ошибка подключения</b>\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = "📊 <b>Detailed Portfolio Analytics</b>\n\n"
            text += "⚠️ <b>Temporary connection error</b>\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.get_back_button(language))
    await callback.answer()


@router.callback_query(F.data == "top_markets")
async def top_markets_handler(callback: CallbackQuery, analytics_api: PolymarketAnalyticsAPI):
    """Топ рынков по объему с актуальными данными"""
    language = "ru"  # Временная заглушка для языка
    
    try:
        # Получаем топ рынков по объему
        top_markets = await analytics_api.get_top_markets_by_volume(10)
        
        if language == "ru":
            text = "🔥 <b>Топ рынков по объему торгов</b>\n\n"
            text += "📊 <i>Актуальные данные с Polymarket</i>\n\n"
            
            if top_markets:
                for i, market in enumerate(top_markets[:5], 1):
                    title = market.get("title", "Unknown Market")[:35]
                    volume = market.get("volume", 0)
                    
                    # Форматируем объем
                    if volume >= 1000000:
                        volume_text = f"${volume/1000000:.1f}M"
                    elif volume >= 1000:
                        volume_text = f"${volume/1000:.1f}K"
                    else:
                        volume_text = f"${volume:.0f}"
                    
                    text += f"{i}. <b>{title}</b>\n"
                    text += f"   💰 Объем: {volume_text}\n"
                    
                    # Добавляем коэффициенты исходов
                    outcomes = market.get("outcomes", [])
                    if outcomes:
                        for outcome in outcomes[:2]:  # Показываем первые 2 исхода
                            outcome_name = outcome.get("name", "Unknown")
                            outcome_percent = outcome.get("percent", 0)
                            text += f"   📊 {outcome_name}: {outcome_percent:.1f}%\n"
                    
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
            text = "🔥 <b>Top Markets by Trading Volume</b>\n\n"
            text += "📊 <i>Real-time data from Polymarket</i>\n\n"
            
            if top_markets:
                for i, market in enumerate(top_markets[:5], 1):
                    title = market.get("title", "Unknown Market")[:35]
                    volume = market.get("volume", 0)
                    
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
        logger.error(f"Ошибка получения топ рынков: {e}")
        if language == "ru":
            text = "🔥 <b>Топ рынков по объему торгов</b>\n\n"
            text += "❌ Ошибка подключения к API\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = "🔥 <b>Top Markets by Trading Volume</b>\n\n"
            text += "❌ API connection error\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.get_back_button(language))
    await callback.answer()


@router.callback_query(F.data == "volatility")
async def volatility_handler(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
    """Анализ волатильности портфеля"""
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
    
    # Используем первый кошелек для анализа
    wallet_address = wallets[0]["address"]
    
    try:
        # Получаем данные портфеля
        portfolio_data = await analytics_api.get_portfolio_analysis(wallet_address)
        markets = portfolio_data.get("markets", [])
        
        if language == "ru":
            text = "📉 <b>Анализ волатильности портфеля</b>\n\n"
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
            text = "📉 <b>Portfolio Volatility Analysis</b>\n\n"
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
        logger.error(f"Ошибка анализа волатильности: {e}")
        if language == "ru":
            text = "📉 <b>Анализ волатильности портфеля</b>\n\n"
            text += "⚠️ <b>Временная ошибка подключения</b>\n"
            text += "Попробуйте обновить данные через несколько минут"
        else:
            text = "📉 <b>Portfolio Volatility Analysis</b>\n\n"
            text += "⚠️ <b>Temporary connection error</b>\n"
            text += "Try refreshing data in a few minutes"
    
    await callback.message.edit_text(text, reply_markup=Keyboards.get_back_button(language))
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
