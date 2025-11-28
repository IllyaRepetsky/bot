import json
import os
from datetime import datetime
from flask import session, redirect, url_for, render_template, request, jsonify
import logging

logger = logging.getLogger(__name__)

# Файл для зберігання заблокованих акаунтів
BANNED_USERS_FILE = 'banned_users.json'

def load_banned_users():
    """Завантажити список заблокованих акаунтів"""
    try:
        if os.path.exists(BANNED_USERS_FILE):
            with open(BANNED_USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Помилка завантаження заблокованих акаунтів: {e}")
        return {}

def save_banned_users(banned_users):
    """Зберегти список заблокованих акаунтів"""
    try:
        with open(BANNED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(banned_users, f, indent=4, ensure_ascii=False)
        logger.info(f"Список заблокованих акаунтів оновлено")
        return True
    except Exception as e:
        logger.error(f"Помилка збереження заблокованих акаунтів: {e}")
        return False

def ban_user_account(username, reason="Порушення правил", banned_by="System"):
    """Заблокувати акаунт користувача"""
    try:
        banned_users = load_banned_users()
        
        banned_users[username] = {
            'reason': reason,
            'banned_by': banned_by,
            'banned_at': datetime.now().isoformat(),
            'ip_address': request.remote_addr if request else 'Unknown'
        }
        
        return save_banned_users(banned_users)
    except Exception as e:
        logger.error(f"Помилка блокування акаунту {username}: {e}")
        return False

def unban_user_account(username):
    """Розблокувати акаунт користувача"""
    try:
        banned_users = load_banned_users()
        
        if username in banned_users:
            del banned_users[username]
            return save_banned_users(banned_users)
        
        return True
    except Exception as e:
        logger.error(f"Помилка розблокування акаунту {username}: {e}")
        return False

def is_user_banned(username):
    """Перевірити чи акаунт заблокований"""
    if not username:
        return False
    banned_users = load_banned_users()
    return username in banned_users

def get_ban_reason(username):
    """Отримати причину блокування акаунту"""
    banned_users = load_banned_users()
    if username in banned_users:
        return banned_users[username].get('reason', 'Причина не вказана')
    return None

def get_all_banned_accounts():
    """Отримати всі заблоковані акаунти"""
    return load_banned_users()

def check_user_ban():
    """Перевірити чи поточний користувач заблокований (для використання в before_request)"""
    if session.get('authenticated') and session.get('username'):
        username = session['username']
        if is_user_banned(username):
            logger.warning(f"Заблокований акаунт намагався отримати доступ: {username}")
            return redirect(url_for('ban_user_page'))
    return None

def auto_ban_user_for_logs_access(username, ip_address):
    """Автоматичне блокування акаунту за спробу доступу до логів"""
    try:
        # Список адміністраторів, яких не блокуємо
        admin_users = ['Repetsky', 'Artem14091']
        
        # Перевіряємо чи користувач не адміністратор
        if username not in admin_users:
            reason = f"Автоматичне блокування за спробу доступу до сторінки логів з IP {ip_address}"
            success = ban_user_account(username, reason, "Система автоматичного блокування")
            
            if success:
                logger.warning(f"🔒 АКАУНТ ЗАБЛОКОВАНО: {username} за спробу доступу до логів")
                
                # Відправляємо сповіщення в Telegram
                from web_app import send_to_punishments_chat
                ban_message = (
                    f"🚫 **АВТОМАТИЧНЕ БЛОКУВАННЯ АКАУНТУ**\n\n"
                    f"👤 Користувач: {username}\n"
                    f"📡 IP: {ip_address}\n"
                    f"📋 Причина: Спроба доступу до сторінки логів\n"
                    f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                send_to_punishments_chat(ban_message)
                
                # Логування дії
                from web_app import log_action
                log_action("auto_account_ban", 
                          f"Автоматичне блокування акаунту {username} за спробу доступу до логів",
                          f"IP: {ip_address}")
                
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Помилка автоматичного блокування акаунту {username}: {e}")
        return False

def setup_user_ban_routes(app):
    """Налаштувати маршрути для блокування акаунтів"""
    
    @app.route('/ban-user')
    def ban_user_page():
        """Сторінка бану акаунту"""
        username = session.get('username', 'Невідомий користувач')
        ban_reason = get_ban_reason(username) or "Порушення правил використання сервісу"
        
        # Очищаємо сесію
        session.clear()
        
        return render_template('banuser.html', 
                             username=username, 
                             ban_reason=ban_reason)
    
    @app.route('/api/ban_account', methods=['POST'])
    def api_ban_account():
        """API для блокування акаунту"""
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data provided'})
                
            username = data.get('username')
            reason = data.get('reason', 'Порушення правил')
            banned_by = session.get('username', 'System')
            
            if not username:
                return jsonify({'success': False, 'error': 'Ім\'я користувача не вказано'})
            
            success = ban_user_account(username, reason, banned_by)
            
            if success:
                # Логування дії
                from web_app import log_action
                log_action("account_banned", 
                          f"Акаунт {username} заблоковано. Причина: {reason}",
                          request.headers.get('User-Agent', ''))
                
                return jsonify({'success': True, 'message': f'Акаунт {username} успішно заблоковано'})
            else:
                return jsonify({'success': False, 'error': 'Не вдалося заблокувати акаунт'})
                
        except Exception as e:
            logger.error(f"Помилка блокування акаунту: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/unban_account', methods=['POST'])
    def api_unban_account():
        """API для розблокування акаунту"""
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data provided'})
                
            username = data.get('username')
            
            if not username:
                return jsonify({'success': False, 'error': 'Ім\'я користувача не вказано'})
            
            success = unban_user_account(username)
            
            if success:
                # Логування дії
                from web_app import log_action
                log_action("account_unbanned", 
                          f"Акаунт {username} розблоковано",
                          request.headers.get('User-Agent', ''))
                
                return jsonify({'success': True, 'message': f'Акаунт {username} успішно розблоковано'})
            else:
                return jsonify({'success': False, 'error': 'Не вдалося розблокувати акаунт'})
                
        except Exception as e:
            logger.error(f"Помилка розблокування акаунту: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/get_banned_accounts')
    def api_get_banned_accounts():
        """API для отримання списку заблокованих акаунтів"""
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            banned_accounts = get_all_banned_accounts()
            return jsonify({'success': True, 'banned_accounts': banned_accounts})
        except Exception as e:
            logger.error(f"Помилка отримання заблокованих акаунтів: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/check_account_ban', methods=['POST'])
    def api_check_account_ban():
        """API для перевірки статусу блокування акаунту"""
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data provided'})
                
            username = data.get('username')
            
            if not username:
                return jsonify({'success': False, 'error': 'Ім\'я користувача не вказано'})
            
            is_banned = is_user_banned(username)
            ban_reason = get_ban_reason(username) if is_banned else None
            
            return jsonify({
                'success': True,
                'username': username,
                'is_banned': is_banned,
                'ban_reason': ban_reason
            })
                
        except Exception as e:
            logger.error(f"Помилка перевірки статусу акаунту: {e}")
            return jsonify({'success': False, 'error': str(e)})

    logger.info("Маршрути блокування акаунтів успішно налаштовані")

# Функція для інтеграції з основним додатком
def init_user_ban_system(app):
    """Ініціалізація системи блокування акаунтів"""
    # Додаємо маршрути
    setup_user_ban_routes(app)
    
    # Додаємо перевірку бану акаунту перед запитами
    @app.before_request
    def check_user_ban_before_request():
        # Виключаємо статичні файли та сторінку бану
        if request.endpoint in ['static', 'ban_user_page', 'login', 'twofa']:
            return None
        
        # Перевіряємо бан акаунту
        if session.get('authenticated') and session.get('username'):
            username = session['username']
            if is_user_banned(username):
                logger.warning(f"Заблокований акаунт намагався отримати доступ: {username}")
                return redirect(url_for('ban_user_page'))
        
        return None
    
    logger.info("Система блокування акаунтів успішно ініціалізована")