import httpx
import re
from typing import List, Dict, Any, Optional


class PolymarketAPI:
    """Класс для работы с Polymarket API"""
    
    BASE_URL = "https://data-api.polymarket.com"
    
    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client
    
    async def get_wallet_positions(self, address: str) -> List[Dict[str, Any]]:
        """Получает позиции кошелька с ретраями"""
        import asyncio
        
        for attempt in range(3):  # 3 попытки
            try:
                # Используем актуальный API эндпоинт для получения позиций
                response = await self.http_client.get(
                    f"{self.BASE_URL}/positions",
                    params={"user": address, "sizeThreshold": 0, "includeClosed": "false"},
                    headers={"User-Agent": "PolymarketTrackerBot/1.0"},
                    timeout=15.0  # Увеличиваем таймаут
                )
                response.raise_for_status()
                data = response.json()
                
                # Проверяем структуру ответа
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and 'positions' in data:
                    return data['positions']
                else:
                    return []
            except Exception as e:
                if attempt == 2:  # Последняя попытка
                    print(f"Ошибка получения позиций для {address}: {e}")
                    return []
                await asyncio.sleep(2)  # Ждем перед повторной попыткой
    
    async def get_wallet_value(self, address: str) -> Optional[float]:
        """Получает общую стоимость портфеля"""
        try:
            # Используем более надежный эндпоинт для получения стоимости
            response = await self.http_client.get(
                f"{self.BASE_URL}/value",
                params={"user": address, "currency": "USDC"},
                headers={"User-Agent": "PolymarketTrackerBot/1.0"}
            )
            response.raise_for_status()
            data = response.json()
            
            # Обрабатываем разные форматы ответа
            if isinstance(data, list) and data:
                return float(data[0].get("value", 0))
            elif isinstance(data, dict):
                return float(data.get("value", 0))
            return None
        except Exception as e:
            print(f"Ошибка получения стоимости для {address}: {e}")
            return None
    
    async def get_active_markets(self, address: str) -> List[Dict[str, Any]]:
        """Получает активные рынки (события) с группировкой"""
        positions = await self.get_wallet_positions(address)
        
        markets = {}
        for position in positions:
            market_id = position.get("marketId") or position.get("conditionId")
            if not market_id:
                continue
                
            # Проверяем, что позиция активна (не закрыта)
            if position.get("isClosed") or position.get("closed"):
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
