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
    
    analytics_manager = AnalyticsManager(analytics_api, db)
    portfolio_report = await analytics_manager.get_user_portfolio_report(user_id)
    
    if "error" in portfolio_report:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков.\nСначала добавьте кошелек в разделе '👛 Кошельки'"
        else:
            text = "❌ You don't have any wallets added.\nFirst add a wallet in the '👛 Wallets' section"
        
        await callback.message.edit_text(text)
        await callback.answer()
        return
    
    wallet_address = portfolio_report["wallet_address"]
    total_value = portfolio_report["total_value"]
    total_pnl = portfolio_report["total_pnl"]
    market_count = portfolio_report["market_count"]
    
    if language == "ru":
        text = f"📈 <b>Общее состояние портфеля</b>\n\n"
        text += f"👛 Кошелек: <code>{wallet_address}</code>\n"
        text += f"💰 Общая стоимость: <b>{total_value:.2f} USDC</b>\n"
        text += f"📊 Прибыль/убыток: <b>{total_pnl:+.2f} USDC</b>\n"
        text += f"🎯 Активных рынков: <b>{market_count}</b>\n\n"
        
        if total_pnl > 0:
            text += "✅ <b>Портфель в плюсе</b>\n"
        elif total_pnl < 0:
            text += "⚠️ <b>Портфель в минусе</b>\n"
        else:
            text += "⚖️ <b>Портфель на нуле</b>\n"
            
        text += f"\n🔄 Данные обновлены: {portfolio_report.get('timestamp', 'только что')}"
    else:
        text = f"📈 <b>Overall Portfolio Status</b>\n\n"
        text += f"👛 Wallet: <code>{wallet_address}</code>\n"
        text += f"💰 Total Value: <b>{total_value:.2f} USDC</b>\n"
        text += f"📊 PnL: <b>{total_pnl:+.2f} USDC</b>\n"
        text += f"🎯 Active Markets: <b>{market_count}</b>\n\n"
        
        if total_pnl > 0:
            text += "✅ <b>Portfolio in profit</b>\n"
        elif total_pnl < 0:
            text += "⚠️ <b>Portfolio in loss</b>\n"
        else:
            text += "⚖️ <b>Portfolio break-even</b>\n"
            
        text += f"\n🔄 Data updated: {portfolio_report.get('timestamp', 'just now')}"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "detailed_analytics")
async def detailed_analytics_handler(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
    """Детальная аналитика портфеля"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    analytics_manager = AnalyticsManager(analytics_api, db)
    analytics_data = await analytics_manager.get_detailed_analytics(user_id)
    
    if "error" in analytics_data:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков"
        else:
            text = "❌ You don't have any wallets added"
        
        await callback.message.edit_text(text)
        await callback.answer()
        return
    
    portfolio = analytics_data["portfolio"]
    volatility = analytics_data["volatility"]
    whale_activity = analytics_data["whale_activity"]
    
    if language == "ru":
        text = f"📊 <b>Детальная аналитика портфеля</b>\n\n"
        text += f"💰 Общая стоимость: <b>{portfolio['total_value']:.2f} USDC</b>\n"
        text += f"📈 Прибыль/убыток: <b>{portfolio['total_pnl']:+.2f} USDC</b>\n"
        text += f"🎯 Рынков: <b>{portfolio['market_count']}</b>\n\n"
        
        text += "<b>Топ рынки по объему:</b>\n"
        for i, market in enumerate(portfolio["markets"][:3], 1):
            text += f"{i}. {market['title'][:30]}... - {market['total_value']:.2f} USDC\n"
        
        text += "\n<b>Анализ волатильности:</b>\n"
        for market_id, vol_data in list(volatility.items())[:3]:
            market_title = next((m['title'] for m in portfolio['markets'] if m['id'] == market_id), "Unknown")
            analysis = vol_data.get('analysis', 'Unknown')
            text += f"• {market_title[:25]}... - {analysis}\n"
        
        text += f"\n🐳 Крупных сделок: <b>{len(whale_activity)}</b>\n"
        text += f"🔄 Обновлено: {analytics_data.get('timestamp', 'только что')}"
    else:
        text = f"📊 <b>Detailed Portfolio Analytics</b>\n\n"
        text += f"💰 Total Value: <b>{portfolio['total_value']:.2f} USDC</b>\n"
        text += f"📈 PnL: <b>{portfolio['total_pnl']:+.2f} USDC</b>\n"
        text += f"🎯 Markets: <b>{portfolio['market_count']}</b>\n\n"
        
        text += "<b>Top Markets by Volume:</b>\n"
        for i, market in enumerate(portfolio["markets"][:3], 1):
            text += f"{i}. {market['title'][:30]}... - {market['total_value']:.2f} USDC\n"
        
        text += "\n<b>Volatility Analysis:</b>\n"
        for market_id, vol_data in list(volatility.items())[:3]:
            market_title = next((m['title'] for m in portfolio['markets'] if m['id'] == market_id), "Unknown")
            analysis = vol_data.get('analysis', 'Unknown')
            text += f"• {market_title[:25]}... - {analysis}\n"
        
        text += f"\n🐳 Whale Trades: <b>{len(whale_activity)}</b>\n"
        text += f"🔄 Updated: {analytics_data.get('timestamp', 'just now')}"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "top_markets")
async def top_markets_handler(callback: CallbackQuery, analytics_api: PolymarketAnalyticsAPI):
    """Топ рынков по объему с актуальными данными"""
    language = "ru"  # Временная заглушка - нужно получить из базы
    
    analytics_manager = AnalyticsManager(analytics_api, None)
    top_markets_report = await analytics_manager.get_top_markets_report()
    
    top_markets = top_markets_report["top_markets"]
    
    if language == "ru":
        text = "🔥 <b>Топ рынков по объему торгов</b>\n\n"
        text += "<i>Актуальные данные с Polymarket API</i>\n\n"
        
        if not top_markets:
            text += "❌ Не удалось загрузить данные рынков\n"
            text += "Попробуйте позже или проверьте подключение"
        else:
            for i, market in enumerate(top_markets[:10], 1):
                volume = market.get('volume', 0)
                liquidity = market.get('liquidity', 0)
                title = market.get('title', 'Unknown Market')
                
                # Форматируем объем
                if volume >= 1000000:
                    volume_str = f"{volume/1000000:.1f}M"
                elif volume >= 1000:
                    volume_str = f"{volume/1000:.1f}K"
                else:
                    volume_str = f"{volume:.0f}"
                
                text += f"{i}. <b>{title[:35]}...</b>\n"
                text += f"   💰 Объем: ${volume_str} | 📊 Ликвидность: {liquidity:.0f} USDC\n\n"
            
            text += f"🔄 Всего рынков: <b>{len(top_markets)}</b>\n"
            text += f"⏰ Обновлено: {top_markets_report.get('timestamp', 'только что')}"
    else:
        text = "🔥 <b>Top Markets by Trading Volume</b>\n\n"
        text += "<i>Real-time data from Polymarket API</i>\n\n"
        
        if not top_markets:
            text += "❌ Failed to load market data\n"
            text += "Please try again later or check connection"
        else:
            for i, market in enumerate(top_markets[:10], 1):
                volume = market.get('volume', 0)
                liquidity = market.get('liquidity', 0)
                title = market.get('title', 'Unknown Market')
                
                # Format volume
                if volume >= 1000000:
                    volume_str = f"{volume/1000000:.1f}M"
                elif volume >= 1000:
                    volume_str = f"{volume/1000:.1f}K"
                else:
                    volume_str = f"{volume:.0f}"
                
                text += f"{i}. <b>{title[:35]}...</b>\n"
                text += f"   💰 Volume: ${volume_str} | 📊 Liquidity: {liquidity:.0f} USDC\n\n"
            
            text += f"🔄 Total Markets: <b>{len(top_markets)}</b>\n"
            text += f"⏰ Updated: {top_markets_report.get('timestamp', 'just now')}"
    
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(F.data == "volatility")
async def volatility_handler(callback: CallbackQuery, db: Database, analytics_api: PolymarketAnalyticsAPI):
    """Анализ волатильности портфеля"""
    user_id = callback.from_user.id
    language = await db.get_user_language(user_id)
    
    analytics_manager = AnalyticsManager(analytics_api, db)
    volatility_report = await analytics_manager.get_volatility_report(user_id)
    
    if "error" in volatility_report:
        if language == "ru":
            text = "❌ У вас нет добавленных кошельков"
        else:
            text = "❌ You don't have any wallets added"
        
        await callback.message.edit_text(text)
        await callback.answer()
        return
    
    volatility_data = volatility_report["volatility_report"]
    
    if language == "ru":
        text = "📉 <b>Анализ волатильности портфеля</b>\n\n"
        text += "<i>Расчет на основе ценовых колебаний за 30 дней</i>\n\n"
        
        if not volatility_data:
            text += "❌ Недостаточно данных для анализа"
        else:
            high_vol = []
            medium_vol = []
            low_vol = []
            
            for market_id, data in volatility_data.items():
                volatility = data.get("volatility", 0)
                analysis = data.get("analysis", "Unknown")
                
                if analysis == "High":
                    high_vol.append((data["title"], volatility))
                elif analysis == "Medium":
                    medium_vol.append((data["title"], volatility))
                else:
                    low_vol.append((data["title"], volatility))
            
            if high_vol:
                text += "⚠️ <b>Высокая волатильность:</b>\n"
                for title, vol in high_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
                text += "\n"
            
            if medium_vol:
                text += "🟡 <b>Средняя волатильность:</b>\n"
                for title, vol in medium_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
                text += "\n"
            
            if low_vol:
                text += "🟢 <b>Низкая волатильность:</b>\n"
                for title, vol in low_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
            
            text += f"\n📊 Всего проанализировано рынков: <b>{len(volatility_data)}</b>\n"
            text += f"🔄 Обновлено: {volatility_report.get('timestamp', 'только что')}"
    else:
        text = "📉 <b>Portfolio Volatility Analysis</b>\n\n"
        text += "<i>Based on 30-day price fluctuations</i>\n\n"
        
        if not volatility_data:
            text += "❌ Insufficient data for analysis"
        else:
            high_vol = []
            medium_vol = []
            low_vol = []
            
            for market_id, data in volatility_data.items():
                volatility = data.get("volatility", 0)
                analysis = data.get("analysis", "Unknown")
                
                if analysis == "High":
                    high_vol.append((data["title"], volatility))
                elif analysis == "Medium":
                    medium_vol.append((data["title"], volatility))
                else:
                    low_vol.append((data["title"], volatility))
            
            if high_vol:
                text += "⚠️ <b>High Volatility:</b>\n"
                for title, vol in high_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
                text += "\n"
            
            if medium_vol:
                text += "🟡 <b>Medium Volatility:</b>\n"
                for title, vol in medium_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
                text += "\n"
            
            if low_vol:
                text += "🟢 <b>Low Volatility:</b>\n"
                for title, vol in low_vol[:3]:
                    text += f"• {title[:25]}... - {vol:.3f}\n"
            
            text += f"\n📊 Total Markets Analyzed: <b>{len(volatility_data)}</b>\n"
            text += f"🔄 Updated: {volatility_report.get('timestamp', 'just now')}"
    
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
