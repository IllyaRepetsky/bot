# runner.py
import subprocess
import sys
import time
import os

def run_services():
    processes = []
    
    try:
        print("🚀 Запуск всіх сервісів...")
        
        # Запуск web_app.py
        print("📱 Запуск web_app.py...")
        web_process = subprocess.Popen([sys.executable, 'web_app.py'])
        processes.append(web_process)
        time.sleep(3)  # Чекаємо, поки веб-додаток запуститься
        
        # Запуск bot.py
        print("🤖 Запуск bot.py...")
        bot_process = subprocess.Popen([sys.executable, 'bot.py'])
        processes.append(bot_process)
        time.sleep(2)
        
        # Запуск ngrok
        print("🌐 Запуск ngrok...")
        ngrok_process = subprocess.Popen(['./ngrok', 'http', '5000'])
        processes.append(ngrok_process)
        
        print("✅ Всі сервіси запущено!")
        print("Натисніть Ctrl+C для зупинки")
        
        # Очікування завершення (або Ctrl+C)
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Зупинка сервісів...")
        for process in processes:
            process.terminate()
        print("✅ Всі сервіси зупинено")

if __name__ == "__main__":
    run_services()