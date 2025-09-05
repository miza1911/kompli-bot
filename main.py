import os
import random
from uuid import uuid4
from pathlib import Path
from urllib.parse import quote

from telegram import Update, User, InlineQueryResultPhoto
from telegram.ext import Application, CommandHandler, ContextTypes, InlineQueryHandler

# === НАСТРОЙКИ ===
TOKEN = os.getenv("TOKEN")  
IMAGES_DIR = Path("images")  


GITHUB_RAW_BASE = "https://raw.githubusercontent.com/miza1911/kompli-bot/main/images"

EMOJI_POOL = list("✨🌟💫☀️🌈🔥🌸⭐️🌼🌻🌙💎💖💚💙💜🤍🤎")

# ротация без повторов
_queue: list[str] = []

def next_image() -> Path:
    """Следующая локальная картинка без повторов до полного цикла."""
    global _queue
    if not _queue:
        if not IMAGES_DIR.exists():
            raise FileNotFoundError("Папка images не найдена в проекте")
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

# === КОМАНДЫ ===
async def cmd_start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Напиши /kompli — И ты получишь комплимент дня! ✨"
    )

async def cmd_kompli(update: Update, _: ContextTypes.DEFAULT_TYPE):
    try:
        img_path = next_image()
        caption = f"Твой комплимент дня, {display_name(update.effective_user)}! {pick_emoji()}"
        with open(img_path, "rb") as f:
            await update.message.reply_photo(photo=f, caption=caption)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

# === INLINE  ===
async def inline_handler(update: Update, _: ContextTypes.DEFAULT_TYPE):
    # даже при пустом запросе '@noskompli_bot ' показываем плитку
    _ = (update.inline_query.query or "")

    # берём следующий файл из твоей ротации
    local_path = next_image()
    filename = quote(local_path.name)              # экранируем пробелы/кириллицу
    bust = uuid4().hex                             # "соль" против кеша
    public_url = f"{GITHUB_RAW_BASE}/{filename}?v={bust}"

    caption = f"Твой комплимент дня, {display_name(update.effective_user)}! {pick_emoji()}"

    result = InlineQueryResultPhoto(
        id=str(uuid4()),                           # уникальный id результата
        photo_url=public_url,
        thumb_url=public_url,
        title="Отправить комплимент дня",          # заголовок плитки
        description="Случайная картинка с подписью ✨",
        caption=caption                            # подпись как у /kompli
    )

    # без кеша, чтобы каждый раз была новая карточка/картинка
    await update.inline_query.answer([result], cache_time=0, is_personal=True)



def main():
    if not TOKEN:
        raise SystemExit("❌ Нет токена в переменной TOKEN (секрет Fly).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kompli", cmd_kompli))
    app.add_handler(InlineQueryHandler(inline_handler))
    print("✅ Бот запущен: /kompli и inline (@бот)")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

