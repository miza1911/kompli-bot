# main.py
import os
import random
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from data import next_image  # берём картинку без повторов

TOKEN = os.getenv("TOKEN")  # Fly.io -> Secrets -> TOKEN

def _emoji():
    return random.choice(list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎❤️💚💙💜🤍🤎"))

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /kompli, и я пришлю комплимент дня ✨")

async def cmd_kompli(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or user.username or "друг"
    path = next_image()
    caption = f"Сегодня ты сияешь, {name}! {_emoji()}"
    with open(path, "rb") as f:
        await update.message.reply_photo(photo=f, caption=caption)

def main():
    if not TOKEN:
        raise SystemExit("❌ Нет токена в переменной окружения TOKEN")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
