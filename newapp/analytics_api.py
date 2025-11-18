import httpx
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json


class PolymarketAnalyticsAPI:
    """Класс для получения актуальных данных аналитики из Polymarket API"""
    
    BASE_URL = "https://data-api.polymarket.com"
    
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
            return response.json()
        except Exception as e:
            self.logger.error(f"Ошибка получения данных рынка {market_id}: {e}")
            return None
    
    async def get_active_markets(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получает список активных рынков"""
        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/markets",
                params={"active": "true", "limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("markets", []) if isinstance(data, dict) else data
        except Exception as e:
            self.logger.error(f"Ошибка получения активных рынков: {e}")
            return []
    
    async def get_market_volume(self, market_id: str, days: int = 7) -> Dict[str, float]:
        """Получает объем торгов за период"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            response = await self.http_client.get(
                f"{self.BASE_URL}/markets/{market_id}/volume",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat()
                }
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Ошибка получения объема рынка {market_id}: {e}")
            return {"total_volume": 0.0, "daily_volume": {}}
    
    async def get_top_markets_by_volume(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает топ рынков по объему торгов"""
        try:
            markets = await self.get_active_markets(limit * 2)
            
            # Сортируем по объему и берем топ
            markets_with_volume = []
            for market in markets:
                volume_data = await self.get_market_volume(market.get("id", ""), days=1)
                total_volume = volume_data.get("total_volume", 0.0)
                
                markets_with_volume.append({
                    "id": market.get("id", ""),
                    "title": market.get("title", "Unknown Market"),
                    "volume": total_volume,
                    "liquidity": market.get("liquidity", 0.0),
                    "outcomes": market.get("outcomes", [])
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
            # Получаем позиции кошелька
            response = await self.http_client.get(
                f"{self.BASE_URL}/positions",
                params={"user": wallet_address, "sizeThreshold": 0}
            )
            response.raise_for_status()
            positions = response.json()
            
            if not positions:
                return {"total_value": 0.0, "markets": [], "pnl": 0.0}
            
            # Рассчитываем общую стоимость
            total_value = sum(float(pos.get("value", 0)) for pos in positions)
            total_pnl = sum(float(pos.get("cashPnl", 0)) for pos in positions)
            
            # Группируем по рынкам
            markets = {}
            for position in positions:
                market_id = position.get("marketId") or position.get("conditionId")
                if not market_id:
                    continue
                    
                if market_id not in markets:
                    markets[market_id] = {
                        "id": market_id,
                        "title": position.get("title") or position.get("marketTitle", "Unknown"),
                        "positions": [],
                        "total_value": 0.0,
                        "total_pnl": 0.0
                    }
                
                markets[market_id]["positions"].append(position)
                markets[market_id]["total_value"] += float(position.get("value", 0))
                markets[market_id]["total_pnl"] += float(position.get("cashPnl", 0))
            
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
            return {"total_value": 0.0, "markets": [], "pnl": 0.0}
    
    async def get_volatility_analysis(self, market_id: str, days: int = 30) -> Dict[str, Any]:
        """Анализ волатильности рынка"""
        try:
            # Получаем исторические данные цен
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            response = await self.http_client.get(
                f"{self.BASE_URL}/markets/{market_id}/prices",
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "interval": "1d"
                }
            )
            response.raise_for_status()
            price_data = response.json()
            
            if not price_data:
                return {"volatility": 0.0, "price_changes": [], "analysis": "Low"}
            
            # Рассчитываем волатильность
            prices = [float(entry.get("price", 0)) for entry in price_data if entry.get("price")]
            if len(prices) < 2:
                return {"volatility": 0.0, "price_changes": [], "analysis": "Low"}
            
            # Расчет стандартного отклонения
            avg_price = sum(prices) / len(prices)
            variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
            volatility = variance ** 0.5
            
            # Анализ уровня волатильности
            if volatility < 0.05:
                analysis = "Low"
            elif volatility < 0.15:
                analysis = "Medium"
            else:
                analysis = "High"
            
            return {
                "volatility": volatility,
                "price_changes": [prices[i] - prices[i-1] for i in range(1, len(prices))],
                "analysis": analysis,
                "price_range": {"min": min(prices), "max": max(prices)}
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа волатильности {market_id}: {e}")
            return {"volatility": 0.0, "price_changes": [], "analysis": "Unknown"}
    
    async def get_whale_activity(self, min_amount: float = 1000.0) -> List[Dict[str, Any]]:
        """Получает информацию о крупных сделках (китах)"""
        try:
            # Получаем последние крупные транзакции
            response = await self.http_client.get(
                f"{self.BASE_URL}/trades",
                params={
                    "min_amount": min_amount,
                    "limit": 20,
                    "sort": "desc"
                }
            )
            response.raise_for_status()
            trades = response.json()
            
            whale_trades = []
            for trade in trades:
                whale_trades.append({
                    "market_id": trade.get("marketId", ""),
                    "amount": float(trade.get("amount", 0)),
                    "price": float(trade.get("price", 0)),
                    "timestamp": trade.get("timestamp", ""),
                    "type": "Buy" if trade.get("isBuy", False) else "Sell"
                })
            
            return whale_trades[:10]  # Возвращаем топ 10
            
        except Exception as e:
            self.logger.error(f"Ошибка получения данных о китах: {e}")
            return []


class AnalyticsManager:
    """Менеджер для работы с аналитикой"""
    
    def __init__(self, analytics_api: PolymarketAnalyticsAPI, db):
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
