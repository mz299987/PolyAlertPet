#!/usr/bin/env python3
"""
Главный файл приложения Polymarket Tracker
"""

import asyncio
import os
import sys

# Добавляем путь к модулям
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'newapp'))

from newapp.bot import main

if __name__ == "__main__":
    try:
        print("🚀 Запуск Polymarket Tracker...")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️ Приложение остановлено")
    except Exception as e:
        print(f"💥 Ошибка: {e}")
        sys.exit(1)