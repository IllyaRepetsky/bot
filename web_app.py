from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from config import Config
from database import Database
import secrets
import string
from datetime import datetime, timedelta
import logging
import requests
import json
import os
import re
from user_ban_system import init_user_ban_system, is_user_banned, ban_user_account, unban_user_account

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Ініціалізація системи блокування акаунтів
init_user_ban_system(app)

db = Database(Config.DATABASE_FILE)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_real_ip():
    """Отримати реальну IP адресу клієнта, навіть через ngrok"""
    # Список заголовків, де може бути реальний IP (через проксі/ngrok)
    headers_to_check = [
        'X-Real-IP',
        'X-Forwarded-For', 
        'X-Forwarded',
        'Forwarded-For',
        'Forwarded',
        'CF-Connecting-IP',  # CloudFlare
        'X-Original-Forwarded-For'  # Додатковий для ngrok
    ]
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # Якщо X-Forwarded-For містить список IP, беремо перший (клієнтський)
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            if ip and ip != 'unknown':
                logger.info(f"Знайдено IP з заголовка {header}: {ip}")
                return ip
    
    # Якщо не знайшли в заголовках, повертаємо стандартний
    real_ip = request.remote_addr
    logger.info(f"Використання стандартного IP: {real_ip}")
    return real_ip
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # Якщо X-Forwarded-For містить список IP, беремо перший
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            if ip and ip != 'unknown':
                logger.info(f"Знайдено IP з заголовка {header}: {ip}")
                return ip
    
    # Якщо не знайшли в заголовках, повертаємо стандартний
    real_ip = request.remote_addr
    logger.info(f"Використання стандартного IP: {real_ip}")
    return real_ip

def load_banned_ips():
    """Завантажити список заблокованих IP з конфігурації"""
    try:
        if hasattr(Config, 'BANNED_IPS'):
            return Config.BANNED_IPS
        return []
    except:
        return []

def save_banned_ips(ips):
    """Зберегти список заблокованих IP"""
    try:
        # Оновлюємо конфігурацію
        Config.BANNED_IPS = ips
        
        # Зберігаємо у файл config.py
        config_content = f'''import os
from datetime import datetime

class Config:
    # Отримайте токен бота від @BotFather в Telegram
    BOT_TOKEN = "{Config.BOT_TOKEN}"
    
    # Web Panel Configuration
    SECRET_KEY = "{Config.SECRET_KEY}"
    HOST = "{Config.HOST}"
    PORT = {Config.PORT}
    DEBUG = {Config.DEBUG}
    
    # Адміністратор у панелі
    ADMIN_USERNAME = "{Config.ADMIN_USERNAME}"
    ADMIN_PASSWORD = "{Config.ADMIN_PASSWORD}"
    ADMIN_TELEGRAM_ID = {Config.ADMIN_TELEGRAM_ID}
    
    # Telegram Group Configuration
    TELEGRAM_GROUP_ID = {Config.TELEGRAM_GROUP_ID}
    DISCORD_WEBHOOK_URL = "{Config.DISCORD_WEBHOOK_URL}"
    
    # Чат спілкування для логування
    LOG_CHANNEL_ID = {Config.LOG_CHANNEL_ID}
    
    # Database
    DATABASE_FILE = "{Config.DATABASE_FILE}"
    
    # Логін та Пароль у панелі
    WEB_USERS = {json.dumps(Config.WEB_USERS, indent=4)}
    
    # Separate chats for notifications
    NOTIFICATIONS_CHAT_ID = {Config.NOTIFICATIONS_CHAT_ID}
    LOGS_CHAT_ID = {Config.LOGS_CHAT_ID}
    PUNISHMENTS_CHAT_ID = {Config.PUNISHMENTS_CHAT_ID}
    
    # Telegram Channel Configuration
    TELEGRAM_CHANNEL_ID = {Config.TELEGRAM_CHANNEL_ID}
    
    # Заблоковані IP адреси
    BANNED_IPS = {json.dumps(ips, indent=4)}
'''
        
        with open('config.py', 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        logger.info(f"Список заблокованих IP оновлено: {ips}")
        return True
    except Exception as e:
        logger.error(f"Помилка збереження IP: {e}")
        return False

def add_banned_ip(ip_address):
    """Додати IP до списку заблокованих"""
    banned_ips = load_banned_ips()
    if ip_address not in banned_ips:
        banned_ips.append(ip_address)
        return save_banned_ips(banned_ips)
    return True

def remove_banned_ip(ip_address):
    """Видалити IP зі списку заблокованих"""
    banned_ips = load_banned_ips()
    if ip_address in banned_ips:
        banned_ips.remove(ip_address)
        return save_banned_ips(banned_ips)
    return True

def is_ip_banned(ip_address):
    """Перевірити чи IP адреса знаходиться в чорному списку"""
    banned_ips = load_banned_ips()
    
    # Перевіряємо точне співпадіння
    if ip_address in banned_ips:
        return True
    
    # Перевіряємо підмережі (якщо вказані у форматі 192.168.1.*)
    for banned_ip in banned_ips:
        if '*' in banned_ip:
            ip_prefix = banned_ip.replace('*', '')
            if ip_address.startswith(ip_prefix):
                return True
    
    return False

def generate_2fa_code() -> str:
    characters = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(characters) for _ in range(10))

def send_2fa_code_direct(telegram_id: int, code: str):
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': telegram_id,
            'text': f"🔐 **Код підтвердження для входу в панель керування**\n\nВаш код: `{code}`\n\n⏰ Код дійсний 1 хвилину\n⚠️ Нікому не повідомляйте цей код!",
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки 2FA коду: {e}")
        return False

def send_discord_notification(message: str):
    try:
        if hasattr(Config, 'DISCORD_WEBHOOK_URL') and Config.DISCORD_WEBHOOK_URL:
            # Додаємо @everyone до повідомлення для Discord
            discord_message = f"@everyone {message}"
            payload = {"content": discord_message}
            response = requests.post(Config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            return response.status_code == 204
    except Exception as e:
        logger.error(f"Помилка відправки в Discord: {e}")
        return False
    return False

def send_telegram_group_notification(message: str):
    try:
        if hasattr(Config, 'TELEGRAM_GROUP_ID') and Config.TELEGRAM_GROUP_ID:
            url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': Config.TELEGRAM_GROUP_ID,
                'text': message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки в групу: {e}")
        return False

def send_telegram_channel_notification(message: str):
    """Надіслати повідомлення в Telegram канал через бота"""
    try:
        if hasattr(Config, 'TELEGRAM_CHANNEL_ID') and Config.TELEGRAM_CHANNEL_ID:
            url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
            payload = {
                'chat_id': Config.TELEGRAM_CHANNEL_ID,
                'text': message,
                'parse_mode': 'Markdown'
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки в канал: {e}")
        return False

def ban_user_in_telegram(user_id: int, reason: str) -> bool:
    """Заблокувати користувача в Telegram групі"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/banChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'revoke_messages': True
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"🚫 Користувача заблоковано\n"
                f"Причина: {reason}\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка блокування в Telegram: {response.text}")
            # Спробуємо видати тимчасове обмеження, якщо бан не працює
            return restrict_user_in_telegram(user_id, 8760)  # 1 рік
    except Exception as e:
        logger.error(f"Помилка блокування користувача в Telegram: {e}")
        return False

def unban_user_in_telegram(user_id: int) -> bool:
    """Розблокувати користувача в Telegram групі"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/unbanChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'only_if_banned': True
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"✅ Користувача розблоковано\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка розблокування в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Помилка розблокування користувача в Telegram: {e}")
        return False

def restrict_user_in_telegram(user_id: int, hours: int) -> bool:
    """Обмежити користувача в Telegram групі (мут)"""
    try:
        # Розраховуємо час закінчення муту
        until_date = int((datetime.now() + timedelta(hours=hours)).timestamp())
        
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/restrictChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'permissions': {
                'can_send_messages': False,
                'can_send_media_messages': False,
                'can_send_polls': False,
                'can_send_other_messages': False,
                'can_add_web_page_previews': False,
                'can_change_info': False,
                'can_invite_users': False,
                'can_pin_messages': False
            },
            'until_date': until_date
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"🔇 Користувач отримав обмеження\n"
                f"Тривалість: {hours} годин\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка обмеження в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Помилка обмеження користувача в Telegram: {e}")
        return False

def unrestrict_user_in_telegram(user_id: int) -> bool:
    """Зняти обмеження з користувача в Telegram групі"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/restrictChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'permissions': {
                'can_send_messages': True,
                'can_send_media_messages': True,
                'can_send_polls': True,
                'can_send_other_messages': True,
                'can_add_web_page_previews': True,
                'can_change_info': False,
                'can_invite_users': False,
                'can_pin_messages': False
            }
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"🔊 З користувача знято обмеження\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка зняття обмеження в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Помилка зняття обмеження в Telegram: {e}")
        return False

def promote_user_to_admin(user_id: int) -> bool:
    """Зробити користувача адміністратором в Telegram групі"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/promoteChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'can_change_info': True,
            'can_delete_messages': True,
            'can_invite_users': True,
            'can_restrict_members': True,
            'can_pin_messages': True,
            'can_promote_members': False
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"👑 Користувач отримав права адміністратора\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка надання прав адміна в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Помилка надання прав адміністратора: {e}")
        return False

def demote_user_from_admin(user_id: int) -> bool:
    """Забрати права адміністратора в Telegram групі"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/promoteChatMember"
        payload = {
            'chat_id': Config.TELEGRAM_GROUP_ID,
            'user_id': user_id,
            'can_change_info': False,
            'can_delete_messages': False,
            'can_invite_users': False,
            'can_restrict_members': False,
            'can_pin_messages': False,
            'can_promote_members': False
        }
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            send_telegram_group_notification(
                f"👤 З користувача знято права адміністратора\n"
                f"ID: {user_id}"
            )
            return True
        else:
            logger.error(f"Помилка зняття прав адміна в Telegram: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Помилка зняття прав адміністратора: {e}")
        return False

def log_action(action_type: str, action_details: str, user_agent: str = None):
    """Функція для логування дій з правильним IP"""
    try:
        username = session.get('username', 'anonymous')
        user_data = session.get('user_data', {})
        display_name = user_data.get('name', username)
        ip_address = get_real_ip()  # Використовуємо функцію для отримання реального IP
        
        db.add_action_log(
            user_id=username,
            username=display_name,
            action_type=action_type,
            action_details=action_details,
            ip_address=ip_address,
            user_agent=user_agent or request.headers.get('User-Agent')
        )
        
        # Відправка логу в Telegram
        log_message = f"📝 **Лог дії**\n\n👤 Користувач: {display_name}\n🔧 Дія: {action_type}\n📋 Деталі: {action_details}\n🌐 IP: {ip_address}\n⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        send_to_logs_chat(log_message)
        
    except Exception as e:
        logger.error(f"Помилка логування: {e}")

def send_to_notifications_chat(message: str):
    """Надіслати повідомлення в чат оповіщень"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': Config.NOTIFICATIONS_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки в чат оповіщень: {e}")
        return False

def send_to_logs_chat(message: str):
    """Надіслати повідомлення в чат логів"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': Config.LOGS_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки в чат логів: {e}")
        return False

def send_to_punishments_chat(message: str):
    """Надіслати повідомлення в чат покарань"""
    try:
        url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': Config.PUNISHMENTS_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Помилка відправки в чат покарань: {e}")
        return False

def punish_user_in_telegram(user_id: int, punishment_type: str, duration_hours: int = None, reason: str = "Порушення правил") -> bool:
    """
    Універсальна функція для покарань в Telegram
    punishment_type: 'ban' | 'mute'
    """
    try:
        if punishment_type == 'ban':
            return ban_user_in_telegram(user_id, reason)
        elif punishment_type == 'mute' and duration_hours:
            return restrict_user_in_telegram(user_id, duration_hours)
        else:
            logger.error(f"Невірний тип покарання: {punishment_type}")
            return False
    except Exception as e:
        logger.error(f"Помилка універсального покарання: {e}")
        return False

@app.before_request
def check_ip_ban():
    """Перевірка IP перед обробкою будь-якого запиту"""
    # Виключаємо статичні файли та сторінку бану
    if request.endpoint in ['static', 'ban_page']:
        return
    
    ip_address = get_real_ip()
    logger.info(f"Перевірка IP: {ip_address} для {request.endpoint}")
    
    if is_ip_banned(ip_address):
        logger.warning(f"Заблокований IP намагався отримати доступ: {ip_address} до {request.endpoint}")
        return render_template('ban.html'), 403

@app.before_request
def auto_ban_regular_users_on_logs():
    """Автоматичне блокування IP та акаунтів звичайних користувачів при доступі до логів"""
    # Вимкнути в режимі розробки
    if not getattr(Config, 'AUTO_BAN_ENABLED', True) or Config.DEBUG:
        return None
    
    # Перевіряємо чи це сторінка логів
    if request.endpoint == 'view_logs':
        if session.get('authenticated'):
            username = session.get('username')
            ip_address = get_real_ip()
            
            # Перевірка whitelist IP
            whitelist_ips = getattr(Config, 'WHITELIST_IPS', [])
            is_whitelisted = any(ip in ip_address for ip in whitelist_ips)
            
            if is_whitelisted:
                return None
            
            # СПИСОК АДМІНІСТРАТОРІВ - не блокувати цих користувачів
            admin_users = ['Repetsky', 'Artem14091']
            is_admin = username in admin_users
            
            if not is_admin:
                # Автоматичне блокування IP
                ip_success = add_banned_ip(ip_address)
                
                # Автоматичне блокування акаунту
                from user_ban_system import auto_ban_user_for_logs_access
                account_banned = auto_ban_user_for_logs_access(username, ip_address)
                
                if ip_success or account_banned:
                    log_action("auto_ip_and_account_ban", 
                              f"Автоматичне блокування IP {ip_address} та акаунту {username} за спробу доступу до логів",
                              request.headers.get('User-Agent', ''))
                    
                    # Відправляємо сповіщення
                    ban_message = (
                        f"🚫 **ПОВНЕ АВТОМАТИЧНЕ БЛОКУВАННЯ**\n\n"
                        f"👤 Користувач: {username}\n"
                        f"📡 IP: {ip_address}\n"
                        f"📋 Причина: Спроба доступу до сторінки логів\n"
                        f"🔒 Дії: Заблоковано IP та акаунт\n"
                        f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    )
                    send_to_punishments_chat(ban_message)
                    
                    # Очищаємо сесію
                    session.clear()
                    
                    # Перенаправляємо на сторінку бану акаунту
                    return redirect(url_for('ban_user_page'))
    
    return None

@app.before_request
def log_all_actions():
    """Логування всіх дій у системі з правильним IP"""
    if request.endpoint and request.endpoint != 'static' and request.endpoint != 'ban_page':
        user_agent = request.headers.get('User-Agent', '')
        
        # Логуємо доступ до сторінок
        if request.endpoint in ['dashboard', 'moderators', 'telegram_chat', 'banned', 'view_logs']:
            log_action(f"page_access_{request.endpoint}", f"Перегляд сторінки {request.endpoint}", user_agent)
        
        # Логуємо POST запити (дії)
        if request.method == 'POST':
            action_details = f"Метод: {request.endpoint}, Дані: {request.get_data()[:500]}"
            log_action(f"action_{request.endpoint}", action_details, user_agent)

# Сторінка бану
@app.route('/ban')
def get_real_ip():
    """Отримати реальну IP адресу клієнта, навіть через ngrok"""
    # Список заголовків, де може бути реальний IP (через проксі/ngrok)
    headers_to_check = [
        'X-Real-IP',
        'X-Forwarded-For', 
        'X-Forwarded',
        'Forwarded-For',
        'Forwarded',
        'CF-Connecting-IP',  # CloudFlare
        'X-Original-Forwarded-For'  # Додатковий для ngrok
    ]
    
    for header in headers_to_check:
        ip = request.headers.get(header)
        if ip:
            # Якщо X-Forwarded-For містить список IP, беремо перший (клієнтський)
            if ',' in ip:
                ip = ip.split(',')[0].strip()
            if ip and ip != 'unknown':
                logger.info(f"Знайдено IP з заголовка {header}: {ip}")
                return ip
    
    # Якщо не знайшли в заголовках, повертаємо стандартний
    real_ip = request.remote_addr
    logger.info(f"Використання стандартного IP: {real_ip}")
    return real_ip

# Маршрути авторизації
@app.route('/')
def index():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Перевіряємо IP перед логіном
    ip_address = get_real_ip()
    if is_ip_banned(ip_address):
        logger.warning(f"Заблокований IP намагався увійти: {ip_address}")
        return render_template('ban.html'), 403
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user_agent = request.headers.get('User-Agent', '')
        
        # Перевіряємо чи акаунт заблокований
        if is_user_banned(username):
            logger.warning(f"Заблокований акаунт намагався увійти: {username}")
            return redirect(url_for('ban_user_page'))
        
        if username in Config.WEB_USERS and Config.WEB_USERS[username]['password'] == password:
            code = generate_2fa_code()
            expires_at = datetime.now() + timedelta(minutes=1)
            
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO twofa_codes (code, telegram_id, expires_at) VALUES (?, ?, ?)',
                         (code, Config.WEB_USERS[username]['telegram_id'], expires_at.isoformat()))
            conn.commit()
            conn.close()
            
            success = send_2fa_code_direct(Config.WEB_USERS[username]['telegram_id'], code)
            
            if success:
                session['pending_2fa'] = True
                session['username'] = username
                session['user_data'] = Config.WEB_USERS[username]
                
                # Логування успішного входу
                log_action("login_success", f"Успішна спроба входу для {username}", user_agent)
                return redirect(url_for('twofa'))
            else:
                log_action("login_2fa_failed", f"Помилка відправки 2FA коду для {username}", user_agent)
                return render_template('login.html', error="Помилка відправки коду 2FA")
        else:
            # Логування невдалої спроби входу
            log_action("login_failed", f"Невірні облікові дані для {username}", user_agent)
            return render_template('login.html', error="Невірні облікові дані")
    
    # Логування доступу до сторінки входу
    log_action("page_access_login", "Перегляд сторінки входу", request.headers.get('User-Agent', ''))
    return render_template('login.html')

@app.route('/2fa', methods=['GET', 'POST'])
def twofa():
    if not session.get('pending_2fa'):
        return redirect(url_for('login'))
    
    user_agent = request.headers.get('User-Agent', '')
    
    if request.method == 'POST':
        code = request.form.get('code')
        user_data = session.get('user_data', {})
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM twofa_codes WHERE code = ? AND telegram_id = ? AND expires_at > ?',
                     (code, user_data.get('telegram_id'), datetime.now().isoformat()))
        
        code_data = cursor.fetchone()
        
        if code_data:
            session['authenticated'] = True
            session['pending_2fa'] = False
            session['login_time'] = datetime.now().isoformat()
            
            cursor.execute('DELETE FROM twofa_codes WHERE code = ?', (code,))
            conn.commit()
            conn.close()
            
            # Логування успішної 2FA
            log_action("2fa_success", f"Успішна 2FA аутентифікація для {session['username']}", user_agent)
            return redirect(url_for('dashboard'))
        else:
            conn.close()
            # Логування невдалої 2FA
            log_action("2fa_failed", f"Невірний код 2FA: {code} для {session['username']}", user_agent)
            return render_template('2fa.html', error="Невірний або прострочений код")
    
    # Логування доступу до сторінки 2FA
    log_action("page_access_2fa", "Перегляд сторінки 2FA", user_agent)
    return render_template('2fa.html')

# Головна сторінка
@app.route('/dashboard')
def dashboard():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    try:
        shifts = db.get_all_shifts()
        stats = db.get_stats()
        
        return render_template('dashboard.html', shifts=shifts, stats=stats)
    except Exception as e:
        logger.error(f"Помилка при завантаженні дашборду: {e}")
        return render_template('dashboard.html', shifts=[], stats={})

# Сторінка модераторів
@app.route('/moderators')
def moderators():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    try:
        moderators_data = db.get_all_moderators()
        shifts = db.get_all_shifts()
        
        # Отримуємо дані про покарання для кожного модератора
        moderators_with_penalties = []
        for moderator in moderators_data:
            penalties_summary = db.get_moderator_penalties_summary(moderator['user_id'])
            moderator['penalties_summary'] = penalties_summary
            moderators_with_penalties.append(moderator)
        
        return render_template('moderators.html', 
                             moderators=moderators_with_penalties, 
                             shifts=shifts)
    except Exception as e:
        logger.error(f"Помилка при завантаженні модераторів: {e}")
        return render_template('moderators.html', moderators=[], shifts=[])

# Сторінка Telegram чату
@app.route('/telegram_chat')
def telegram_chat():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    try:
        group_users = db.get_all_group_users()
        stats = db.get_stats()
        logger.info(f"Завантажено {len(group_users)} користувачів для Telegram чату")
        return render_template('telegram_chat.html', users=group_users, stats=stats)
    except Exception as e:
        logger.error(f"Помилка при завантаженні чату: {e}")
        return render_template('telegram_chat.html', users=[], stats={})

# Сторінка заблокованих
@app.route('/banned')
def banned():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    try:
        banned_users = db.get_banned_users()
        banned_ips = load_banned_ips()
        return render_template('banned.html', banned_users=banned_users, banned_ips=banned_ips)
    except Exception as e:
        logger.error(f"Помилка при завантаженні заблокованих: {e}")
        return render_template('banned.html', banned_users=[], banned_ips=[])

# Сторінка логів
@app.route('/logs')
def view_logs():
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    
    # Отримуємо дані користувача
    username = session.get('username')
    ip_address = get_real_ip()
    
    # Список адміністраторів
    admin_users = ['Repetsky', 'Artem14091']
    
    # Якщо користувач не адмін - блокуємо IP та АКАУНТ
    if username not in admin_users:
        # Whitelist для тестування
        whitelist_ips = [
            '127.0.0.1', 'localhost', '::1', '0.0.0.0',
            '172.17.0.1', '192.168.', '10.0.',
            'ngrok.io', 'ngrok-free.app', 'ngrok.com'
        ]
        
        # Перевіряємо чи IP в whitelist
        is_whitelisted = any(ip in ip_address for ip in whitelist_ips)
        
        if not is_whitelisted:
            # Блокуємо IP
            success = add_banned_ip(ip_address)
            if success:
                # АВТОМАТИЧНЕ БЛОКУВАННЯ АКАУНТУ
                from user_ban_system import auto_ban_user_for_logs_access
                account_banned = auto_ban_user_for_logs_access(username, ip_address)
                
                # Логуємо дію
                log_action("auto_ip_ban_and_account_ban", 
                          f"Автоматичне блокування IP {ip_address} та акаунту {username} за спробу доступу до логів",
                          request.headers.get('User-Agent', ''))
                
                # Відправляємо сповіщення в Telegram
                ban_message = (
                    f"🚫 **ПОВНЕ АВТОМАТИЧНЕ БЛОКУВАННЯ**\n\n"
                    f"👤 Користувач: {username}\n"
                    f"📡 IP: {ip_address}\n"
                    f"📋 Причина: Спроба доступу до сторінки логів\n"
                    f"🔒 Дії: Заблоковано IP та акаунт\n"
                    f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_to_punishments_chat(ban_message)
                
                # Очищаємо сесію і перенаправляємо на бан акаунту
                session.clear()
                return redirect(url_for('ban_user_page'))
    
    # Якщо адмін - показуємо логи
    try:
        action_logs = db.get_action_logs(limit=100)
        login_stats = db.get_login_stats(days=30)
        
        return render_template('logs.html', 
                             logs=action_logs, 
                             stats=login_stats,
                             total_logs=len(action_logs))
    except Exception as e:
        logger.error(f"Помилка при завантаженні логів: {e}")
        return render_template('logs.html', logs=[], stats={}, total_logs=0)

# API для оповіщень
@app.route('/api/send_notification', methods=['POST'])
def api_send_notification():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        notification_type = data.get('type')
        custom_message = data.get('custom_message')
        
        active_shifts = db.get_active_shifts()
        # Виправляємо відображення нікнеймів - використовуємо first_name замість username
        moderators_on_shift = [f"{shift['first_name']} (@{shift['username'] or 'без нікнейму'})" for shift in active_shifts]
        moderators_list = "\n".join(moderators_on_shift) if moderators_on_shift else "Немає модераторів на зміні"
        
        messages = {
            'low_moderators': f"\n⚠️УВАГА! Мало Модерації на стрімі\nМодератори на зміні:\n{moderators_list}",
            'stream_problem': "🔧Технічні проблеми зі стрімом\nНаразі пробуємо вирішити її\nОбов'язково зачиніть поки зміни!",
            'stream_started': "🎥Стрім Розпочатий! Приєднуємось на нього",
            'custom': custom_message
        }
        
        message = messages.get(notification_type)
        if message:
            # Відправка в Discord з @everyone
            discord_success = send_discord_notification(message)
            
            # Відправка в Telegram канал
            telegram_success = send_telegram_channel_notification(message)
            
            # Логування
            log_action("notification_sent", 
                      f"Тип: {notification_type}, Discord: {discord_success}, Telegram: {telegram_success}",
                      request.headers.get('User-Agent', ''))
            
            return jsonify({
                'success': True, 
                'discord_sent': discord_success,
                'telegram_sent': telegram_success
            })
        else:
            return jsonify({'success': False, 'error': 'Invalid notification type'})
            
    except Exception as e:
        logger.error(f"Помилка відправки сповіщення: {e}")
        return jsonify({'success': False, 'error': str(e)})

# API для керування модераторами
@app.route('/api/add_moderator', methods=['POST'])
def api_add_moderator():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        username = data.get('username')
        first_name = data.get('first_name')
        
        db.add_moderator(user_id, username, first_name)
        log_action("moderator_added", f"ID: {user_id}, Ім'я: {first_name}", request.headers.get('User-Agent', ''))
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка додавання модератора: {e}")
        log_action("moderator_add_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/remove_moderator/<int:user_id>', methods=['POST'])
def api_remove_moderator(user_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        db.remove_moderator(user_id)
        log_action("moderator_removed", f"ID: {user_id}", request.headers.get('User-Agent', ''))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка видалення модератора: {e}")
        log_action("moderator_remove_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

# API для отримання інформації про модератора
@app.route('/api/get_moderator_info/<int:user_id>')
def api_get_moderator_info(user_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        moderator = db.get_moderator(user_id)
        if not moderator:
            return jsonify({'error': 'Moderator not found'}), 404
        
        shifts = db.get_moderator_shifts(user_id)
        penalties_summary = db.get_moderator_penalties_summary(user_id)
        
        return jsonify({
            'moderator': moderator,
            'shifts': shifts,
            'penalties_summary': penalties_summary
        })
    except Exception as e:
        logger.error(f"Помилка отримання інформації про модератора: {e}")
        return jsonify({'error': str(e)}), 500

# API для керування користувачами групи
@app.route('/api/ban_user', methods=['POST'])
def api_ban_user():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        reason = data.get('reason', 'Рішення адміністратора')
        
        db.ban_user(user_id, reason, session['username'])
        log_action("user_banned", f"ID: {user_id}, Причина: {reason}", request.headers.get('User-Agent', ''))
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка блокування користувача: {e}")
        log_action("user_ban_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unban_user', methods=['POST'])
def api_unban_user():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        
        db.unban_user(user_id)
        log_action("user_unbanned", f"ID: {user_id}", request.headers.get('User-Agent', ''))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка розблокування користувача: {e}")
        log_action("user_unban_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mute_user', methods=['POST'])
def api_mute_user():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        hours = data.get('hours', 1)
        
        mute_until = (datetime.now() + timedelta(hours=hours)).isoformat()
        db.mute_user(user_id, mute_until)
        log_action("user_muted", f"ID: {user_id}, Годин: {hours}", request.headers.get('User-Agent', ''))
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка муту користувача: {e}")
        log_action("user_mute_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unmute_user', methods=['POST'])
def api_unmute_user():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        
        db.unmute_user(user_id)
        log_action("user_unmuted", f"ID: {user_id}", request.headers.get('User-Agent', ''))
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Помилка зняття муту: {e}")
        log_action("user_unmute_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/set_admin', methods=['POST'])
def api_set_admin():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        is_admin = data.get('is_admin', False)
        
        if is_admin:
            # Надаємо права адміністратора
            telegram_success = promote_user_to_admin(user_id)
        else:
            # Забираємо права адміністратора
            telegram_success = demote_user_from_admin(user_id)
        
        if telegram_success:
            # Оновлюємо базу даних
            db.set_user_admin(user_id, is_admin)
            action = "надано" if is_admin else "забрано"
            log_action("admin_rights_changed", f"ID: {user_id}, Дії: {action}", request.headers.get('User-Agent', ''))
            return jsonify({'success': True})
        else:
            action = "надати" if is_admin else "забрати"
            return jsonify({'success': False, 'error': f'Не вдалося {action} права адміністратора в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка зміни прав адміністратора: {e}")
        log_action("admin_rights_change_failed", f"Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

# API для керування користувачами чату через Telegram
@app.route('/api/ban_user_chat', methods=['POST'])
def api_ban_user_chat():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        reason = data.get('reason', 'Рішення адміністратора')
        banned_by = session.get('username', 'System')
        
        # Виконуємо бан в Telegram
        telegram_success = ban_user_in_telegram(user_id, reason)
        
        if telegram_success:
            # Оновлюємо базу даних
            db.ban_user(user_id, reason, banned_by)
            
            # Логування дії
            log_action("user_banned_chat", 
                      f"ID: {user_id}, Причина: {reason}, Заблоковав: {banned_by}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_message = (
                f"🚫 **Користувача заблоковано**\n\n"
                f"👤 ID: {user_id}\n"
                f"📝 Причина: {reason}\n"
                f"🔧 Виконав: {banned_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            log_action("user_ban_failed", 
                      f"ID: {user_id}, Причина: {reason} - Помилка Telegram",
                      request.headers.get('User-Agent', ''))
            return jsonify({'success': False, 'error': 'Не вдалося заблокувати користувача в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка блокування користувача в чаті: {e}")
        log_action("user_ban_error", 
                  f"ID: {user_id}, Помилка: {str(e)}",
                  request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unban_user_chat', methods=['POST'])
def api_unban_user_chat():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        
        # Виконуємо розбан в Telegram
        telegram_success = unban_user_in_telegram(user_id)
        
        if telegram_success:
            # Оновлюємо базу даних
            db.unban_user(user_id)
            log_action("user_unbanned_chat", f"ID: {user_id}", request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_message = f"✅ **Користувача розблоковано**\n\n👤 ID: {user_id}\n🔧 Виконав: {session['username']}\n⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося розблокувати користувача в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка розблокування користувача в чаті: {e}")
        log_action("user_unban_error", f"ID: {user_id}, Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mute_user_chat', methods=['POST'])
def api_mute_user_chat():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        hours = data.get('hours', 1)
        
        # Виконуємо мут в Telegram
        telegram_success = restrict_user_in_telegram(user_id, hours)
        
        if telegram_success:
            # Оновлюємо базу даних
            mute_until = (datetime.now() + timedelta(hours=hours)).isoformat()
            db.mute_user(user_id, mute_until)
            log_action("user_muted_chat", f"ID: {user_id}, Годин: {hours}", request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_message = f"🔇 **Користувач отримав мут**\n\n👤 ID: {user_id}\n⏱️ Тривалість: {hours} годин\n🔧 Виконав: {session['username']}\n⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося видати мут в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка муту користувача в чаті: {e}")
        log_action("user_mute_error", f"ID: {user_id}, Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unmute_user_chat', methods=['POST'])
def api_unmute_user_chat():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        
        # Виконуємо зняття муту в Telegram
        telegram_success = unrestrict_user_in_telegram(user_id)
        
        if telegram_success:
            # Оновлюємо базу даних
            db.unmute_user(user_id)
            log_action("user_unmuted_chat", f"ID: {user_id}", request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_message = f"🔊 **З користувача знято мут**\n\n👤 ID: {user_id}\n🔧 Виконав: {session['username']}\n⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося зняти мут в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка зняття муту в чаті: {e}")
        log_action("user_unmute_error", f"ID: {user_id}, Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/delete_user_data/<int:user_id>', methods=['POST'])
def api_delete_user_data(user_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        success = db.delete_user_data(user_id)
        if success:
            log_action("user_data_deleted", f"ID: {user_id}", request.headers.get('User-Agent', ''))
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося видалити дані'})
    except Exception as e:
        logger.error(f"Помилка видалення даних користувача: {e}")
        log_action("user_data_delete_error", f"ID: {user_id}, Помилка: {str(e)}", request.headers.get('User-Agent', ''))
        return jsonify({'success': False, 'error': str(e)})

# API для отримання інформації про користувача групи
@app.route('/api/get_group_user_info/<int:user_id>')
def api_get_group_user_info(user_id):
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        user_info = db.get_group_user_info(user_id)
        if not user_info:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'user': user_info,
            'messages': user_info.get('messages', [])
        })
    except Exception as e:
        logger.error(f"Помилка отримання інформації про користувача: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_group_users')
def api_get_group_users():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        users = db.get_all_group_users()
        logger.info(f"Завантажено {len(users)} користувачів з бази даних")
        return jsonify({'users': users})
    except Exception as e:
        logger.error(f"Помилка отримання користувачів групи: {e}")
        return jsonify({'error': str(e)}), 500

# API для отримання логів
@app.route('/api/get_logs')
def api_get_logs():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        limit = request.args.get('limit', 100, type=int)
        user_id = request.args.get('user_id')
        
        logs = db.get_action_logs(limit=limit, user_id=user_id)
        return jsonify({'logs': logs})
    except Exception as e:
        logger.error(f"Помилка отримання логів: {e}")
        return jsonify({'error': str(e)}), 500

# НОВІ API ДЛЯ ОНОВЛЕННИХ ФУНКЦІЙ

@app.route('/api/force_toggle_shift', methods=['POST'])
def api_force_toggle_shift():
    """Примусове відкриття/закриття зміни"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        moderator_id = data.get('moderator_id')
        action = data.get('action')  # 'open' або 'close'
        
        if action == 'open':
            # Примусово відкриваємо зміну
            shift_id = db.start_shift(moderator_id)
            if shift_id:
                log_action("shift_forced_open", 
                          f"Примусово відкрито зміну #{shift_id} для модератора {moderator_id}",
                          request.headers.get('User-Agent', ''))
                return jsonify({'success': True, 'message': 'Зміну примусово відкрито'})
            else:
                return jsonify({'success': False, 'error': 'Не вдалося відкрити зміну'})
        
        elif action == 'close':
            # Примусово закриваємо зміну
            success = db.end_shift(moderator_id)
            if success:
                log_action("shift_forced_close", 
                          f"Примусово закрито зміну для модератора {moderator_id}",
                          request.headers.get('User-Agent', ''))
                return jsonify({'success': True, 'message': 'Зміну примусово закрито'})
            else:
                return jsonify({'success': False, 'error': 'Не вдалося закрити зміну'})
        
        else:
            return jsonify({'success': False, 'error': 'Невірна дія'})
            
    except Exception as e:
        logger.error(f"Помилка примусового керування зміною: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/mute_user_with_reason', methods=['POST'])
def api_mute_user_with_reason():
    """Мут користувача з причиною та інформацією про того, хто видав"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        hours = data.get('hours', 1)
        reason = data.get('reason', 'Порушення правил')
        issued_by = session.get('username', 'Невідомо')
        
        # Виконуємо мут в Telegram
        telegram_success = restrict_user_in_telegram(user_id, hours)
        
        if telegram_success:
            # Оновлюємо базу даних
            mute_until = (datetime.now() + timedelta(hours=hours)).isoformat()
            db.mute_user(user_id, mute_until)
            
            # Логування з причиною та інформацією про того, хто видав
            log_action("user_muted_with_reason", 
                      f"ID: {user_id}, Годин: {hours}, Причина: {reason}, Видав: {issued_by}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань з детальною інформацією
            punishment_message = (
                f"🔇 **Користувач отримав мут**\n\n"
                f"👤 ID: {user_id}\n"
                f"⏱️ Тривалість: {hours} годин\n"
                f"📝 Причина: {reason}\n"
                f"🔧 Виконав: {issued_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося видати мут в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка муту з причиною: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/ban_user_with_reason', methods=['POST'])
def api_ban_user_with_reason():
    """Бан користувача з причиною та інформацією про того, хто видав"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        reason = data.get('reason', 'Порушення правил')
        banned_by = session.get('username', 'System')
        
        # Виконуємо бан в Telegram
        telegram_success = ban_user_in_telegram(user_id, reason)
        
        if telegram_success:
            # Оновлюємо базу даних
            db.ban_user(user_id, reason, banned_by)
            
            # Логування
            log_action("user_banned_with_reason", 
                      f"ID: {user_id}, Причина: {reason}, Видав: {banned_by}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_message = (
                f"🚫 **Користувача заблоковано**\n\n"
                f"👤 ID: {user_id}\n"
                f"📝 Причина: {reason}\n"
                f"🔧 Виконав: {banned_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося заблокувати користувача в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка бану з причиною: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/issue_penalty', methods=['POST'])
def api_issue_penalty():
    """Система штрафів, доган та попереджень"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        moderator_id = data.get('moderator_id')
        penalty_type = data.get('type')  # 'fine', 'warning', 'reprimand'
        value = data.get('value')
        reason = data.get('reason', '')
        issued_by = session.get('username', 'Невідомо')
        
        # Валідація значень
        if penalty_type == 'fine' and (value < 1 or value > 100):
            return jsonify({'success': False, 'error': 'Штраф має бути від 1 до 100%'})
        elif penalty_type == 'warning' and (value < 1 or value > 1):
            return jsonify({'success': False, 'error': 'Попередження може бути тільки 1'})
        elif penalty_type == 'reprimand' and (value < 1 or value > 3):
            return jsonify({'success': False, 'error': 'Догана може бути від 1 до 3'})
        
        # Додаємо покарання в базу даних
        success = db.add_penalty(moderator_id, penalty_type, value, reason, issued_by)
        
        if success:
            # Логування
            log_action("penalty_issued", 
                      f"Модератор: {moderator_id}, Тип: {penalty_type}, Значення: {value}, Причина: {reason}",
                      request.headers.get('User-Agent', ''))
            
            # Отримуємо інформацію про модератора для повідомлення
            moderator = db.get_moderator(moderator_id)
            if moderator:
                penalty_message = (
                    f"⚖️ **Видано покарання**\n\n"
                    f"👤 Модератор: {moderator.get('first_name', 'Невідомо')}\n"
                    f"📋 Тип: {get_penalty_type_name(penalty_type)}\n"
                    f"🔢 Значення: {value}\n"
                    f"📝 Причина: {reason}\n"
                    f"🔧 Виконав: {issued_by}\n"
                    f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_to_punishments_chat(penalty_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося видати покарання'})
            
    except Exception as e:
        logger.error(f"Помилка видачі покарання: {e}")
        return jsonify({'success': False, 'error': str(e)})

def get_penalty_type_name(penalty_type):
    """Отримати назву типу покарання"""
    names = {
        'fine': 'Штраф',
        'warning': 'Попередження',
        'reprimand': 'Догана'
    }
    return names.get(penalty_type, penalty_type)

@app.route('/api/punish_user', methods=['POST'])
def api_punish_user():
    """Універсальний ендпоінт для покарань"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        user_id = data.get('user_id')
        punishment_type = data.get('type')  # 'ban' або 'mute'
        duration = data.get('duration', 1)  # Для муту
        reason = data.get('reason', 'Порушення правил')
        issued_by = session.get('username', 'Невідомо')
        
        # Виконуємо покарання в Telegram
        telegram_success = punish_user_in_telegram(user_id, punishment_type, duration, reason)
        
        if telegram_success:
            # Оновлюємо базу даних
            if punishment_type == 'ban':
                db.ban_user(user_id, reason, issued_by)
            elif punishment_type == 'mute':
                mute_until = (datetime.now() + timedelta(hours=duration)).isoformat()
                db.mute_user(user_id, mute_until)
            
            # Логування
            log_action(f"user_{punishment_type}", 
                      f"ID: {user_id}, Тривалість: {duration}, Причина: {reason}, Видав: {issued_by}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка в чат покарань
            punishment_names = {
                'ban': 'заблоковано',
                'mute': 'отримав мут'
            }
            punishment_message = (
                f"{'🚫' if punishment_type == 'ban' else '🔇'} **Користувача {punishment_names.get(punishment_type, 'покарано')}**\n\n"
                f"👤 ID: {user_id}\n"
                f"{f'⏱️ Тривалість: {duration} годин\n' if punishment_type == 'mute' else ''}"
                f"📝 Причина: {reason}\n"
                f"🔧 Виконав: {issued_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(punishment_message)
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': f'Не вдалося виконати покарання в Telegram'})
            
    except Exception as e:
        logger.error(f"Помилка покарання: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_stats')
def api_get_stats():
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        stats = db.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"Помилка отримання статистики: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/update_penalty', methods=['POST'])
def api_update_penalty():
    """Оновити покарання модератора з системою сповіщень про зміни"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        moderator_id = data.get('moderator_id')
        penalty_type = data.get('type')  # 'fine', 'warning', 'reprimand'
        new_value = data.get('value')
        reason = data.get('reason', '')
        issued_by = session.get('username', 'Невідомо')
        
        # Валідація значень
        if penalty_type == 'fine' and (new_value < 0 or new_value > 100):
            return jsonify({'success': False, 'error': 'Штраф має бути від 0 до 100%'})
        elif penalty_type == 'warning' and (new_value < 0 or new_value > 1):
            return jsonify({'success': False, 'error': 'Попередження може бути тільки 0 або 1'})
        elif penalty_type == 'reprimand' and (new_value < 0 or new_value > 3):
            return jsonify({'success': False, 'error': 'Догана може бути від 0 до 3'})
        
        # Отримуємо поточний стан покарань
        current_penalties = db.get_current_penalties(moderator_id)
        current_value = current_penalties.get(penalty_type, 0)
        
        # Оновлюємо покарання
        success = db.update_penalty(moderator_id, penalty_type, new_value, reason, issued_by)
        
        if success:
            # Формуємо повідомлення про зміни
            message = create_penalty_change_message(
                moderator_id, penalty_type, current_value, new_value, reason, issued_by
            )
            
            # Відправляємо повідомлення про зміни
            send_penalty_change_notification(message)
            
            # Логування
            log_action("penalty_updated", 
                      f"Модератор: {moderator_id}, Тип: {penalty_type}, З {current_value} на {new_value}, Причина: {reason}",
                      request.headers.get('User-Agent', ''))
            
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося оновити покарання'})
            
    except Exception as e:
        logger.error(f"Помилка оновлення покарання: {e}")
        return jsonify({'success': False, 'error': str(e)})

def create_penalty_change_message(moderator_id, penalty_type, old_value, new_value, reason, issued_by):
    """Створити повідомлення про зміну покарання"""
    penalty_names = {
        'fine': 'штраф',
        'warning': 'попередження',
        'reprimand': 'догану'
    }
    
    penalty_icons = {
        'fine': '💰',
        'warning': '⚠️',
        'reprimand': '📝'
    }
    
    if new_value > old_value:
        # Додано покарання
        action = "додано"
        change = f"+{new_value - old_value}"
    elif new_value < old_value:
        # Знято покарання
        action = "знято"
        change = f"{new_value - old_value}"
    else:
        # Без змін
        action = "залишено без змін"
        change = "0"
    
    moderator = db.get_moderator(moderator_id)
    moderator_name = moderator.get('first_name', 'Невідомо') if moderator else 'Невідомо'
    
    message = (
        f"{penalty_icons.get(penalty_type, '⚖️')} **Зміна покарання**\n\n"
        f"👤 **Модератор:** {moderator_name}\n"
        f"📋 **Тип:** {penalty_names.get(penalty_type, penalty_type)}\n"
        f"📊 **Старий стан:** {old_value}\n"
        f"📈 **Новий стан:** {new_value}\n"
        f"🔄 **Зміна:** {change}\n"
        f"📝 **Причина:** {reason}\n"
        f"🔧 **Виконав:** {issued_by}\n"
        f"⏰ **Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message

def send_penalty_change_notification(message: str):
    """Надіслати сповіщення про зміну покарання"""
    # Відправка в чат покарань
    send_to_punishments_chat(message)
    
    # Можна також відправляти в інші чати, якщо потрібно
    # send_to_logs_chat(message)

@app.route('/api/remove_penalty', methods=['POST'])
def api_remove_penalty():
    """Зняти покарання з модератора"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        moderator_id = data.get('moderator_id')
        penalty_type = data.get('type')  # 'fine', 'warning', 'reprimand'
        remove_value = data.get('value', 1)
        reason = data.get('reason', '')
        issued_by = session.get('username', 'Невідомо')
        
        # Валідація значень
        if remove_value <= 0:
            return jsonify({'success': False, 'error': 'Значення має бути більше 0'})
        
        # Знімаємо покарання
        success = db.remove_penalty(moderator_id, penalty_type, remove_value, reason, issued_by)
        
        if success:
            # Отримуємо поточний стан після зняття
            current_penalties = db.get_current_penalties(moderator_id)
            new_value = current_penalties.get(penalty_type, 0)
            
            # Формуємо повідомлення про зняття
            message = create_penalty_removal_message(
                moderator_id, penalty_type, remove_value, new_value, reason, issued_by
            )
            
            # Відправляємо повідомлення
            send_penalty_change_notification(message)
            
            # Логування
            log_action("penalty_removed", 
                      f"Модератор: {moderator_id}, Тип: {penalty_type}, Знято: {remove_value}, Причина: {reason}",
                      request.headers.get('User-Agent', ''))
            
            return jsonify({'success': True, 'new_value': new_value})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося зняти покарання'})
            
    except Exception as e:
        logger.error(f"Помилка зняття покарання: {e}")
        return jsonify({'success': False, 'error': str(e)})

def create_penalty_removal_message(moderator_id, penalty_type, removed_value, new_value, reason, issued_by):
    """Створити повідомлення про зняття покарання"""
    penalty_names = {
        'fine': 'штраф',
        'warning': 'попередження',
        'reprimand': 'догану'
    }
    
    penalty_icons = {
    'fine': '💰',
    'warning': '⚠️',
    'reprimand': '📝'
    }
    
    moderator = db.get_moderator(moderator_id)
    moderator_name = moderator.get('first_name', 'Невідомо') if moderator else 'Невідомо'
    
    message = (
        f"✅ **Зняття покарання**\n\n"
        f"👤 **Модератор:** {moderator_name}\n"
        f"📋 **Тип:** {penalty_names.get(penalty_type, penalty_type)}\n"
        f"➖ **Знято:** {removed_value}\n"
        f"📊 **Новий стан:** {new_value}\n"
        f"📝 **Причина зняття:** {reason}\n"
        f"🔧 **Виконав:** {issued_by}\n"
        f"⏰ **Час:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    return message

# НОВІ API ДЛЯ БЛОКУВАННЯ IP АДРЕС
@app.route('/api/get_banned_ips')
def api_get_banned_ips():
    """Отримати список заблокованих IP"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        banned_ips = load_banned_ips()
        return jsonify({
            'success': True,
            'banned_ips': banned_ips
        })
    except Exception as e:
        logger.error(f"Помилка отримання заблокованих IP: {e}")
        return jsonify({'success': False, 'error': str(e)})

def is_valid_ipv4(ip_address):
    """Перевірити чи є IPv4 адреса валідною"""
    ipv4_pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$')
    if ipv4_pattern.match(ip_address):
        # Перевіряємо октети
        parts = ip_address.split('.')
        for part in parts:
            if part == '*':
                continue
            if not part.isdigit() or int(part) > 255:
                return False
        return True
    return False

def is_valid_ipv6(ip_address):
    """Перевірити чи є IPv6 адреса валідною"""
    try:
        # Спрощений підхід - використовуємо вбудовану бібліотеку
        import ipaddress
        ipaddress.IPv6Address(ip_address)
        return True
    except:
        # Якщо стандартна бібліотека не спрацювала, пробуємо регулярні вирази
        # Базовий IPv6 формат
        ipv6_pattern = re.compile(r'^[0-9a-fA-F:]+:[0-9a-fA-F:]+$')
        # IPv6 з скороченням ::
        ipv6_short_pattern = re.compile(r'^[0-9a-fA-F:]*::[0-9a-fA-F:]*$')
        # IPv6 з IPv4 в кінці
        ipv6_with_ipv4 = re.compile(r'^[0-9a-fA-F:]+:[0-9a-fA-F:]+:[0-9a-fA-F.]{7,15}$')
        
        return (ipv6_pattern.match(ip_address) or 
                ipv6_short_pattern.match(ip_address) or
                ipv6_with_ipv4.match(ip_address))

def is_valid_ip_address(ip_address):
    """Перевірити чи IP адреса валідна (IPv4 або IPv6) - спрощена версія"""
    try:
        import ipaddress
        # Спробуємо створити об'єкт IP адреси
        ipaddress.ip_address(ip_address)
        return True
    except:
        # Перевіряємо IPv4 з маскою (*)
        if '*' in ip_address:
            ip_parts = ip_address.split('.')
            if len(ip_parts) == 4:
                valid = True
                for part in ip_parts:
                    if part != '*' and (not part.isdigit() or int(part) > 255):
                        valid = False
                        break
                if valid:
                    return True
        
        # Додаткова перевірка для IPv6 з двокрапками
        if ':' in ip_address and len(ip_address) >= 3:
            # Базова перевірка IPv6
            parts = ip_address.split(':')
            if 3 <= len(parts) <= 8:
                valid = True
                for part in parts:
                    if part and not all(c in '0123456789abcdefABCDEF' for c in part):
                        valid = False
                        break
                if valid:
                    return True
    
    return False

def get_ip_version(ip_address):
    """Визначити версію IP адреси - спрощена версія"""
    if '.' in ip_address or (ip_address.count('*') > 0 and '.' in ip_address):
        return 'IPv4'
    elif ':' in ip_address:
        return 'IPv6'
    else:
        return 'Unknown'

def get_ip_version(ip_address):
    """Визначити версію IP адреси"""
    if is_valid_ipv4(ip_address) or ('*' in ip_address and '.' in ip_address):
        return 'IPv4'
    elif is_valid_ipv6(ip_address):
        return 'IPv6'
    else:
        return 'Unknown'

@app.route('/api/ban_ip', methods=['POST'])
def api_ban_ip():
    """Заблокувати IP адресу (IPv4 або IPv6)"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ip_address = data.get('ip_address')
        banned_by = session.get('username', 'System')
        
        if not ip_address:
            return jsonify({'success': False, 'error': 'IP адреса не вказана'})
        
        # Перевіряємо формат IP (IPv4 або IPv6)
        if not is_valid_ip_address(ip_address):
            return jsonify({'success': False, 'error': 'Невірний формат IP адреси. Використовуйте IPv4 (напр. 192.168.1.1) або IPv6 (напр. 2001:db8::1)'})
        
        # Додаємо IP до списку заблокованих
        success = add_banned_ip(ip_address)
        
        if success:
            ip_version = get_ip_version(ip_address)
            
            # Логування дії
            log_action("ip_banned", 
                      f"IP: {ip_address} ({ip_version}), Заблоковав: {banned_by}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка сповіщення
            notification_message = (
                f"🌐 **Заблоковано {ip_version} адресу**\n\n"
                f"📡 IP: `{ip_address}`\n"
                f"🔢 Тип: {ip_version}\n"
                f"🔧 Виконав: {banned_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(notification_message)
            
            return jsonify({
                'success': True, 
                'message': f'{ip_version} адресу {ip_address} успішно заблоковано',
                'ip_version': ip_version
            })
        else:
            return jsonify({'success': False, 'error': 'Не вдалося заблокувати IP'})
            
    except Exception as e:
        logger.error(f"Помилка блокування IP: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/unban_ip', methods=['POST'])
def api_unban_ip():
    """Розблокувати IP адресу"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ip_address = data.get('ip_address')
        
        if not ip_address:
            return jsonify({'success': False, 'error': 'IP адреса не вказана'})
        
        # Видаляємо IP зі списку заблокованих
        success = remove_banned_ip(ip_address)
        
        if success:
            # Логування дії
            log_action("ip_unbanned", 
                      f"IP: {ip_address}",
                      request.headers.get('User-Agent', ''))
            
            # Відправка сповіщення
            notification_message = (
                f"🌐 **Розблоковано IP адресу**\n\n"
                f"📡 IP: `{ip_address}`\n"
                f"🔧 Виконав: {session.get('username', 'Невідомо')}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            send_to_punishments_chat(notification_message)
            
            return jsonify({'success': True, 'message': f'IP {ip_address} успішно розблоковано'})
        else:
            return jsonify({'success': False, 'error': 'Не вдалося розблокувати IP'})
            
    except Exception as e:
        logger.error(f"Помилка розблокування IP: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/check_ip_ban', methods=['POST'])
def api_check_ip_ban():
    """Перевірити чи IP заблокований"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ip_address = data.get('ip_address')
        
        if not ip_address:
            return jsonify({'success': False, 'error': 'IP адреса не вказана'})
        
        is_banned = is_ip_banned(ip_address)
        
        return jsonify({
            'success': True,
            'ip_address': ip_address,
            'is_banned': is_banned
        })
            
    except Exception as e:
        logger.error(f"Помилка перевірки IP: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/analyze_ip', methods=['POST'])
def api_analyze_ip():
    """Проаналізувати IP адресу"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        ip_address = data.get('ip_address')
        
        if not ip_address:
            return jsonify({'success': False, 'error': 'IP адреса не вказана'})
        
        ip_version = get_ip_version(ip_address)
        is_valid = is_valid_ip_address(ip_address)
        is_banned = is_ip_banned(ip_address)
        
        return jsonify({
            'success': True,
            'ip_address': ip_address,
            'ip_version': ip_version,
            'is_valid': is_valid,
            'is_banned': is_banned
        })
            
    except Exception as e:
        logger.error(f"Помилка аналізу IP: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/verify_password', methods=['POST'])
def api_verify_password():
    """Перевірити пароль для доступу до блокування IP"""
    if not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.json
        password = data.get('password')
        
        # Пароль для блокування IP
        correct_password = "1221"
        
        if password == correct_password:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Невірний пароль'})
            
    except Exception as e:
        logger.error(f"Помилка перевірки пароля: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
def logout():
    if session.get('authenticated'):
        log_action("logout", 
                  "Вихід з системи",
                  request.headers.get('User-Agent', ''))
    session.clear()
    return redirect(url_for('login'))

def check_database():
    """Перевірка стану бази даних"""
    try:
        db = Database(Config.DATABASE_FILE)
        users = db.get_all_group_users()
        print(f"📊 Знайдено {len(users)} користувачів у базі даних")
        
        for user in users:
            messages = db.get_group_user_messages(user['user_id'], limit=5)
            print(f"👤 {user['first_name']} (ID: {user['user_id']}) - повідомлень: {len(messages)}")
            
        return True
    except Exception as e:
        print(f"❌ Помилка перевірки бази даних: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Запуск Flask додатку...")
    print(f"🌐 Адреса: http://{Config.HOST}:{Config.PORT}")
    print(f"🔧 Режим відладки: {Config.DEBUG}")
    
    # Перевірка бази даних
    if check_database():
        print("✅ База даних успішно перевірена")
    else:
        print("❌ Проблеми з базою даних")
    
    # Завантаження заблокованих IP
    banned_ips = load_banned_ips()
    print(f"🛡️ Завантажено {len(banned_ips)} заблокованих IP адрес")
    
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)