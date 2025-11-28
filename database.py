import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

class Database:
    def __init__(self, db_file: str = "shift_system.db"):
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        # Таблица модераторов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moderators (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                total_shifts INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица змін
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moderator_id INTEGER,
                start_time TEXT,
                end_time TEXT,
                status TEXT DEFAULT 'active',
                duration_minutes INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (moderator_id) REFERENCES moderators (user_id)
            )
        ''')
        
        # Таблица пользователей группы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_banned BOOLEAN DEFAULT FALSE,
                is_muted BOOLEAN DEFAULT FALSE,
                ban_reason TEXT,
                banned_by TEXT,
                banned_until TEXT,
                mute_until TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений группы
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_text TEXT,
                message_type TEXT, -- 'sent', 'edited', 'deleted'
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES group_users (user_id)
            )
        ''')
        
        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        ''')
        
        # Таблица 2FA кодов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS twofa_codes (
                code TEXT PRIMARY KEY,
                telegram_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                expires_at TEXT
            )
        ''')
        
        # Таблица логов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                details TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица детальних логів
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS action_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                action_type TEXT,
                action_details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица штрафів, доган та попереджень
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS penalties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                moderator_id INTEGER,
                penalty_type TEXT, -- 'fine', 'warning', 'reprimand'
                value INTEGER,
                reason TEXT,
                issued_by TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (moderator_id) REFERENCES moderators (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_file)
    
    # =============================================
    # МЕТОДИ ДЛЯ РОБОТИ З МОДЕРАТОРАМИ
    # =============================================
    
    def add_moderator(self, user_id: int, username: str, first_name: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO moderators (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
            conn.commit()
        except Exception as e:
            print(f"Помилка додавання модератора: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def remove_moderator(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM moderators WHERE user_id = ?', (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Помилка видалення модератора: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_moderator(self, user_id: int) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM moderators WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                columns = [col[0] for col in cursor.description]
                return dict(zip(columns, result))
            return None
        except Exception as e:
            print(f"Помилка отримання модератора: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_moderators(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM moderators WHERE is_active = TRUE')
            columns = [col[0] for col in cursor.description]
            moderators = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return moderators
        except Exception as e:
            print(f"Помилка отримання модераторів: {e}")
            return []
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ РОБОТИ ЗІ ЗМІНАМИ
    # =============================================
    
    def start_shift(self, moderator_id: int) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Перевіряємо чи є активна зміна
            cursor.execute('SELECT id FROM shifts WHERE moderator_id = ? AND status = "active"', (moderator_id,))
            active_shift = cursor.fetchone()
            
            if active_shift:
                return None
            
            cursor.execute('''
                INSERT INTO shifts (moderator_id, start_time, status)
                VALUES (?, ?, ?)
            ''', (moderator_id, datetime.now().isoformat(), 'active'))
            
            shift_id = cursor.lastrowid
            conn.commit()
            return shift_id
            
        except Exception as e:
            print(f"Помилка початку зміни: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def end_shift(self, moderator_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Знаходимо активну зміну
            cursor.execute('SELECT id, start_time FROM shifts WHERE moderator_id = ? AND status = "active"', (moderator_id,))
            active_shift = cursor.fetchone()
            
            if not active_shift:
                return False
            
            shift_id, start_time = active_shift
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.now()
            duration = int((end_dt - start_dt).total_seconds() / 60)
            
            cursor.execute('''
                UPDATE shifts 
                SET end_time = ?, status = 'completed', duration_minutes = ?
                WHERE id = ?
            ''', (end_dt.isoformat(), duration, shift_id))
            
            # Оновлюємо загальну кількість змін
            cursor.execute('''
                UPDATE moderators 
                SET total_shifts = total_shifts + 1
                WHERE user_id = ?
            ''', (moderator_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Помилка завершення зміни: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_moderator_shifts(self, moderator_id: int) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM shifts 
                WHERE moderator_id = ? 
                ORDER BY created_at DESC
                LIMIT 20
            ''', (moderator_id,))
            columns = [col[0] for col in cursor.description]
            shifts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return shifts
        except Exception as e:
            print(f"Помилка отримання змін модератора: {e}")
            return []
        finally:
            conn.close()
    
    def get_active_shifts(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT s.*, m.username, m.first_name 
                FROM shifts s
                JOIN moderators m ON s.moderator_id = m.user_id
                WHERE s.status = 'active'
            ''')
            columns = [col[0] for col in cursor.description]
            shifts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return shifts
        except Exception as e:
            print(f"Помилка отримання активних змін: {e}")
            return []
        finally:
            conn.close()
    
    def get_all_shifts(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT s.*, m.username, m.first_name 
                FROM shifts s
                JOIN moderators m ON s.moderator_id = m.user_id
                ORDER BY s.created_at DESC
            ''')
            columns = [col[0] for col in cursor.description]
            shifts = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return shifts
        except Exception as e:
            print(f"Помилка отримання всіх змін: {e}")
            return []
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ РОБОТИ З КОРИСТУВАЧАМИ ГРУПИ
    # =============================================
    
    def add_group_user(self, user_id: int, username: str, first_name: str, is_admin: bool = False):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO group_users (user_id, username, first_name, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, first_name, is_admin))
            conn.commit()
        except Exception as e:
            print(f"Помилка додавання користувача групи: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_group_user_info(self, user_id: int) -> Optional[Dict]:
        """Отримати повну інформацію про користувача групи"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM group_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                columns = [col[0] for col in cursor.description]
                user_data = dict(zip(columns, result))
                
                # Отримуємо повідомлення користувача
                messages = self.get_group_user_messages(user_id)
                user_data['messages'] = messages
                
                return user_data
            return None
        except Exception as e:
            print(f"Помилка отримання інформації про користувача: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_group_users(self) -> List[Dict]:
        """Отримати всіх користувачів групи"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM group_users ORDER BY created_at DESC')
            columns = [col[0] for col in cursor.description]
            users = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return users
        except Exception as e:
            print(f"Помилка отримання користувачів групи: {e}")
            return []
        finally:
            conn.close()
    
    def ban_user(self, user_id: int, reason: str, banned_by: str, ban_until: str = None):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE group_users 
                SET is_banned = TRUE, ban_reason = ?, banned_by = ?, banned_until = ?
                WHERE user_id = ?
            ''', (reason, banned_by, ban_until, user_id))
            conn.commit()
        except Exception as e:
            print(f"Помилка блокування користувача: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def unban_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE group_users 
                SET is_banned = FALSE, ban_reason = NULL, banned_by = NULL, banned_until = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Помилка розблокування користувача: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def mute_user(self, user_id: int, mute_until: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE group_users 
                SET is_muted = TRUE, mute_until = ?
                WHERE user_id = ?
            ''', (mute_until, user_id))
            conn.commit()
        except Exception as e:
            print(f"Помилка муту користувача: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def unmute_user(self, user_id: int):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE group_users 
                SET is_muted = FALSE, mute_until = NULL
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
        except Exception as e:
            print(f"Помилка зняття муту: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def set_user_admin(self, user_id: int, is_admin: bool):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE group_users 
                SET is_admin = ?
                WHERE user_id = ?
            ''', (is_admin, user_id))
            conn.commit()
        except Exception as e:
            print(f"Помилка зміни прав адміністратора: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_banned_users(self) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT * FROM group_users WHERE is_banned = TRUE OR is_muted = TRUE')
            columns = [col[0] for col in cursor.description]
            users = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return users
        except Exception as e:
            print(f"Помилка отримання заблокованих користувачів: {e}")
            return []
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ РОБОТИ З ПОВІДОМЛЕННЯМИ ГРУПИ
    # =============================================
    
    def add_group_message(self, user_id: int, message_text: str, message_type: str = 'sent'):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO group_messages (user_id, message_text, message_type)
                VALUES (?, ?, ?)
            ''', (user_id, message_text, message_type))
            conn.commit()
        except Exception as e:
            print(f"Помилка додавання повідомлення групи: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_group_user_messages(self, user_id: int, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM group_messages 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            columns = [col[0] for col in cursor.description]
            messages = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return messages
        except Exception as e:
            print(f"Помилка отримання повідомлень користувача: {e}")
            return []
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ ЛОГУВАННЯ
    # =============================================
    
    def add_log(self, user_id: int, action: str, details: str, ip_address: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO logs (user_id, action, details, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (user_id, action, details, ip_address))
            conn.commit()
        except Exception as e:
            print(f"Помилка додавання логу: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ РОЗШИРЕНОГО ЛОГУВАННЯ
    # =============================================
    
    def add_action_log(self, user_id: str, username: str, action_type: str, 
                      action_details: str, ip_address: str, user_agent: str = None):
        """Додати детальний лог дії"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO action_logs 
                (user_id, username, action_type, action_details, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, action_type, action_details, ip_address, user_agent))
            conn.commit()
        except Exception as e:
            print(f"Помилка додавання логу дії: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_action_logs(self, limit: int = 100, user_id: str = None) -> List[Dict]:
        """Отримати лог дій"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if user_id:
                cursor.execute('''
                    SELECT * FROM action_logs 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM action_logs 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                ''', (limit,))
            
            columns = [col[0] for col in cursor.description]
            logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return logs
        except Exception as e:
            print(f"Помилка отримання логів дій: {e}")
            return []
        finally:
            conn.close()
    
    def get_login_stats(self, days: int = 30) -> Dict:
        """Статистика входів за останні дні"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Загальна кількість входів
            cursor.execute('''
                SELECT COUNT(*) FROM action_logs 
                WHERE action_type LIKE '%login%' AND timestamp > ?
            ''', (since_date,))
            total_logins = cursor.fetchone()[0] or 0
            
            # Успішні входи
            cursor.execute('''
                SELECT COUNT(*) FROM action_logs 
                WHERE action_type = 'login_success' AND timestamp > ?
            ''', (since_date,))
            successful_logins = cursor.fetchone()[0] or 0
            
            # Невдалі входи
            cursor.execute('''
                SELECT COUNT(*) FROM action_logs 
                WHERE action_type = 'login_failed' AND timestamp > ?
            ''', (since_date,))
            failed_logins = cursor.fetchone()[0] or 0
            
            # Активні користувачі
            cursor.execute('''
                SELECT COUNT(DISTINCT user_id) FROM action_logs 
                WHERE timestamp > ?
            ''', (since_date,))
            active_users = cursor.fetchone()[0] or 0
            
            return {
                'total_logins': total_logins,
                'successful_logins': successful_logins,
                'failed_logins': failed_logins,
                'active_users': active_users,
                'success_rate': round((successful_logins / max(total_logins, 1)) * 100, 1)
            }
            
        except Exception as e:
            print(f"Помилка отримання статистики входів: {e}")
            return {
                'total_logins': 0,
                'successful_logins': 0,
                'failed_logins': 0,
                'active_users': 0,
                'success_rate': 0
            }
        finally:
            conn.close()

    # =============================================
    # МЕТОДИ ДЛЯ 2FA
    # =============================================
    
    def save_2fa_code(self, code: str, telegram_id: int, expires_at: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO twofa_codes (code, telegram_id, expires_at)
                VALUES (?, ?, ?)
            ''', (code, telegram_id, expires_at))
            conn.commit()
        except Exception as e:
            print(f"Помилка збереження 2FA коду: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    def verify_2fa_code(self, code: str, telegram_id: int) -> bool:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM twofa_codes 
                WHERE code = ? AND telegram_id = ? AND expires_at > ?
            ''', (code, telegram_id, datetime.now().isoformat()))
            result = cursor.fetchone()
            return result is not None
        except Exception as e:
            print(f"Помилка перевірки 2FA коду: {e}")
            return False
        finally:
            conn.close()
    
    def delete_2fa_code(self, code: str):
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM twofa_codes WHERE code = ?', (code,))
            conn.commit()
        except Exception as e:
            print(f"Помилка видалення 2FA коду: {e}")
            conn.rollback()
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ СТАТИСТИКИ
    # =============================================
    
    def get_stats(self) -> Dict:
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Модератори на зміні
            cursor.execute('SELECT COUNT(*) FROM shifts WHERE status = "active"')
            moderators_on_shift = cursor.fetchone()[0] or 0
            
            # Всі модератори
            cursor.execute('SELECT COUNT(*) FROM moderators WHERE is_active = TRUE')
            total_moderators = cursor.fetchone()[0] or 0
            
            # Всього змін
            cursor.execute('SELECT COUNT(*) FROM shifts')
            total_shifts = cursor.fetchone()[0] or 0
            
            # Середня кількість змін за тиждень
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            cursor.execute('SELECT COUNT(*) FROM shifts WHERE created_at > ?', (week_ago,))
            weekly_shifts = cursor.fetchone()[0] or 0
            avg_weekly_shifts = weekly_shifts / max(total_moderators, 1)
            
            # Статистика групи
            cursor.execute('SELECT COUNT(*) FROM group_users')
            total_group_users = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM group_users WHERE is_admin = TRUE')
            group_admins = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM group_users WHERE is_banned = TRUE')
            banned_users = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM group_users WHERE is_muted = TRUE')
            muted_users = cursor.fetchone()[0] or 0
            
            # Отримуємо список активних модераторів для відображення
            active_moderators = self.get_active_shifts()
            
            return {
                'moderators_on_shift': moderators_on_shift,
                'total_moderators': total_moderators,
                'total_shifts': total_shifts,
                'avg_weekly_shifts': round(avg_weekly_shifts, 1),
                'total_group_users': total_group_users,
                'group_admins': group_admins,
                'banned_users': banned_users,
                'muted_users': muted_users,
                'active_moderators_list': active_moderators
            }
            
        except Exception as e:
            print(f"Помилка отримання статистики: {e}")
            return {
                'moderators_on_shift': 0,
                'total_moderators': 0,
                'total_shifts': 0,
                'avg_weekly_shifts': 0,
                'total_group_users': 0,
                'group_admins': 0,
                'banned_users': 0,
                'muted_users': 0,
                'active_moderators_list': []
            }
        finally:
            conn.close()
    
    # =============================================
    # МЕТОДИ ДЛЯ ШТРАФІВ ТА ПОКАРАНЬ
    # =============================================
    
    def add_penalty(self, moderator_id: int, penalty_type: str, value: int, reason: str, issued_by: str):
        """Додати штраф, догану або попередження модератору"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO penalties (moderator_id, penalty_type, value, reason, issued_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (moderator_id, penalty_type, value, reason, issued_by))
            conn.commit()
            return True
        except Exception as e:
            print(f"Помилка додавання покарання: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_moderator_penalties(self, moderator_id: int) -> List[Dict]:
        """Отримати всі покарання модератора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT * FROM penalties 
                WHERE moderator_id = ? 
                ORDER BY created_at DESC
            ''', (moderator_id,))
            columns = [col[0] for col in cursor.description]
            penalties = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return penalties
        except Exception as e:
            print(f"Помилка отримання покарань: {e}")
            return []
        finally:
            conn.close()
    
    def get_moderator_penalties_summary(self, moderator_id: int) -> Dict:
        """Отримати сумарну інформацію про покарання модератора"""
        penalties = self.get_moderator_penalties(moderator_id)
        
        total_fine = 0
        total_warnings = 0
        total_reprimands = 0
        
        for penalty in penalties:
            if penalty['penalty_type'] == 'fine':
                total_fine += penalty['value']
            elif penalty['penalty_type'] == 'warning':
                total_warnings += penalty['value']
            elif penalty['penalty_type'] == 'reprimand':
                total_reprimands += penalty['value']
        
        return {
            'total_fine': total_fine,
            'total_warnings': total_warnings,
            'total_reprimands': total_reprimands,
            'all_penalties': penalties
        }
    
    def get_current_penalties(self, moderator_id: int) -> Dict:
        """Отримати поточні активні покарання модератора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT penalty_type, SUM(value) as total_value
                FROM penalties 
                WHERE moderator_id = ?
                GROUP BY penalty_type
            ''', (moderator_id,))
            
            result = {}
            for row in cursor.fetchall():
                result[row[0]] = row[1]
            
            return result
        except Exception as e:
            print(f"Помилка отримання поточних покарань: {e}")
            return {}
        finally:
            conn.close()
    
    def update_penalty(self, moderator_id: int, penalty_type: str, new_value: int, reason: str, issued_by: str) -> bool:
        """Оновити покарання модератора з логуванням змін"""
        try:
            # Отримуємо поточне значення
            current_penalties = self.get_current_penalties(moderator_id)
            current_value = current_penalties.get(penalty_type, 0)
            
            # Розраховуємо різницю
            difference = new_value - current_value
            
            if difference == 0:
                return True  # Немає змін
            
            # Додаємо нове покарання з різницею
            if difference > 0:
                # Додаємо покарання
                return self.add_penalty(moderator_id, penalty_type, difference, reason, issued_by)
            else:
                # Знімаємо частину покарання (від'ємне значення)
                return self.add_penalty(moderator_id, penalty_type, difference, f"Зняття: {reason}", issued_by)
                
        except Exception as e:
            print(f"Помилка оновлення покарання: {e}")
            return False
    
    def get_penalty_history(self, moderator_id: int, penalty_type: str = None) -> List[Dict]:
        """Отримати історію покарань модератора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if penalty_type:
                cursor.execute('''
                    SELECT * FROM penalties 
                    WHERE moderator_id = ? AND penalty_type = ?
                    ORDER BY created_at DESC
                ''', (moderator_id, penalty_type))
            else:
                cursor.execute('''
                    SELECT * FROM penalties 
                    WHERE moderator_id = ?
                    ORDER BY created_at DESC
                ''', (moderator_id,))
            
            columns = [col[0] for col in cursor.description]
            penalties = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return penalties
        except Exception as e:
            print(f"Помилка отримання історії покарань: {e}")
            return []
        finally:
            conn.close()
    
    def remove_penalty(self, moderator_id: int, penalty_type: str, remove_value: int, reason: str, issued_by: str) -> bool:
        """Зняти частину покарання модератору"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Отримуємо поточне значення покарання
            current_penalties = self.get_current_penalties(moderator_id)
            current_value = current_penalties.get(penalty_type, 0)
            
            print(f"DEBUG: Removing penalty - Type: {penalty_type}, Current: {current_value}, Remove: {remove_value}")
            
            if current_value <= 0:
                print(f"DEBUG: No penalty to remove for {penalty_type}")
                return False  # Немає що знімати
            
            # Визначаємо скільки знімати
            remove_amount = min(remove_value, current_value)
            
            if remove_amount <= 0:
                return False
            
            # Додаємо запис з від'ємним значенням для зняття
            cursor.execute('''
                INSERT INTO penalties (moderator_id, penalty_type, value, reason, issued_by)
                VALUES (?, ?, ?, ?, ?)
            ''', (moderator_id, penalty_type, -remove_amount, f"Зняття: {reason}", issued_by))
            
            conn.commit()
            print(f"DEBUG: Successfully removed {remove_amount} from {penalty_type}")
            return True
            
        except Exception as e:
            print(f"Помилка зняття покарання: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # =============================================
    # ДОДАТКОВІ МЕТОДИ
    # =============================================
    
    def delete_user_data(self, user_id: int) -> bool:
        """Видалити всі дані користувача"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Видаляємо повідомлення
            cursor.execute('DELETE FROM group_messages WHERE user_id = ?', (user_id,))
            # Видаляємо користувача
            cursor.execute('DELETE FROM group_users WHERE user_id = ?', (user_id,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"Помилка видалення даних користувача: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def is_user_banned_or_muted(self, user_id: int) -> Dict:
        """Перевірити чи користувач заблокований або в муті"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('SELECT is_banned, is_muted, mute_until FROM group_users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                return {
                    'is_banned': bool(result[0]),
                    'is_muted': bool(result[1]),
                    'mute_until': result[2]
                }
            return {'is_banned': False, 'is_muted': False, 'mute_until': None}
        except Exception as e:
            print(f"Помилка перевірки статусу користувача: {e}")
            return {'is_banned': False, 'is_muted': False, 'mute_until': None}
        finally:
            conn.close()

    # =============================================
    # МЕТОДИ ДЛЯ ПРИМУСОВОГО КЕРУВАННЯ ЗМІНАМИ
    # =============================================

    def force_end_shift(self, moderator_id: int) -> bool:
        """Примусово завершити зміну модератора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Знаходимо активну зміну
            cursor.execute('SELECT id, start_time FROM shifts WHERE moderator_id = ? AND status = "active"', (moderator_id,))
            active_shift = cursor.fetchone()
            
            if not active_shift:
                return False
            
            shift_id, start_time = active_shift
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.now()
            duration = int((end_dt - start_dt).total_seconds() / 60)
            
            cursor.execute('''
                UPDATE shifts 
                SET end_time = ?, status = 'force_completed', duration_minutes = ?
                WHERE id = ?
            ''', (end_dt.isoformat(), duration, shift_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Помилка примусового завершення зміни: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def force_start_shift(self, moderator_id: int) -> Optional[int]:
        """Примусово розпочати зміну модератора"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Спочатку закриваємо активну зміну, якщо вона є
            self.force_end_shift(moderator_id)
            
            # Створюємо нову зміну
            cursor.execute('''
                INSERT INTO shifts (moderator_id, start_time, status)
                VALUES (?, ?, ?)
            ''', (moderator_id, datetime.now().isoformat(), 'force_active'))
            
            shift_id = cursor.lastrowid
            conn.commit()
            return shift_id
            
        except Exception as e:
            print(f"Помилка примусового початку зміни: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    # =============================================
    # МЕТОДИ ДЛЯ ОЧИЩЕННЯ ДАНИХ
    # =============================================

    def clear_old_logs(self, days: int = 30) -> bool:
        """Очистити старі логи"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Очищаємо логи дій
            cursor.execute('DELETE FROM action_logs WHERE timestamp < ?', (cutoff_date,))
            
            # Очищаємо звичайні логи
            cursor.execute('DELETE FROM logs WHERE created_at < ?', (cutoff_date,))
            
            # Очищаємо старі 2FA коди
            cursor.execute('DELETE FROM twofa_codes WHERE expires_at < ?', (datetime.now().isoformat(),))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Помилка очищення логів: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def clear_penalties_history(self, moderator_id: int = None) -> bool:
        """Очистити історію покарань"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if moderator_id:
                # Очищаємо покарання конкретного модератора
                cursor.execute('DELETE FROM penalties WHERE moderator_id = ?', (moderator_id,))
            else:
                # Очищаємо всі покарання старші за 90 днів
                cutoff_date = (datetime.now() - timedelta(days=90)).isoformat()
                cursor.execute('DELETE FROM penalties WHERE created_at < ?', (cutoff_date,))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Помилка очищення історії покарань: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    # =============================================
    # МЕТОДИ ДЛЯ ЕКСПОРТУ ДАНИХ
    # =============================================

    def export_moderators_data(self) -> List[Dict]:
        """Експортувати дані модераторів"""
        moderators = self.get_all_moderators()
        result = []
        
        for moderator in moderators:
            # Отримуємо додаткову інформацію про кожного модератора
            shifts = self.get_moderator_shifts(moderator['user_id'])
            penalties = self.get_moderator_penalties_summary(moderator['user_id'])
            
            moderator_data = {
                'user_id': moderator['user_id'],
                'username': moderator['username'],
                'first_name': moderator['first_name'],
                'total_shifts': moderator['total_shifts'],
                'created_at': moderator['created_at'],
                'total_shifts_count': len(shifts),
                'penalties': penalties,
                'last_shifts': shifts[:5]  # Останні 5 змін
            }
            result.append(moderator_data)
        
        return result

    def export_group_users_data(self) -> List[Dict]:
        """Експортувати дані користувачів групи"""
        users = self.get_all_group_users()
        result = []
        
        for user in users:
            user_data = {
                'user_id': user['user_id'],
                'username': user['username'],
                'first_name': user['first_name'],
                'is_admin': user['is_admin'],
                'is_banned': user['is_banned'],
                'is_muted': user['is_muted'],
                'ban_reason': user['ban_reason'],
                'banned_by': user['banned_by'],
                'banned_until': user['banned_until'],
                'mute_until': user['mute_until'],
                'created_at': user['created_at']
            }
            result.append(user_data)
        
        return result

    # =============================================
    # МЕТОДИ ДЛЯ СТАТИСТИКИ ПОКАРАНЬ
    # =============================================

    def get_penalties_stats(self, days: int = 30) -> Dict:
        """Отримати статистику покарань за останні дні"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            since_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Загальна кількість покарань
            cursor.execute('SELECT COUNT(*) FROM penalties WHERE created_at > ?', (since_date,))
            total_penalties = cursor.fetchone()[0] or 0
            
            # Кількість покарань по типах
            cursor.execute('''
                SELECT penalty_type, COUNT(*) as count, SUM(value) as total_value
                FROM penalties 
                WHERE created_at > ?
                GROUP BY penalty_type
            ''', (since_date,))
            
            penalties_by_type = {}
            for row in cursor.fetchall():
                penalties_by_type[row[0]] = {
                    'count': row[1],
                    'total_value': row[2]
                }
            
            # Найактивніші адміністратори по видачі покарань
            cursor.execute('''
                SELECT issued_by, COUNT(*) as penalty_count
                FROM penalties 
                WHERE created_at > ?
                GROUP BY issued_by 
                ORDER BY penalty_count DESC
                LIMIT 10
            ''', (since_date,))
            
            top_issuers = []
            for row in cursor.fetchall():
                top_issuers.append({
                    'issued_by': row[0],
                    'penalty_count': row[1]
                })
            
            return {
                'total_penalties': total_penalties,
                'penalties_by_type': penalties_by_type,
                'top_issuers': top_issuers,
                'period_days': days
            }
            
        except Exception as e:
            print(f"Помилка отримання статистики покарань: {e}")
            return {
                'total_penalties': 0,
                'penalties_by_type': {},
                'top_issuers': [],
                'period_days': days
            }
        finally:
            conn.close()

    # =============================================
    # МЕТОДИ ДЛЯ ПЕРЕВІРКИ СТАНУ СИСТЕМИ
    # =============================================

    def check_system_health(self) -> Dict:
        """Перевірити стан системи"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Перевіряємо кількість записів в основних таблицях
            tables = ['moderators', 'shifts', 'group_users', 'penalties', 'action_logs']
            table_stats = {}
            
            for table in tables:
                cursor.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0] or 0
                table_stats[table] = count
            
            # Перевіряємо активні зміни
            active_shifts = len(self.get_active_shifts())
            
            # Перевіряємо останні логи
            cursor.execute('SELECT MAX(timestamp) FROM action_logs')
            last_log = cursor.fetchone()[0]
            
            # Перевіряємо базу даних на наявність помилок
            cursor.execute('PRAGMA integrity_check')
            integrity_check = cursor.fetchone()[0]
            
            return {
                'table_stats': table_stats,
                'active_shifts': active_shifts,
                'last_log_time': last_log,
                'integrity_check': integrity_check,
                'database_file': self.db_file,
                'check_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Помилка перевірки стану системи: {e}")
            return {
                'error': str(e),
                'check_time': datetime.now().isoformat()
            }
        finally:
            conn.close()


def check_database():
    """Перевірка стану бази даних"""
    try:
        db = Database()
        users = db.get_all_group_users()
        print(f"📊 Знайдено {len(users)} користувачів у базі даних")
        
        for user in users:
            print(f"👤 {user['first_name']} (ID: {user['user_id']})")
            
        return True
    except Exception as e:
        print(f"❌ Помилка перевірки бази даних: {e}")
        return False


# Викликайте цю функцію для тестування
if __name__ == '__main__':
    check_database()