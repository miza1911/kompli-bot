import os
import random
from pathlib import Path
from typing import List
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")  # на fly.io задашь через fly secrets set TOKEN=...

# список картинок подключаем из data.py
from data import IMAGES  

# список эмодзи для подписи
EMOJI_POOL = ["✨", "🌟", "💫", "🔥", "☀️", "🌞", "🌈", "💖", "⭐", "🎉", "🚀"]

# очередь для картинок (чтобы не повторялись, пока все не покажет)
_image_queue: List[int] = []


def _reshuffle_images_if_needed():
    global _image_queue
    if not _image_queue:
        if not IMAGES:
            raise RuntimeError("❌ Список IMAGES пуст. Заполни его в data.py и положи файлы в папку images/")
        _image_queue = list(range(len(IMAGES)))
        random.shuffle(_image_queue)


def pick_image_path() -> Path:
    _reshuffle_images_if_needed()
    idx = _image_queue.pop()
    p = Path(IMAGES[idx])
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    return p


def pick_caption(user) -> str:
    if getattr(user, "username", None):
        uname = f"@{user.username}"
    elif getattr(user, "first_name", None):
        uname = user.first_name
    else:
        uname = "друг"
    emoji = random.choice(EMOJI_POOL)
    return f"{emoji} {uname}, твой комплимент дня!"


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /kompli, и я пришлю комплимент дня 🌟")


async def kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img = pick_image_path()
        caption = pick_caption(update.effective_user)
        with open(img, "rb") as f:
            await update.message.reply_photo(f, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")


def main():
    if not TOKEN:
        raise SystemExit("❌ Нет TOKEN. Установи секрет: fly secrets set TOKEN=...")

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("kompli", kompli))

    print("✅ Bot running… команда /kompli")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
