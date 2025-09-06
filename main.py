import os
import json
import random
import sqlite3
import uuid
from pathlib import Path
from typing import List
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultPhoto
from aiogram.exceptions import TelegramBadRequest



# ---------- ENV ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]              # токен от BotFather
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")  # напр. https://kompli-bot.fly.dev

# ---------- PATHS / STATIC ----------
ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "static" / "images"
if not IMAGES_DIR.exists():
    raise RuntimeError("Создайте папку app/static/images и добавьте изображения.")

# ---------- PERSISTENT 'DECK' STATE ----------
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "deck_state.sqlite3")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB_PATH)
conn.execute("""
CREATE TABLE IF NOT EXISTS deck (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    order_json TEXT NOT NULL,
    idx INTEGER NOT NULL
)
""")
conn.commit()

def _load_images() -> List[str]:
    """
    Собираем все изображения из app/static/images и подпапок.
    Храним относительные пути вида '/static/images/sub/файл 1.png'
    """
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files: List[str] = []
    for p in IMAGES_DIR.rglob("*"):
        if (
            p.is_file()
            and p.suffix.lower() in exts
            and not p.name.startswith(".")
        ):
            rel = p.relative_to(ROOT).as_posix()  # 'static/images/файл 1.png'
            files.append(f"/{rel}")
    if not files:
        raise RuntimeError("В app/static/images нет изображений.")
    return files

def _init_deck_if_needed():
    cur = conn.execute("SELECT order_json, idx FROM deck WHERE id = 1")
    if cur.fetchone() is None:
        files = _load_images()
        random.shuffle(files)
        conn.execute(
            "INSERT INTO deck(id, order_json, idx) VALUES (1, ?, 0)",
            (json.dumps(files),),
        )
        conn.commit()

def _get_next_image_url() -> str:
    """Вернёт HTTPS-URL следующей картинки; на конце тасует и идёт по кругу."""
    _init_deck_if_needed()
    cur = conn.execute("SELECT order_json, idx FROM deck WHERE id = 1")
    order_json, idx = cur.fetchone()
    order = json.loads(order_json)

    # Если набор файлов изменился на диске — пересобираем колоду
    disk_files = _load_images()
    if set(order) != set(disk_files):
        order = disk_files
        random.shuffle(order)
        idx = 0

    if idx >= len(order):
        random.shuffle(order)
        idx = 0

    rel = order[idx]  # '/static/images/подпапка/файл 1.png'
    rel_quoted = "/" + quote(rel.lstrip("/"))  # кодируем пробелы/кириллицу
    full_url = f"{PUBLIC_URL}{rel_quoted}"

    idx += 1
    conn.execute(
        "UPDATE deck SET order_json = ?, idx = ? WHERE id = 1",
        (json.dumps(order), idx),
    )
    conn.commit()
    return full_url

# ---------- TELEGRAM ----------
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

START_TEXT = "Привет! Команда: /kompli — и ты получишь свой комплимент дня! 🌞"

@dp.message(Command("start"))
async def on_start(m: types.Message):
    await m.answer(START_TEXT)

@dp.message(Command("kompli"))
async def on_kompli(m: types.Message):
    try:
        url = _get_next_image_url()
        uname = f"@{(m.from_user.username or m.from_user.full_name).replace(' ', '_')}"
        caption = f"Твой комплимент дня, {uname} 🌸"
        await m.answer_photo(photo=url, caption=caption)
    except TelegramBadRequest:
        await m.answer("Не удалось отправить изображение. Попробуй ещё раз чуть позже.")

@dp.inline_query()
async def on_inline(q: InlineQuery):
    """
    Пользователь набрал @botname⎵ → показываем одну плитку.
    По нажатию отправится фото с подписью. Почти отключаем кэш,
    чтобы подпись адресовалась вызвавшему пользователю.
    """
    url = _get_next_image_url()
    uname = f"@{(q.from_user.username or q.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌼"

    results = [
        InlineQueryResultPhoto(
            id=str(uuid.uuid4()),
            photo_url=url,
            thumb_url=url,
            caption=caption,
        )
    ]
    await q.answer(results=results, cache_time=1, is_personal=True)

# ---------- FASTAPI / WEBHOOK ----------
app = FastAPI()

# Отдаём статику (картинки)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

@app.get("/", response_class=PlainTextResponse)
def health():
    return "ok"

@app.post(f"/webhook/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(f"{PUBLIC_URL}/webhook/{BOT_TOKEN}")

if __name__ == "__main__":
    main()

