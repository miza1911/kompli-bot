import os
import json
import random
import sqlite3
import uuid
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultPhoto
from aiogram.exceptions import TelegramBadRequest

# -------- ENV --------
BOT_TOKEN = os.environ["BOT_TOKEN"]                   # секрет на Fly
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")    # https://kompli-bot.fly.dev

# -------- PATHS / STATIC --------
ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "images"                         # кладём картинки сюда (в корне репо /images)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# -------- DB (deck state) --------
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

def _discover_images() -> List[str]:
    """Вернём относительные URL '/images/...'; любые имена/подпапки, кириллица ок."""
    exts = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    files: List[str] = []
    for p in IMAGES_DIR.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts and not p.name.startswith("."):
            rel = p.relative_to(ROOT).as_posix()     # 'images/файл 1.png'
            files.append(f"/{rel}")                  # '/images/файл 1.png'
    return files

def _init_deck():
    cur = conn.execute("SELECT order_json, idx FROM deck WHERE id = 1")
    if cur.fetchone() is None:
        order = _discover_images()
        random.shuffle(order)
        conn.execute("INSERT INTO deck(id, order_json, idx) VALUES (1, ?, 0)", (json.dumps(order),))
        conn.commit()

def _next_image_url() -> Optional[str]:
    """Следующая картинка без повторов до конца колоды; перемешиваем и по кругу."""
    _init_deck()
    cur = conn.execute("SELECT order_json, idx FROM deck WHERE id = 1")
    order_json, idx = cur.fetchone()
    order = json.loads(order_json)

    disk = _discover_images()
    if set(order) != set(disk):
        order = disk
        random.shuffle(order)
        idx = 0

    if not order:
        conn.execute("UPDATE deck SET order_json = ?, idx = 0 WHERE id = 1", (json.dumps(order),))
        conn.commit()
        return None

    if idx >= len(order):
        random.shuffle(order)
        idx = 0

    rel = order[idx]                                  # '/images/подпапка/файл 1.png'
    rel_quoted = "/" + quote(rel.lstrip("/"))         # экранируем пробелы/кириллицу
    url = f"{PUBLIC_URL}{rel_quoted}"

    idx += 1
    conn.execute("UPDATE deck SET order_json = ?, idx = ? WHERE id = 1", (json.dumps(order), idx))
    conn.commit()
    return url

# -------- TELEGRAM --------
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

START_TEXT = "Привет! Команда: /kompli — и ты получишь свой комплимент дня! ✨"

@dp.message(Command("start"))
async def on_start(m: types.Message):
    await m.answer(START_TEXT)

@dp.message(Command("kompli"))
async def on_kompli(m: types.Message):
    url = _next_image_url()
    if not url:
        await m.answer("Пока нет изображений. Добавь файлы в репо: /images")
        return
    uname = f"@{(m.from_user.username or m.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌸"
    try:
        await m.answer_photo(photo=url, caption=caption)
    except TelegramBadRequest:
        await m.answer("Не удалось отправить изображение. Попробуй позже.")

# ====== INLINE: всплывающее окно по @username⎵ ======
@dp.inline_query()
async def on_inline(q: InlineQuery):
    """
    Возвращаем одну плитку. По нажатию отправится фото + подпись с ником.
    cache_time=1 и is_personal=True — чтобы подпись была персональной.
    """
    url = _next_image_url()
    if not url:
        await q.answer(
            results=[],
            switch_pm_text="Добавь картинки в /images",
            switch_pm_parameter="noimages",
            cache_time=1,
            is_personal=True
        )
        return

    uname = f"@{(q.from_user.username or q.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌼"

    result = InlineQueryResultPhoto(
        id=str(uuid.uuid4()),
        photo_url=url,
        thumb_url=url,
        caption=caption,
        title="Отправить комплимент дня",
        description="Картинка + подпись с твоим ником",
    )
    await q.answer([result], cache_time=1, is_personal=True)
# ====== /INLINE ======

# -------- FASTAPI / WEBHOOK --------
app = FastAPI()
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/", response_class=PlainTextResponse)
def health():
    return "ok"

@app.post(f"/webhook/{{token}}")
async def telegram_webhook(request: Request, token: str):
    # Принимаем апдейты только по своему токену
    if token != BOT_TOKEN:
        return {"ok": False}

    try:
        payload = await request.json()
    except Exception:
        # на всякий пожарный
        return {"ok": True}

    try:
        update = types.Update.model_validate(payload)  # aiogram 3.x — без context
        await dp.feed_update(bot, update)
    except Exception as e:
        # не роняем 500 — логируй у себя, но телеге всегда OK
        # можно добавить print(str(e)) — увидишь в логах Fly
        return {"ok": True}

    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    # Явно разрешаем inline
    await bot.set_webhook(
        f"{PUBLIC_URL}/webhook/{BOT_TOKEN}",
        allowed_updates=["message", "inline_query", "callback_query"],
        drop_pending_updates=False
    )
