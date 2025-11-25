import os
import random
from uuid import uuid4
import feedparser

from telegram import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    InputMediaPhoto,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    InlineQueryHandler,
    ChosenInlineResultHandler,
    CallbackQueryHandler,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
EMOJIS = ["✨", "🌟", "🍀", "🌈", "💫", "🧿", "🪄", "🎉", "☀️", "🌸"]

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
        except Exception as e:
            print(f"RSS load error: {e}")
    _all_images_cache = list(set(all_imgs))
    return _all_images_cache

def pick_random_photo() -> str:
    global _seen_images
    images = load_images_from_rss()
    if not images:
        return "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee"

    if len(_seen_images) >= len(images):
        _seen_images = set()
    pool = [x for x in images if x not in _seen_images] or images
    url = random.choice(pool)
    _seen_images.add(url)
    return url

def username_or_name(user) -> str:
    if user.username:
        return f"@{user.username}"
    name = (user.first_name or "").strip() or "Гость"
    return name

def make_caption(for_user) -> str:
    return f"{for_user} · Твой комплимент дня! {random.choice(EMOJIS)}"

# ---------- HANDLERS ----------
async def start(update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "Привет! Я умею делать комплименты. 🌸\n\n"
        "• Для получения комплимента: /kompli"
    )
    await update.message.reply_text(msg)

async def kompli(update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    caption = make_caption(username_or_name(user))
    photo_url = pick_random_photo()
    await update.message.reply_photo(photo=photo_url, caption=caption, parse_mode=ParseMode.HTML)

# ---------- INLINE ----------
ARTICLE_ID = "predict_inline"
BTN_PAYLOAD = "go_predict"

async def inline_query(update, context: ContextTypes.DEFAULT_TYPE):
    preview_url = pick_random_photo()
    result = InlineQueryResultArticle(
        id=ARTICLE_ID,
        title="Получить комплимент дня!🎉",
        description="Нажми — и придет твой комплимент!",
        input_message_content=InputTextMessageContent("⏳ Получаю комплимент…"),
        thumbnail_url=preview_url,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Получить сейчас", callback_data=BTN_PAYLOAD)]]
        ),
    )
    await update.inline_query.answer([result], cache_time=0, is_personal=True)

async def on_chosen_inline(update, context: ContextTypes.DEFAULT_TYPE):
    chosen = update.chosen_inline_result
    if not chosen or chosen.result_id != ARTICLE_ID or not chosen.inline_message_id:
        return

    user = chosen.from_user
    caption = make_caption(username_or_name(user))
    photo_url = pick_random_photo()
    try:
        await context.bot.edit_message_media(
            inline_message_id=chosen.inline_message_id,
            media=InputMediaPhoto(media=photo_url, caption=caption, parse_mode=ParseMode.HTML),
            reply_markup=None,
        )
    except Exception as e:
        print(f"edit_message_media (chosen) failed: {e}")

async def on_callback(update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or q.data != BTN_PAYLOAD:
        return
    user = q.from_user
    caption = make_caption(username_or_name(user))
    photo_url = pick_random_photo()
    try:
        await q.edit_message_media(
            media=InputMediaPhoto(media=photo_url, caption=caption, parse_mode=ParseMode.HTML)
        )
    except Exception as e:
        print(f"edit_message_media (callback) failed: {e}")

# ---------- MAIN ----------
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не найден. Добавь его в Secrets на Fly")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(CommandHandler(["kompli"], kompli))
    app.add_handler(InlineQueryHandler(inline_query))
    app.add_handler(ChosenInlineResultHandler(on_chosen_inline))
    app.add_handler(CallbackQueryHandler(on_callback))

    print("Kompli bot is running…")
    app.run_polling(allowed_updates=[
        "message", "inline_query", "chosen_inline_result", "callback_query"
    ])

if __name__ == "__main__":
    main()
