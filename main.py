import os
import random
import uuid
from typing import Optional

import feedparser
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineQuery, InlineQueryResultPhoto
from aiogram.exceptions import TelegramBadRequest
import uvicorn

# ---------- ENV ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")

# ---------- PINTEREST RSS ----------
PINTEREST_RSS = [
    "https://ru.pinterest.com/sisiboroda/komplik.rss",
]

_seen_images = set()
_all_images_cache = []

def load_images_from_rss() -> list:
    global _all_images_cache
    if _all_images_cache:
        return _all_images_cache
    all_imgs = []
    for rss in PINTEREST_RSS:
        try:
            feed = feedparser.parse(rss)
            for entry in feed.entries:
                if "media_content" in entry:
                    for media in entry.media_content:
                        url = media.get("url")
                        if url and url.startswith("http"):
                            all_imgs.append(url)
                elif "links" in entry:
                    for l in entry.links:
                        if l.get("type", "").startswith("image"):
                            all_imgs.append(l["href"])
        except:
            pass
    _all_images_cache = list(set(all_imgs))
    return _all_images_cache

def get_next_pinterest_image() -> Optional[str]:
    global _seen_images
    images = load_images_from_rss()
    if not images:
        return None
    if len(_seen_images) >= len(images):
        _seen_images = set()
    available = [x for x in images if x not in _seen_images]
    if not available:
        return None
    img = random.choice(available)
    _seen_images.add(img)
    return img

# ---------- TELEGRAM ----------
bot = Bot(BOT_TOKEN)
dp = Dispatcher()

START_TEXT = "Привет! Команда: /kompli — и ты получишь свой комплимент дня! 🌞"

@dp.message(Command("start"))
async def on_start(m: types.Message):
    await m.answer(START_TEXT)

@dp.message(Command("kompli"))
async def on_kompli(m: types.Message):
    url = get_next_pinterest_image()
    if not url:
        await m.answer("Не удалось получить изображение. Проверь RSS ссылки.")
        return
    try:
        uname = f"@{(m.from_user.username or m.from_user.full_name).replace(' ', '_')}"
        caption = f"Твой комплимент дня, {uname} 🌸"
        await m.answer_photo(photo=url, caption=caption)
    except TelegramBadRequest:
        await m.answer("Не удалось отправить изображение. Попробуй позже.")

@dp.inline_query()
async def on_inline(q: InlineQuery):
    url = get_next_pinterest_image()
    if not url:
        await q.answer(
            results=[],
            switch_pm_text="Нет картинок",
            switch_pm_parameter="noimages",
            cache_time=1,
            is_personal=True
        )
        return
    uname = f"@{(q.from_user.username or q.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌼"
    results = [InlineQueryResultPhoto(
        id=str(uuid.uuid4()),
        photo_url=url,
        thumb_url=url,
        caption=caption
    )]
    await q.answer(results=results, cache_time=1, is_personal=True)

# ---------- FASTAPI / WEBHOOK ----------
app = FastAPI()

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
    # ставим webhook на Fly URL
    await bot.set_webhook(f"{PUBLIC_URL}/webhook/{BOT_TOKEN}")

# ---------- RUN SERVER ----------
# Важно: всегда запускаем uvicorn, без if __name__ == "__main__"
uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
