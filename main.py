import os
import random
from uuid import uuid4
from pathlib import Path

from telegram import Update, User, InlineQueryResultPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")                       # токен берём из переменной окружения (Fly secrets)
IMAGES_DIR = Path("images")                      # локальные картинки для /kompli
# RAW-URL публичного репозитория с теми же именами файлов:
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/miza1911/kompli-bot/main/images"

EMOJI_POOL = list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎💖💚💙💜🤍🤎")

_queue: list[str] = []

def next_image() -> Path:
    """Вернёт путь к следующей локальной картинке без повторов до полного цикла."""
    global _queue
    if not _queue:
        files = [
            f.name for f in IMAGES_DIR.iterdir()
            if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".gif"}
        ]
        if not files:
            raise FileNotFoundError("В папке images нет картинок")
        random.shuffle(files)
        _queue = files
    return IMAGES_DIR / _queue.pop()

def pick_emoji() -> str:
    return random.choice(EMOJI_POOL)

def display_name(u: User) -> str:
    return f"@{u.username}" if u and u.username else (u.first_name if u and u.first_name else "друг")

def make_caption(u: User) -> str:
    # 👉 формат: юзернейм + «Твой комплимент дня» + эмодзи в конце
    return f"{display_name(u)} — Твой комплимент дня {pick_emoji()}"

# === КОМАНДЫ ===
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привет! Напиши /kompli — И я пришлю твой комплимент дня! ✨")

async def cmd_kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img_path = next_image()
        caption = make_caption(update.effective_user)
        with open(img_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption)  # без кнопок
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# === INLINE (@бот в любом чате) — без кнопок ===
async def inline_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    # отвечаем даже на пустой запрос, чтобы карточка показывалась в списке
    local_path = next_image()
    filename = local_path.name
    public_url = f"{GITHUB_RAW_BASE}/{filename}"  # должен открываться анонимно!

    result = InlineQueryResultPhoto(
        id=str(uuid4()),
        photo_url=public_url,
        thumb_url=public_url,
        caption=make_caption(update.effective_user),
    )
    await update.inline_query.answer([result], cache_time=0, is_personal=True)

def main():
    if not TOKEN:
        raise SystemExit("❌ Нет токена в переменной TOKEN (секрет Fly).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))
    app.add_handler(InlineQueryHandler(inline_handler))  # можно удалить, если inline не нужен
    print("✅ Бот запущен")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()


