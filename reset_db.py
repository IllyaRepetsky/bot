from database import Database
from config import Config
import os

def reset_database():
    """Пересоздание базы данных"""
    if os.path.exists(Config.DATABASE_FILE):
        os.remove(Config.DATABASE_FILE)
        print(f"🗑️ Удален файл базы данных: {Config.DATABASE_FILE}")
    
    db = Database(Config.DATABASE_FILE)
    print("✅ База данных пересоздана")
    
    # Добавляем тестового оператора (замените на свои данные)
    db.add_operator(123456789, "admin", "Администратор")
    print("✅ Добавлен тестовый оператор")

if __name__ == "__main__":
    reset_database()