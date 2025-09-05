import os
import random
from telegram import Update, User
from telegram.ext import Application, CommandHandler, ContextTypes
from data import next_image  # берём путь к следующей картинке без повторов

# Токен берётся из Secrets на Fly: TOKEN
TOKEN = os.getenv("TOKEN")

EMOJI_POOL = list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎💖💚💙💜🤍🤎")

def pick_emoji() -> str:
    return random.choice(EMOJI_POOL)

def display_name(u: User) -> str:
    if getattr(u, "username", None):
        return f"@{u.username}"
    if getattr(u, "first_name", None):
        return u.first_name
    return "друг"

async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Команда: /kompli — И ты получишь свой комплимент дня ✨")

async def cmd_kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img_path = next_image()
        name = display_name(update.effective_user)
        caption = f"{pick_emoji()} {name}, твой комплимент дня!"

        with open(img_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    if not TOKEN:
        raise SystemExit("❌ Нет токена. На Fly задаётся в Secrets как TOKEN.")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))

    print("✅ Bot running… команда /kompli (эмодзи + username)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

