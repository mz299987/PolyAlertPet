import re
from typing import Optional, List, Dict, Any

from . import core

DATA_API_BASE = "https://data-api.polymarket.com"

WALLET_REGEX = re.compile(r"0x[a-fA-F0-9]{40}", re.IGNORECASE)


def extract_wallet_address(text: str) -> Optional[str]:
    if not text:
        return None
    m = WALLET_REGEX.search(text)
    return m.group(0) if m else None


async def pm_get_positions(address: str) -> List[Dict[str, Any]]:
    assert core.http_client is not None
    resp = await core.http_client.get(
        f"{DATA_API_BASE}/positions",
        params={"user": address, "sizeThreshold": 0},
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


async def pm_get_value(address: str) -> Optional[float]:
    assert core.http_client is not None
    resp = await core.http_client.get(
        f"{DATA_API_BASE}/value",
        params={"user": address},
        timeout=20.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, list) and data:
        return float(data[0].get("value", 0.0))
    return None


async def pm_get_activity_trades(address: str, since_ts: Optional[int] = None) -> List[Dict[str, Any]]:
    assert core.http_client is not None
    params: Dict[str, Any] = {
        "user": address,
        "limit": 100,
        "type": "TRADE",
        "sortBy": "TIMESTAMP",
        "sortDirection": "DESC",
    }
    resp = await core.http_client.get(
        f"{DATA_API_BASE}/activity",
        params=params,
        timeout=20.0,
    )
    resp.raise_for_status()
    trades = resp.json()
    if since_ts is None:
        return trades
    return [t for t in trades if int(t.get("timestamp", 0)) > since_ts]


async def resolve_wallet_or_profile(text: str) -> Optional[str]:
    """
    Понимает:
    - 0x-адрес
    - ссылки с 0x (wallet/profile)
    - ссылки вида polymarket.com/@username (парсим страницу)
    """
    if not text:
        return None

    addr = extract_wallet_address(text)
    if addr:
        return addr

    m = re.search(
        r"(https?://)?(www\.)?polymarket\.com/@([A-Za-z0-9_\-\.]+)",
        text,
    )
    if not m:
        return None

    url = m.group(0)
    if not url.startswith("http"):
        url = "https://" + url

    assert core.http_client is not None
    try:
        resp = await core.http_client.get(url, timeout=20.0)
        resp.raise_for_status()
        html = resp.text
        addr_from_html = extract_wallet_address(html)
        return addr_from_html
    except Exception:
        return None
