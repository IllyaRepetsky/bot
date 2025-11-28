from database import Database
from config import Config
from datetime import datetime, timedelta

def add_test_data():
    db = Database(Config.DATABASE_FILE)
    
    print("🔄 Додавання тестових даних...")
    
    # Додаємо тестових модераторів
    moderators = [
        (123456789, "test_moderator", "Тест Модератор"),
        (987654321, "moderator2", "Другий Модератор"),
    ]
    
    for user_id, username, first_name in moderators:
        db.add_moderator(user_id, username, first_name)
        print(f"✅ Додано модератора: {first_name}")
    
    # Додаємо тестових користувачів групи
    group_users = [
        (111111111, "user1", "Користувач 1"),
        (222222222, "user2", "Користувач 2"),
        (333333333, "user3", "Користувач 3"),
        (444444444, "admin_user", "Адмін Користувач", True),
        (555555555, "banned_user", "Заблокований Користувач"),
    ]
    
    for user_data in group_users:
        if len(user_data) == 3:
            user_id, username, first_name = user_data
            db.add_group_user(user_id, username, first_name)
            print(f"✅ Додано користувача: {first_name}")
        else:
            user_id, username, first_name, is_admin = user_data
            db.add_group_user(user_id, username, first_name, is_admin)
            print(f"✅ Додано адміна: {first_name}")
    
    # Додаємо тестові повідомлення
    for user_id, username, first_name, *_ in group_users:
        messages = [
            f"Привіт, це тестове повідомлення від {first_name}",
            f"Як справи? Це друге повідомлення",
            f"Дуже цікава система контролю змін!",
        ]
        
        for message in messages:
            db.add_group_message(user_id, message, 'sent')
    
    # Додаємо тестову зміну
    db.start_shift(123456789)
    
    print("\n✅ Тестові дані успішно додані!")
    print("📊 Перевірте веб-панель")

if __name__ == "__main__":
    add_test_data()