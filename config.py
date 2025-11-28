import os
from datetime import datetime

class Config:
    # Отримайте токен бота від @BotFather в Telegram
    BOT_TOKEN = "8390304087:AAF8jQ8S-ogWRLczhYzvmZ199Fvisuv6PN4"
    
    # Web Panel Configuration
    SECRET_KEY = "your-very-secure-secret-key-change-this-12345"
    HOST = "127.0.0.1"
    PORT = 5000
    DEBUG = True
    
    # Адміністратор у панелі
    ADMIN_USERNAME = "Repetsky"
    ADMIN_PASSWORD = "123456789"
    ADMIN_TELEGRAM_ID = 6585759419
    
    # Telegram Group Configuration
    TELEGRAM_GROUP_ID = -1002075742226
    DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1389309712587292895/U4XlbShRWBFSVK5gGTrgfWhVp4MT8OspJpdMK67EjY3O6Zzq51fTD_wdOynmmm0dBI9k"
    
    # Чат спілкування для логування
    LOG_CHANNEL_ID = -1002990760459
    
    # Database
    DATABASE_FILE = "shift_system.db"
    
    # Логін та Пароль у панелі
    WEB_USERS = {
    "arteml2": {
        "password": "qG6^cxA1)z",
        "telegram_id": 1584480423,
        "name": "S.M | \u0410\u0440\u0442\u0435\u043c \u041b\u0435\u0432\u0456\u043d"
    },
    "Repetsky": {
        "password": "1111",
        "telegram_id": 6585759419,
        "name": "\u0417\u0413\u0410 | \u0406\u043b\u043b\u044f \u0420\u0435\u043f\u0435\u0446\u044c\u043a\u0438\u0439"
    },
    "babych_nazar": {
        "password": "jH3$qhA7(g",
        "telegram_id": 5376871426,
        "name": "S.M | \u041d\u0430\u0437\u0430\u0440 \u0411\u0430\u0431\u043e\u0447\u043a\u0430"
    },
    "tgk_angel1": {
        "password": "dQ1!uR+zvL",
        "telegram_id": 1289978142,
        "name": "S.M | \u041c\u0430\u0440\u043a \u0412\u0430\u043a\u0430\u0440\u0447\u0443\u043a"
    },
    "Artem14091": {
        "password": "1111",
        "telegram_id": 1187014036,
        "name": "\u0413\u0410 | \u0410\u0440\u0442\u0435\u043c \u0411\u043e\u044f\u0440\u0441\u044c\u043a\u0438\u0439"
    },
    "almaz1619": {
        "password": "xY2*oaB6#l",
        "telegram_id": 2083499587,
        "name": "\u0417\u0413\u0410 | \u0414\u0430\u043d\u0438\u043b\u043e \u041b\u0443\u0431'\u044f\u043d\u043e\u0432"
    },
    "Test": {
        "password": "1111",
        "telegram_id": 6585759419,
        "name": "Test"
    }
}
    
    # Separate chats for notifications
    NOTIFICATIONS_CHAT_ID = -1002990760459
    LOGS_CHAT_ID = -1002990760459
    PUNISHMENTS_CHAT_ID = -1002990760459
    
    # Telegram Channel Configuration
    TELEGRAM_CHANNEL_ID = -1002075742226
    
    # Заблоковані IP адреси
    BANNED_IPS = []

