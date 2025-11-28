import threading
import time
import signal
import sys
import os
from web_app import app, db

def run_web():
    """Запуск веб-приложения"""
    try:
        print("🌐 Запуск веб-панелі...")
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Помилка при запуску веб-панелі: {e}")

def signal_handler(sig, frame):
    """Обробник сигналів завершення"""
    print("\n🛑 Отримано сигнал завершення...")
    print("⏳ Завершення роботи всіх компонентів...")
    sys.exit(0)

if __name__ == "__main__":
    print("🚀 Запуск системи підтримки на Railway...")
    
    # Налаштовуємо обробник сигналів
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ініціалізація бази даних
    try:
        db.init_db()
        print("✅ База даних ініціалізована")
    except Exception as e:
        print(f"❌ Помилка ініціалізації БД: {e}")
    
    # На Railway запускаємо тільки веб-додаток
    print("🌐 Запуск веб-панелі...")
    
    # Отримуємо порт з змінної середовища Railway
    port = int(os.environ.get('PORT', 5000))
    host = '0.0.0.0'
    
    print(f"📍 Веб-панель запускається на {host}:{port}")
    
    try:
        # Запускаємо веб-приложение
        app.run(host=host, port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        print("\n🛑 Отримано Ctrl+C...")
        print("👋 До побачення!")
    except Exception as e:
        print(f"❌ Помилка: {e}")