import httpx
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json


class PolymarketAnalyticsAPI:
    """Класс для получения актуальных данных аналитики из Polymarket API"""
    
    BASE_URL = "https://gamma-api.polymarket.com"
    
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
        self.logger = logging.getLogger(__name__)
    
    async def get_market_data(self, market_id: str) -> Optional[Dict[str, Any]]:
        """Получает актуальные данные по рынку"""
        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/markets/{market_id}"
            )
            response.raise_for_status()
            market_data = response.json()
            
            # Нормализуем название рынка
            if isinstance(market_data, dict):
                title = (market_data.get("title") or 
                        market_data.get("question") or 
                        market_data.get("name") or 
                        market_data.get("marketTitle") or 
                        "Unknown Market")
                market_data["normalized_title"] = title
                
            return market_data
        except Exception as e:
            self.logger.error(f"Ошибка получения данных рынка {market_id}: {e}")
            return None
    
    async def get_active_markets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает список активных рынков с реальными коэффициентами"""
        try:
            # Используем актуальный API для получения рынков
            response = await self.http_client.get(
                f"{self.BASE_URL}/markets",
                params={
                    "limit": limit,
                    "sort": "volume",
                    "active": "true",
                    "includeClosed": "false"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # Обрабатываем разные форматы ответа
            if isinstance(data, list):
                markets = data
            elif isinstance(data, dict) and 'markets' in data:
                markets = data['markets']
            elif isinstance(data, dict) and 'data' in data:
                markets = data['data']
            elif isinstance(data, dict) and 'results' in data:
                markets = data['results']
            else:
                markets = []
            
            # Обрабатываем каждый рынок для получения детальной информации
            processed_markets = []
            for market in markets[:limit]:
                market_id = market.get("id") or market.get("conditionId") or market.get("marketId")
                if not market_id:
                    continue
                    
                # Получаем детальную информацию по рынку
                detailed_data = await self.get_market_data(market_id)
                if detailed_data:
                    market.update(detailed_data)
                
                processed_markets.append(market)
            
            return processed_markets
                
        except Exception as e:
            self.logger.error(f"Ошибка получения активных рынков: {e}")
            return []

        except Exception as e:
            self.logger.error(f"Ошибка получения активных рынков: {e}")
            return []

    async def get_market_volume(self, market_id: str, days: int = 7) -> Dict[str, float]:
        """Получает объем торгов за период"""
        try:
            # Получаем данные рынка, которые могут содержать объем
            market_data = await self.get_market_data(market_id)

            if not market_data:
                return {"total_volume": 0.0, "daily_volume": {}}
            
            # Извлекаем объем из данных рынка
            volume = market_data.get("volume", 0) or market_data.get("volume24h", 0) or market_data.get("totalVolume", 0)
            
            return {
                "total_volume": float(volume or 0),
                "daily_volume": {
                    datetime.now().strftime("%Y-%m-%d"): float(volume or 0)
                }
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения объема рынка {market_id}: {e}")
            return {"total_volume": 0.0, "daily_volume": {}}
    
    async def get_top_markets_by_volume(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает топ рынков по объему торгов"""
        try:
            # Получаем активные рынки с сортировкой по объему
            markets = await self.get_active_markets(limit * 2)
            
            if not markets:
                return []
            
            # Сортируем по объему и берем топ
            markets_with_volume = []
            for market in markets:
                # Извлекаем объем из данных рынка
                volume = market.get("volume", 0) or market.get("volume24h", 0) or market.get("totalVolume", 0) or market.get("volumeUSD", 0)
                
                # Извлекаем название рынка из разных возможных полей
                title = (market.get("title") or 
                        market.get("question") or 
                        market.get("name") or 
                        market.get("marketTitle") or 
                        "Unknown Market")
                
                markets_with_volume.append({
                    "id": market.get("id", "") or market.get("conditionId", "") or market.get("marketId", ""),
                    "title": title,
                    "volume": float(volume or 0),
                    "liquidity": float(market.get("liquidity", 0) or market.get("totalLiquidity", 0) or market.get("liquidityUSD", 0) or 0),
                    "outcomes": market.get("outcomes", []),
                    "url": market.get("url", ""),
                    "category": market.get("category", ""),
                    "endDate": market.get("endDate", "")
                })
            
            # Сортируем по объему в убывающем порядке
            markets_with_volume.sort(key=lambda x: x["volume"], reverse=True)
            return markets_with_volume[:limit]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения топ рынков: {e}")
            return []
    
    async def get_portfolio_analysis(self, wallet_address: str) -> Dict[str, Any]:
        """Анализ портфеля кошелька"""
        try:
            # Получаем позиции кошелька с использованием API позиций
            response = await self.http_client.get(
                f"{self.BASE_URL}/positions",
                params={"user": wallet_address}
            )
            
            if response.status_code == 200:
                positions = response.json()
            else:
                # Если API позиций не работает, используем альтернативный подход
                positions = []
            
            if not positions:
                return {"total_value": 0.0, "markets": [], "pnl": 0.0, "market_count": 0}
            
            # Рассчитываем общую стоимость и PnL
            total_value = 0.0
            total_pnl = 0.0
            
            # Группируем по рынкам
            markets = {}
            for position in positions:
                market_id = position.get("marketId") or position.get("conditionId")
                if not market_id:
                    continue
                    
                # Получаем значение позиции
                value = float(position.get("value", 0) or position.get("positionValue", 0) or 0)
                pnl = float(position.get("cashPnl", 0) or position.get("pnl", 0) or 0)
                
                total_value += value
                total_pnl += pnl
                
                if market_id not in markets:
                    markets[market_id] = {
                        "id": market_id,
                        "title": position.get("title") or position.get("marketTitle", "Unknown"),
                        "positions": [],
                        "total_value": 0.0,
                        "total_pnl": 0.0
                    }
                
                markets[market_id]["positions"].append(position)
                markets[market_id]["total_value"] += value
                markets[market_id]["total_pnl"] += pnl
            
            # Сортируем рынки по стоимости
            sorted_markets = sorted(markets.values(), key=lambda x: x["total_value"], reverse=True)
            
            return {
                "total_value": total_value,
                "total_pnl": total_pnl,
                "market_count": len(sorted_markets),
                "markets": sorted_markets
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа портфеля {wallet_address}: {e}")
            return {"total_value": 0.0, "markets": [], "pnl": 0.0, "market_count": 0}
    
    async def get_volatility_analysis(self, market_id: str, days: int = 30) -> Dict[str, Any]:
        """Анализ волатильности рынка"""
        try:
            # Получаем данные рынка
            market_data = await self.get_market_data(market_id)
            
            if not market_data:
                return {"volatility": 0.0, "price_changes": [], "analysis": "Low"}
            
            # Получаем текущие цены исходов
            outcomes = market_data.get("outcomes", [])
            
            if not outcomes:
                return {"volatility": 0.0, "price_changes": [], "analysis": "Low"}
            
            # Извлекаем цены исходов
            prices = []
            for outcome in outcomes:
                price = outcome.get("price", 0) or outcome.get("lastPrice", 0)
                if price:
                    prices.append(float(price))
            
            if len(prices) < 2:
                return {"volatility": 0.0, "price_changes": [], "analysis": "Low"}
            
            # Расчет стандартного отклонения
            avg_price = sum(prices) / len(prices)
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            volatility = variance ** 0.5
            
            # Анализ уровня волатильности
            if volatility > 0.3:
                analysis = "High"
            elif volatility > 0.15:
                analysis = "Medium"
            else:
                analysis = "Low"
            
            return {
                "volatility": volatility,
                "price_changes": [],
                "analysis": analysis,
                "price_range": {"min": min(prices) if prices else 0, "max": max(prices) if prices else 0}
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа волатильности {market_id}: {e}")
            return {"volatility": 0.0, "price_changes": [], "analysis": "Unknown"}
    
    async def get_whale_activity(self, min_amount: float = 1000.0) -> List[Dict[str, Any]]:
        """Получает информацию о крупных сделках (китах)"""
        try:
            # Получаем активные рынки
            markets = await self.get_active_markets(20)
            
            whale_trades = []
            
            # Для каждого рынка получаем информацию о крупных сделках
            for market in markets[:10]:  # Ограничиваем для производительности
                market_id = market.get("id", "")
                
                # Получаем последние сделки по рынку
                try:
                    response = await self.http_client.get(
                        f"{self.BASE_URL}/markets/{market_id}/trades",
                        params={"limit": 10}
                    )
                    
                    if response.status_code == 200:
                        trades = response.json()
                        
                        for trade in trades:
                            amount = float(trade.get("amount", 0) or trade.get("quantity", 0))
                            
                            # Фильтруем крупные сделки
                            if amount >= min_amount:
                                whale_trades.append({
                                    "market_id": market_id,
                                    "market_title": market.get("title", "Unknown"),
                                    "amount": amount,
                                    "price": float(trade.get("price", 0)),
                                    "timestamp": trade.get("timestamp", ""),
                                    "type": "Buy" if trade.get("isBuy", False) else "Sell"
                                })
                                
                except Exception:
                    continue
            
            # Сортируем по размеру сделки
            whale_trades.sort(key=lambda x: x["amount"], reverse=True)
            return whale_trades[:10]  # Возвращаем топ 10
            
        except Exception as e:
            self.logger.error(f"Ошибка получения данных о китах: {e}")
            return []


class AnalyticsManager:
    """Менеджер для работы с аналитикой"""
    
    def __init__(self, analytics_api, db):
        self.analytics_api = analytics_api
        self.db = db
        self.logger = logging.getLogger(__name__)
    
    async def get_user_portfolio_report(self, user_id: int) -> Dict[str, Any]:
        """Получает отчет по портфелю пользователя"""
        wallets = await self.db.get_user_wallets(user_id)
        if not wallets:
            return {"error": "No wallets found"}
        
        # Анализируем первый кошелек
        wallet_address = wallets[0]["address"]
        portfolio_data = await self.analytics_api.get_portfolio_analysis(wallet_address)
        
        return {
            "wallet_address": wallet_address,
            "total_value": portfolio_data["total_value"],
            "total_pnl": portfolio_data["total_pnl"],
            "market_count": portfolio_data["market_count"],
            "markets": portfolio_data["markets"][:5]  # Топ 5 рынков
        }
    
    async def get_detailed_analytics(self, user_id: int) -> Dict[str, Any]:
        """Получает детальную аналитику"""
        wallets = await self.db.get_user_wallets(user_id)
        if not wallets:
            return {"error": "No wallets found"}
        
        wallet_address = wallets[0]["address"]
        portfolio_data = await self.analytics_api.get_portfolio_analysis(wallet_address)
        
        # Получаем данные по волатильности для основных рынков
        volatility_data = {}
        for market in portfolio_data["markets"][:3]:  # Топ 3 рынка
            vol_data = await self.analytics_api.get_volatility_analysis(market["id"])
            volatility_data[market["id"]] = vol_data
        
        # Получаем информацию о китах
        whale_activity = await self.analytics_api.get_whale_activity()
        
        return {
            "portfolio": portfolio_data,
            "volatility": volatility_data,
            "whale_activity": whale_activity,
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_top_markets_report(self) -> Dict[str, Any]:
        """Получает отчет по топ рынкам"""
        top_markets = await self.analytics_api.get_top_markets_by_volume(10)
        
        # Добавляем анализ волатильности для топ рынков
        for market in top_markets[:5]:
            vol_data = await self.analytics_api.get_volatility_analysis(market["id"])
            market["volatility"] = vol_data
        
        return {
            "top_markets": top_markets,
            "total_count": len(top_markets),
            "timestamp": datetime.now().isoformat()
        }
    
    async def get_volatility_report(self, user_id: int) -> Dict[str, Any]:
        """Получает отчет по волатильности"""
        wallets = await self.db.get_user_wallets(user_id)
        if not wallets:
            return {"error": "No wallets found"}
        
        wallet_address = wallets[0]["address"]
        portfolio_data = await self.analytics_api.get_portfolio_analysis(wallet_address)
        
        volatility_report = {}
        for market in portfolio_data["markets"]:
            vol_data = await self.analytics_api.get_volatility_analysis(market["id"])
            volatility_report[market["id"]] = {
                "title": market["title"],
                "volatility": vol_data["volatility"],
                "analysis": vol_data["analysis"],
                "price_range": vol_data.get("price_range", {})
            }
        
        return {
            "volatility_report": volatility_report,
            "timestamp": datetime.now().isoformat()
        }
