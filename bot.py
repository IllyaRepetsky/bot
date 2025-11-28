import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from config import Config
from database import Database
from datetime import datetime, timedelta

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class ShiftBot:
    def __init__(self):
        self.config = Config()
        self.db = Database(self.config.DATABASE_FILE)
        self.application = None
    
    def initialize(self):
        """Ініціалізація бота"""
        try:
            print("🔄 Ініціалізація бота контролю змін...")
            self.application = Application.builder().token(self.config.BOT_TOKEN).build()
            
            # Додаємо обробники команд
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(CallbackQueryHandler(self.button_handler))
            
            # Додаємо обробники для всіх повідомлень
            self.application.add_handler(MessageHandler(
                filters.ALL & ~filters.COMMAND, 
                self.handle_all_messages
            ))
            
            print("✅ Бот ініціалізовано успішно")
            return True
            
        except Exception as e:
            print(f"❌ Помилка ініціалізації бота: {e}")
            return False

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник команди /start"""
        try:
            user = update.effective_user
            chat = update.effective_chat
            
            # Додаємо користувача в базу незалежно від типу чату
            self.db.add_group_user(user.id, user.username, user.first_name)
            print(f"✅ Користувач {user.id} доданий/оновлений в базі")
            
            # Якщо це приватний чат - показуємо панель модератора
            if chat.type == 'private':
                moderator = self.db.get_moderator(user.id)
                if not moderator:
                    await update.message.reply_text(
                        "❌ У вас немає прав модератора. Зверніться до адміністратора."
                    )
                    return
                
                # Отримуємо інформацію про поточну зміну
                active_shifts = self.db.get_active_shifts()
                current_shift = next((s for s in active_shifts if s['moderator_id'] == user.id), None)
                
                status = "Активна" if current_shift else "Неактивна"
                total_shifts = moderator['total_shifts']
                
                keyboard = []
                if current_shift:
                    keyboard.append([InlineKeyboardButton("🛑 Завершити зміну", callback_data="end_shift")])
                else:
                    keyboard.append([InlineKeyboardButton("🟢 Розпочати зміну", callback_data="start_shift")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"👋 Вітаю, {user.first_name}!\n"
                    f"Ви відкрили службову панель зміни.\n\n"
                    f"📊 Статус зміни: {status}\n"
                    f"🔢 Всього змін: {total_shifts}",
                    reply_markup=reply_markup
                )
            else:
                # Якщо це група - просто підтверджуємо
                await update.message.reply_text(
                    f"👋 Бот активований! Моніторинг користувачів групи запущено."
                )
            
        except Exception as e:
            logging.error(f"Помилка в команді /start: {e}")
            await update.message.reply_text("❌ Сталася помилка. Спробуйте пізніше.")

    async def handle_all_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник всіх повідомлень - зберігає користувачів та повідомлення в базу"""
        try:
            if not update.message or not update.message.from_user:
                return
                
            user = update.message.from_user
            chat = update.message.chat
            
            print(f"📨 Отримано повідомлення від {user.id} в чаті {chat.id}")
            
            # Додаємо/оновлюємо користувача в базі
            self.db.add_group_user(user.id, user.username, user.first_name)
            print(f"✅ Користувач {user.id} ({user.first_name}) доданий/оновлений в базі")
            
            # Зберігаємо повідомлення в базу
            message_text = update.message.text or update.message.caption or "[Медіа-повідомлення]"
            self.db.add_group_message(user.id, message_text, 'sent')
            print(f"💬 Повідомлення від {user.id} збережено в базі: {message_text[:50]}...")
            
            # Перевіряємо чи користувач заблокований або в муті (тільки для груп)
            if chat.type in ['group', 'supergroup']:
                user_status = self.db.is_user_banned_or_muted(user.id)
                
                if user_status['is_banned']:
                    # Видаляємо повідомлення заблокованого користувача
                    try:
                        await update.message.delete()
                        print(f"🗑️ Видалено повідомлення заблокованого користувача {user.id}")
                    except Exception as e:
                        print(f"❌ Не вдалося видалити повідомлення: {e}")
                
                elif user_status['is_muted'] and user_status['mute_until']:
                    mute_until = datetime.fromisoformat(user_status['mute_until'])
                    if mute_until > datetime.now():
                        # Видаляємо повідомлення замученого користувача
                        try:
                            await update.message.delete()
                            print(f"🔇 Видалено повідомлення замученого користувача {user.id}")
                        except Exception as e:
                            print(f"❌ Не вдалося видалити повідомлення: {e}")
                    else:
                        # Мут закінчився - знімаємо його
                        self.db.unmute_user(user.id)
                        print(f"🔊 Мут знято з користувача {user.id}")
                
        except Exception as e:
            logging.error(f"Помилка обробки повідомлення: {e}")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обробник кнопок"""
        try:
            query = update.callback_query
            await query.answer()
            
            user = query.from_user
            moderator = self.db.get_moderator(user.id)
            
            if not moderator:
                await query.edit_message_text("❌ У вас немає прав модератора.")
                return
            
            if query.data == "start_shift":
                # Початок зміни
                shift_id = self.db.start_shift(user.id)
                if shift_id:
                    # Логування
                    self.db.add_log(user.id, "shift_started", f"Зміна #{shift_id} розпочата", "telegram_bot")
                    
                    await query.edit_message_text(
                        f"✅ Зміну розпочато!\n"
                        f"Час початку: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                        f"Не забудьте завершити зміну командою /start"
                    )
                else:
                    await query.edit_message_text("❌ У вас вже є активна зміна!")
            
            elif query.data == "end_shift":
                # Завершення зміни
                success = self.db.end_shift(user.id)
                if success:
                    # Логування
                    self.db.add_log(user.id, "shift_ended", "Зміна завершена", "telegram_bot")
                    
                    await query.edit_message_text(
                        f"🛑 Зміну завершено!\n"
                        f"Час завершення: {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n"
                        f"Дякуємо за роботу! 👏"
                    )
                else:
                    await query.edit_message_text("❌ У вас немає активної зміни!")
            
        except Exception as e:
            logging.error(f"Помилка в button_handler: {e}")
            try:
                await query.edit_message_text("❌ Сталася помилка. Спробуйте пізніше.")
            except:
                await query.message.reply_text("❌ Сталася помилка. Спробуйте пізніше.")

    def run(self):
        """Запуск бота"""
        try:
            if self.application is None:
                if not self.initialize():
                    print("❌ Не вдалося ініціалізувати бота")
                    return
            
            print("🎯 Бот контролю змін запущено. Очікування повідомлень...")
            print("💡 Використовуйте /start для перевірки")
            print("👥 Додайте бота в групу для моніторингу користувачів")
            print("💬 Бот автоматично зберігатиме всі повідомлення та користувачів в базу даних")
            print("⚠️  Для завершення роботи натисніть Ctrl+C")
            
            self.application.run_polling()
            
        except KeyboardInterrupt:
            print("\n🛑 Отримано Ctrl+C...")
            print("✅ Бот зупинений")
        except Exception as e:
            print(f"❌ Критична помилка: {e}")

def main():
    """Головна функція"""
    print("=" * 50)
    print("👨‍💼 Запуск бота контролю змін працівників")
    print("=" * 50)
    
    bot = ShiftBot()
    bot.run()

async def update_user_status_from_telegram(self, user_id: int):
    """Оновити статус користувача з Telegram"""
    try:
        # Отримуємо інформацію про користувача в групі
        url = f"https://api.telegram.org/bot{self.config.BOT_TOKEN}/getChatMember"
        payload = {
            'chat_id': self.config.TELEGRAM_GROUP_ID,
            'user_id': user_id
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            data = response.json()
            member = data.get('result', {})
            status = member.get('status', '')
            
            # Оновлюємо статус в базі даних
            if status in ['kicked', 'banned']:
                self.db.ban_user(user_id, "Автоматичне оновлення", "Система")
            elif status == 'restricted':
                # Перевіряємо чи є обмеження на відправку повідомлень
                permissions = member.get('permissions', {})
                if not permissions.get('can_send_messages', True):
                    self.db.mute_user(user_id, (datetime.now() + timedelta(hours=1)).isoformat())
            elif status == 'administrator':
                self.db.set_user_admin(user_id, True)
            else:
                # Якщо статус member/creator - знімаємо всі обмеження
                self.db.unban_user(user_id)
                self.db.unmute_user(user_id)
                
    except Exception as e:
        logging.error(f"Помилка оновлення статусу користувача {user_id}: {e}")

# Додайте ці методи до класу ShiftBot в bot.py

async def handle_penalty_notification(self, moderator_id: int, penalty_type: str, value: int, reason: str, issued_by: str):
    """Надіслати сповіщення про покарання модератору"""
    try:
        moderator = self.db.get_moderator(moderator_id)
        if moderator:
            penalty_names = {
                'fine': 'штраф',
                'warning': 'попередження',
                'reprimand': 'догану'
            }
            
            message = (
                f"⚖️ **Ви отримали {penalty_names.get(penalty_type, 'покарання')}**\n\n"
                f"📋 Тип: {penalty_names.get(penalty_type, penalty_type)}\n"
                f"🔢 Значення: {value}\n"
                f"📝 Причина: {reason}\n"
                f"🔧 Видав: {issued_by}\n"
                f"⏰ Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Якщо ви не згодні з цим рішенням, зверніться до адміністрації."
            )
            
            await self.application.bot.send_message(
                chat_id=moderator_id,
                text=message,
                parse_mode='Markdown'
            )
    except Exception as e:
        logging.error(f"Помилка відправки сповіщення про покарання: {e}")

if __name__ == "__main__":
    main()
