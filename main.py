import os
import asyncio
import feedparser
from deep_translator import GoogleTranslator
from flask import Flask
from telegram import Bot

# ==============================
# ENV VARS
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID non impostati")

bot = Bot(token=BOT_TOKEN)

# ==============================
# FLASK
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# RSS ECONOMY NEWS
# ==============================
ECONOMY_RSS_URL = "https://www.investing.com/rss/news_25.rss"  # Economy News RSS

sent_items = set()

async def fetch_economy_news():
    feed = feedparser.parse(ECONOMY_RSS_URL)
    return feed.entries

async def send_economy_news():
    entries = await fetch_economy_news()

    for entry in entries:
        # Evita doppioni
        if entry.id in sent_items:
            continue

        title = entry.get("title", "")
        link = entry.get("link", "")
        published = entry.get("published", "")

        # Traduzione in italiano
        try:
            title_it = GoogleTranslator(source='auto', target='it').translate(title)
        except Exception:
            title_it = title  # fallback se Google Translator fallisce

        message = (
            f"📰 Economia News\n"
            f"{title_it}\n"
            f"🕒 {published}\n"
            f"🔗 {link}"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_items.add(entry.id)
            print(f"[SENT] {title}")
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    # Messaggio di startup
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot Economy News avviato correttamente")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

    while True:
        try:
            await send_economy_news()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(300)  # controlla ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Avvia Flask in background
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler
    asyncio.run(scheduler())
