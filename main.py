import os
import random
import uuid
import json
import sqlite3
from pathlib import Path
from typing import List, Optional
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    Message, InlineQuery, InlineQueryResultPhoto,
    InlineQueryResultArticle, InputTextMessageContent, BotCommand
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest

# ---------- ENV ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]                         # секрет на Fly
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")          # https://kompli-bot.fly.dev

# ---------- PATHS / IMAGES ----------
ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

# ---------- PERSISTENT 'DECK' ----------
DB_PATH = Path(os.getenv("DB_PATH", str(ROOT / "deck_state.sqlite3")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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
            rel = p.relative_to(ROOT).as_posix()   # 'images/файл 1.png'
            files.append(f"/{rel}")                # '/images/файл 1.png'
    return files

def _init_deck():
    cur = conn.execute("SELECT order_json, idx FROM deck WHERE id = 1")
    if cur.fetchone() is None:
        order = _discover_images()
        random.shuffle(order)
        conn.execute("INSERT INTO deck(id, order_json, idx) VALUES (1, ?, 0)", (json.dumps(order),))
        conn.commit()

def _next_image_url() -> Optional[str]:
    """Следующая картинка без повторов до конца колоды; затем перетасовать и по кругу."""
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

    rel = order[idx]                               # '/images/подпапка/файл 1.png'
    rel_quoted = "/" + quote(rel.lstrip("/"))      # экранируем пробелы/кириллицу
    url = f"{PUBLIC_URL}{rel_quoted}"

    idx += 1
    conn.execute("UPDATE deck SET order_json = ?, idx = ? WHERE id = 1", (json.dumps(order), idx))
    conn.commit()
    return url

# ---------- TELEGRAM ----------
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

START_TEXT = "Привет! Команда: /kompli — и ты получишь свой комплимент дня! ✨"

@dp.message(commands=["start", "help"])
async def on_start(m: Message):
    await m.answer(START_TEXT)

@dp.message(commands=["kompli"])
async def on_kompli(m: Message):
    url = _next_image_url()
    if not url:
        await m.answer("Пока нет изображений. Добавь файлы в репо в папку /images")
        return
    uname = f"@{(m.from_user.username or m.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌸"
    try:
        await m.answer_photo(photo=url, caption=caption)
    except TelegramBadRequest:
        await m.answer("Не удалось отправить изображение. Попробуй позже.")

# ---------- INLINE ----------
@dp.inline_query()
async def on_inline(q: InlineQuery):
    url = _next_image_url()
    if not url:
        await q.answer(
            results=[],
            switch_pm_text="Добавь картинки в /images",
            switch_pm_parameter="noimages",
            cache_time=1,
            is_personal=True,
        )
        return

    uname = f"@{(q.from_user.username or q.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌼"

    article = InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="Комплимент дня",
        description="Нажми, чтобы отправить картинку с подписью",
        input_message_content=InputTextMessageContent(
            "Выбирай карточку ниже 👇 (это плитка для всплывашки)"
        ),
    )

    photo = InlineQueryResultPhoto(
        id=str(uuid.uuid4()),
        photo_url=url,
        thumb_url=url,
        caption=caption,
    )

    await q.answer([article, photo], cache_time=1, is_personal=True)

# ---------- FASTAPI ----------
app = FastAPI()
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/", response_class=PlainTextResponse)
def health():
    return "ok"

@app.post(f"/webhook/{{token}}")
async def telegram_webhook(request: Request, token: str):
    if token != BOT_TOKEN:
        return {"ok": False}
    try:
        payload = await request.json()
        update = types.Update.model_validate(payload)
        await dp.feed_update(bot, update)
    except Exception:
        return {"ok": True}
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    await bot.set_my_commands([
        BotCommand(command="kompli", description="Отправить комплимент дня"),
        BotCommand(command="help", description="Показать помощь"),
    ])
    await bot.set_webhook(
        f"{PUBLIC_URL}/webhook/{BOT_TOKEN}",
        allowed_updates=["message", "inline_query", "callback_query"],
        drop_pending_updates=False,
    )

# ---------- LOCAL RUN ----------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

