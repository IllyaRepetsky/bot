import os
import logging
from datetime import datetime
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# === Налаштування ===
TOKEN = "8109666202:AAGDFPzgDc6DwEB0vaJxRigI-Bm_g2pIJFk"
LOG_CHAT_ID = -1003020835257  # Основний лог-канал

# Тільки ці користувачі можуть використовувати /cp
ADMIN_IDS = [7134643873, 6585759419, 1088168546]

GROUP_LIST = {
    -1002850165516: "УЗ Тест",
    -1002689387513: "НПУ",
    -1002231276589: "ЗСУ",
    -1002436885765: "СБУ",
    -1002151129276: "ДСНС",
    -1002206527577: "ДКВС",
    -1002595607468: "МОЗ",
    -1002598770392: "Ст. МОЗ",
    -1002751262762: "Ст. ДСНС",
    -1002517487873: "Ст. ЗСУ",
    -1002154754764: "ВРУ",
    -1002922391721: "Ст. ДКВС",
    -1002507129397: "Ст. НПУ",
    -1002908572334: "Кандидати на Ст. СБУ",
    -1003050216086: "Ст. СБУ",
    -1002547240754: "Ст. ЗМІ",
    -1002200865130: "ЗМІ",
    -1002174855146: "УЗ",
    -1002959034145: "Ст. УЗ",
    -1002118397409: "Парламент",

}

LOG_FILE = os.path.join(os.path.dirname(__file__), "bot_logs.txt")
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write("=== Telegram Bot Logs ===\n")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Стан логування по чатах (True – увімкнено, False – вимкнено)
logging_state: Dict[int, bool] = {cid: True for cid in GROUP_LIST.keys()}

# Чорні списки по чатах
blacklists: Dict[int, list] = {cid: [] for cid in GROUP_LIST.keys()}


# === Допоміжні ===
async def write_log(context: ContextTypes.DEFAULT_TYPE, text: str):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {text}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    try:
        await context.bot.send_message(chat_id=LOG_CHAT_ID, text=line)
    except Exception:
        pass


def get_chat_menu(chat_id: int):
    """Повертає клавіатуру для чату"""
    state = logging_state.get(chat_id, True)
    toggle_btn = "❌Зупинити логування" if state else "✅Запустити логування"
    keyboard = [
        [InlineKeyboardButton("👥 Користувачі", callback_data=f"users_{chat_id}")],
        [InlineKeyboardButton("🚫 Чорний список", callback_data=f"black_{chat_id}")],
        [InlineKeyboardButton(toggle_btn, callback_data=f"toggle_{chat_id}")],
        [InlineKeyboardButton("⬅️ Повернутись назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(keyboard)


# === Команда /cp ===
async def cmd_cp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("❌ У вас немає доступу.")
        return

    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"chat_{cid}")]
        for cid, name in GROUP_LIST.items()
    ]
    await update.message.reply_text("📋 Виберіть чат:", reply_markup=InlineKeyboardMarkup(keyboard))


# === Обробка натискань кнопок ===
async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_main":
        keyboard = [
            [InlineKeyboardButton(name, callback_data=f"chat_{cid}")]
            for cid, name in GROUP_LIST.items()
        ]
        await query.edit_message_text("📋 Виберіть чат:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("chat_"):
        chat_id = int(data.split("_")[1])
        await query.edit_message_text(
            f"Чат: {GROUP_LIST.get(chat_id, chat_id)}",
            reply_markup=get_chat_menu(chat_id)
        )

    elif data.startswith("users_"):
        chat_id = int(data.split("_")[1])
        try:
            members = await context.bot.get_chat_administrators(chat_id)
            users_text = "👥 Користувачі:\n" + "\n".join(
                f"{m.user.full_name} (@{m.user.username}) ID: {m.user.id}"
                for m in members
            )
        except Exception as e:
            users_text = f"❌ Не вдалося отримати користувачів: {e}"

        keyboard = [[InlineKeyboardButton("⬅️ Повернутись назад", callback_data=f"chat_{chat_id}")]]
        await query.edit_message_text(users_text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("black_"):
        chat_id = int(data.split("_")[1])
        bl = blacklists.get(chat_id, [])
        if bl:
            text = "🚫 Чорний список:\n" + "\n".join(bl)
        else:
            text = "🚫 Чорний список порожній."

        keyboard = [[InlineKeyboardButton("⬅️ Повернутись назад", callback_data=f"chat_{chat_id}")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("toggle_"):
        chat_id = int(data.split("_")[1])
        logging_state[chat_id] = not logging_state.get(chat_id, True)
        state = logging_state[chat_id]
        await query.edit_message_text(
            f"Чат: {GROUP_LIST.get(chat_id, chat_id)}\nСтан логування: {'✅ Увімкнено' if state else '⛔ Вимкнено'}",
            reply_markup=get_chat_menu(chat_id)
        )


# === Вітання нових учасників ===
async def on_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    group_name = GROUP_LIST.get(chat.id, chat.title or "невідомої групи")

    for user in update.message.new_chat_members:
        username = f"@{user.username}" if user.username else user.full_name
        welcome_text = (
            f"{username}\n\n"
            f"👋Вітаю! Ви доєднались до Офіційної Telegram групи {group_name}.\n\n"
            "⚠️У Вас є 3 години для відправки форми у даний чат⚠️\n"
            "Не відправлення форми — Блокування у чаті\n\n"
            "📄Форма\n"
            "1. Нікнейм та ID\n"
            "2. Звання\n"
            "3. Фото посвідчення з гри (На фото повинно бути видимий ID та час)"
        )
        await context.bot.send_message(chat_id=chat.id, text=welcome_text)
        await write_log(context, f"👤 Новий учасник у {group_name}: {username}")


# === Логування повідомлень ===
async def on_new_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    chat = update.effective_chat
    if not logging_state.get(chat.id, True):
        return
    log_msg = f"🆕 {GROUP_LIST.get(chat.id, chat.id)} | {msg.from_user.full_name}({msg.from_user.id}): {msg.text or '<медіа>'}"
    await write_log(context, log_msg)


# === Запуск ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("cp", cmd_cp))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, on_new_message))
    logger.info("✅ Бот запущений...")
    app.run_polling()


if __name__ == "__main__":
    main()
