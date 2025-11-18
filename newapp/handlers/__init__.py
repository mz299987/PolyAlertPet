"""
Пакет обработчиков для бота Polymarket
"""

from .start import router as start_router
from .wallets import router as wallets_router
from .status import router as status_router
from .analytics import router as analytics_router
from .settings import router as settings_router
from .betting import router as betting_router
from .reports import router as reports_router

__all__ = [
    'start_router',
    'wallets_router', 
    'status_router',
    'analytics_router',
    'settings_router',
    'betting_router',
    'reports_router'
]
