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
TOKEN = os.getenv("TOKEN")  # на Fly хранится в Secrets
IMAGES_DIR = Path("images")  # локальные картинки для /kompli

# ВАЖНО: public RAW-URL (а не /tree/). Замени на свой репозиторий при необходимости.
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/miza1911/kompli-bot/main/images"

EMOJI_POOL = list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎💖💚💙💜🤍🤎")

# Очередь для "без повторов"
_queue: list[str] = []

def _list_image_files() -> list[str]:
    if not IMAGES_DIR.exists():
        raise FileNotFoundError("Папка images не найдена рядом с main.py")
    files = [
        f.name for f in IMAGES_DIR.iterdir()
        if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}
    ]
    if not files:
        raise FileNotFoundError("В папке images нет картинок")
    return files

def next_image() -> Path:
    """Следующая локальная картинка без повторов до полного цикла."""
    global _queue
    if not _queue:
        files = _list_image_files()
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
        "Привет! Команда: /kompli — и я пришлю твой комплимент дня! ✨\n"
        
    )

async def cmd_kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img_path = next_image()
        caption = f"{pick_emoji()} {display_name(update.effective_user)}"
        with open(img_path, "rb") as f:
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton("Ещё ✨", switch_inline_query_current_chat="kompli")
            ]])
            await update.message.reply_photo(photo=f, caption=caption, reply_markup=kb)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# === INLINE ===
async def inline_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    """
    Отдаём одну карточку с публичным RAW-URL из GitHub и кнопкой “Ещё ✨”.
    """
    q = (update.inline_query.query or "").strip().lower()
    if not q or ("kompli" not in q and "компли" not in q and "compl" not in q):
        return  # не засоряем подсказки

    local_path = next_image()
    filename = local_path.name
    public_url = f"{GITHUB_RAW_BASE}/{filename}"  # RAW ссылка

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
        raise SystemExit("❌ Нет токена в переменной окружения TOKEN (секрет Fly).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))
    app.add_handler(InlineQueryHandler(inline_handler))
    print("✅ Бот запущен: /kompli и inline (@бот kompli)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

