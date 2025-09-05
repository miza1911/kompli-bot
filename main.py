import os
import random
from uuid import uuid4
from pathlib import Path

from telegram import (
    Update, User, InlineQueryResultPhoto,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")  # хранится в Fly Secrets
IMAGES_DIR = Path("images")  # локальные картинки для /kompli


BASE_URL = "https://raw.githubusercontent.com/miza1911/kompli-bot/main/images"

EMOJI_POOL = list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎💖💚💙💜🤍🤎")

# ротация без повторов (имена файлов)
_queue: list[str] = []

def _ensure_images_list() -> list[str]:
    files = [
        f.name for f in IMAGES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    ]
    if not files:
        raise FileNotFoundError("В папке images нет картинок")
    return files

def next_image() -> Path:
    """Следующая локальная картинка без повторов до полного цикла."""
    global _queue
    if not _queue:
        files = _ensure_images_list()
        random.shuffle(files)
        _queue = files
    return IMAGES_DIR / _queue.pop()

def pick_emoji() -> str:
    return random.choice(EMOJI_POOL)

def display_name(u: User) -> str:
    return f"@{u.username}" if u and u.username else (u.first_name if u and u.first_name else "друг")

# === КОМАНДЫ ===
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! /kompli — И ты получишь свой комплимент дня! ✨\n"
        
    )

async def cmd_kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img_path = next_image()
        caption = f"{pick_emoji()} {display_name(update.effective_user)}"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("Ещё ✨", switch_inline_query_current_chat="kompli")
        ]])
        with open(img_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption, reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# === INLINE ===
async def inline_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """Выдаём одну карточку через публичный raw-URL + кнопка 'Ещё ✨'."""
    q = (update.inline_query.query or "").strip().lower()
    if not q or ("kompli" not in q and "компли" not in q and "compl" not in q):
        return

    local_path = next_image()
    filename = local_path.name
    public_url = f"{BASE_URL}/{filename}"

    caption = f"{pick_emoji()} {display_name(update.effective_user)}"
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("Ещё ✨", switch_inline_query_current_chat="kompli")
    ]])

    result = InlineQueryResultPhoto(
        id=str(uuid4()),
        photo_url=public_url,
        thumb_url=public_url,
        caption=caption,
        reply_markup=kb,
    )
    await update.inline_query.answer([result], cache_time=0, is_personal=True)

def main():
    if not TOKEN:
        raise SystemExit("❌ Нет токена (секрет TOKEN на Fly).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))
    app.add_handler(InlineQueryHandler(inline_handler))
    print("✅ Бот запущен: /kompli и inline (@бот kompli)")
    app.run_polling(drop_pending_updates=True)

if name == "__main__":
    main()
