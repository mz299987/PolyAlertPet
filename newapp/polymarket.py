import httpx
import re
from typing import List, Dict, Any, Optional


class PolymarketAPI:
    """Класс для работы с Polymarket API"""
    
    BASE_URL = "https://data-api.polymarket.com"
    
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
    
    async def get_wallet_positions(self, address: str) -> List[Dict[str, Any]]:
        """Получает позиции кошелька"""
        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/positions",
                params={"user": address, "sizeThreshold": 0}
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return []
    
    async def get_wallet_value(self, address: str) -> Optional[float]:
        """Получает общую стоимость портфеля"""
        try:
            response = await self.http_client.get(
                f"{self.BASE_URL}/value",
                params={"user": address}
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return float(data[0].get("value", 0))
            return None
        except Exception:
            return None
    
    async def get_active_markets(self, address: str) -> List[Dict[str, Any]]:
        """Получает активные рынки (события) с группировкой"""
        positions = await self.get_wallet_positions(address)
        
        markets = {}
        for position in positions:
            market_id = position.get("marketId") or position.get("conditionId")
            if not market_id:
                continue
                
            if market_id not in markets:
                markets[market_id] = {
                    "id": market_id,
                    "title": position.get("title") or position.get("marketTitle") or "Unknown Market",
                    "positions": []
                }
            
            markets[market_id]["positions"].append(position)
        
        return list(markets.values())
    
    def extract_address_from_text(self, text: str) -> Optional[str]:
        """Извлекает адрес кошелька из текста"""
        # Поиск 0x-адреса
        match = re.search(r"0x[a-fA-F0-9]{40}", text)
        if match:
            return match.group(0)
        
        # Поиск в URL Polymarket
        match = re.search(r"polymarket\.com/@([^\s/]+)", text)
        if match:
            # Для простоты возвращаем username
            # В реальном приложении нужно парсить страницу для получения адреса
            return match.group(1)
            
        return None
    
    def format_position_info(self, position: Dict[str, Any]) -> str:
        """Форматирует информацию о позиции"""
        title = position.get("title") or position.get("marketTitle") or "Unknown"
        outcome = position.get("outcome") or "?"
        
        # Значение позиции
        value = float(position.get("value") or position.get("positionValue") or 0)
        
        # Прибыль/убыток
        cash_pnl = float(position.get("cashPnl") or 0)
        percent_pnl = float(position.get("percentPnl") or 0)
        
        # Форматирование знаков
        cash_sign = "+" if cash_pnl >= 0 else ""
        percent_sign = "+" if percent_pnl >= 0 else ""
        
        return f"{title} - {outcome} value {value:.2f} USDC ({cash_sign}{cash_pnl:.2f}$) - {percent_sign}{percent_pnl:.2f}%"
    
    def calculate_total_pnl(self, positions: List[Dict[str, Any]]) -> float:
        """Рассчитывает общий PnL"""
        total = 0.0
        for position in positions:
            total += float(position.get("cashPnl") or 0)
        return total