import os
import asyncio
from aiohttp import web

async def health(request: web.Request) -> web.Response:
    return web.Response(text="OK")

async def start_health_server():
    """Запускаем health-сервер в фоновом режиме"""
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    
    port = int(os.getenv("PORT", "8000"))
    
    # Запускаем в фоновом режиме
    async def run_server():
        try:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            print(f"✅ Health-сервер запущен на порту {port}")
            # Бесконечный цикл для поддержания сервера активным
            while True:
                await asyncio.sleep(3600)  # Спим 1 час
        except Exception as e:
            print(f"❌ Ошибка health-сервера: {e}")
    
    # Запускаем сервер в фоне
    asyncio.create_task(run_server())
