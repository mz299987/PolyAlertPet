import os
from aiohttp import web

async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")

async def start_health_server():
    """Запускаем health-сервер и возвращаем running server"""
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    
    port = int(os.getenv("PORT", "8000"))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Health-сервер запущен на порту {port}")
    
    return runner  # Возвращаем runner для корректного закрытия
