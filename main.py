# main.py — один файл, всё в одном: aiogram v3 + FastAPI + inline-всплывашка + /kompli
import os
import random
import uuid
from telebot import TeleBot, types

TOKEN = os.getenv("BOT_TOKEN", "YOUR_TOKEN_HERE")
bot = TeleBot(TOKEN, parse_mode="HTML")

# --- ваши картинки на GitHub (RAW HTTPS ссылки) ---
IMAGES = [
    # примеры: замените на свои raw-ссылки
    "https://raw.githubusercontent.com/miza1911/kompli-bot/main/images/photo_2025-09-05_21-49-56.jpg",
   
]

COMPLIMENTS = [
    "Ты сегодня блестяще выглядишь ✨",
    "Твоё чувство юмора — топ! 😄",
    "С тобой всё получается легче 🌸",
]

# --- Команды (подсказки при вводе / ) ---
bot.set_my_commands([
    types.BotCommand("kompli", "Отправить комплимент дня"),
    types.BotCommand("help", "Показать помощь"),
])

def pick():
    return random.choice(IMAGES), random.choice(COMPLIMENTS)

# --- /kompli: обычная команда ---
@bot.message_handler(commands=["kompli"])
def cmd_kompli(m):
    img, text = pick()
    bot.send_photo(m.chat.id, img, caption=f"Комплимент дня: {text}")

@bot.message_handler(commands=["help", "start"])
def cmd_help(m):
    bot.reply_to(
        m,
        "Напиши /kompli или используй inline:\n"
        "в любом чате введи @<имя_бота> и выбери карточку."
    )

# --- INLINE MODE: @botname → всплывающее окно с карточкой ---
@bot.inline_handler(func=lambda q: True)
def inline(q: types.InlineQuery):
    img, text = pick()
    results = [
        types.InlineQueryResultPhoto(
            id=str(uuid.uuid4()),
            photo_url=img,
            thumb_url=img,
            caption=f"Комплимент дня: {text}"
        )
    ]
    # cache_time=0, чтобы изменения были заметны сразу
    bot.answer_inline_query(q.id, results=results, cache_time=0, is_personal=True)

bot.polling(none_stop=True)



# ---------- ENV ----------
BOT_TOKEN = os.environ["BOT_TOKEN"]                         # секрет на Fly
PUBLIC_URL = os.environ["PUBLIC_URL"].rstrip("/")          # https://kompli-bot.fly.dev

# ---------- PATHS / IMAGES ----------
ROOT = Path(__file__).parent
IMAGES_DIR = ROOT / "images"                               # картинки в /images (в корне репо)
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
        await m.answer("Пока нет изображений. Добавь файлы в репо в папку /images")
        return
    uname = f"@{(m.from_user.username or m.from_user.full_name).replace(' ', '_')}"
    caption = f"Твой комплимент дня, {uname} 🌸"
    try:
        await m.answer_photo(photo=url, caption=caption)
    except TelegramBadRequest:
        await m.answer("Не удалось отправить изображение. Попробуй позже.")

# ---------- INLINE (всплывающее окно при @бот⎵) ----------
from aiogram.types import (
    InlineQuery, InlineQueryResultPhoto,
    InlineQueryResultArticle, InputTextMessageContent
)

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

    # 1) «Серая» плитка (Article) — просто для красивого всплывания
    article = InlineQueryResultArticle(
        id=str(uuid.uuid4()),
        title="Комплимент дня",
        description="Нажми, чтобы отправить картинку с подписью",
        input_message_content=InputTextMessageContent(
            "Выбирай карточку ниже 👇 (это плитка для всплывашки)"
        ),
    )

    # 2) Реальная отправка фото
    photo = InlineQueryResultPhoto(
        id=str(uuid.uuid4()),
        photo_url=url,
        thumb_url=url,
        caption=caption,
        title="Отправить картинку",      # не везде видно, но не мешает
        description="Картинка + подпись",
    )

    # Сначала плитка, потом фото
    await q.answer([article, photo], cache_time=1, is_personal=True)

# ---------- FASTAPI / WEBHOOK ----------
app = FastAPI()
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

@app.get("/", response_class=PlainTextResponse)
def health():
    return "ok"

@app.post(f"/webhook/{{token}}")
async def telegram_webhook(request: Request, token: str):
    # принимаем апдейты только по правильному токену в пути
    if token != BOT_TOKEN:
        return {"ok": False}
    try:
        payload = await request.json()
        update = types.Update.model_validate(payload)  # aiogram 3.x
        await dp.feed_update(bot, update)
    except Exception:
        # не роняем вебхук 500-кой — всегда отвечаем 200/ok
        return {"ok": True}
    return {"ok": True}

@app.on_event("startup")
async def on_startup():
    # ставим вебхук с разрешением на inline
    await bot.set_webhook(
        f"{PUBLIC_URL}/webhook/{BOT_TOKEN}",
        allowed_updates=["message", "inline_query", "callback_query"],
        drop_pending_updates=False,
    )
