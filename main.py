import os
import asyncio
from datetime import datetime
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator

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
    return "Bot Economy News attivo ✅"

# ==============================
# GLOBAL STATE
# ==============================
sent_news = set()

# ==============================
# FEED RSS
# ==============================
ECONOMY_RSS = "https://www.investing.com/rss/news_25.rss"  # Economy News

# ==============================
# FETCH NEWS
# ==============================
def fetch_economy_news():
    feed = feedparser.parse(ECONOMY_RSS)
    news_items = []

    for entry in feed.entries:
        news_id = getattr(entry, "id", entry.link)  # usa link se id non esiste
        if news_id in sent_news:
            continue

        title_it = GoogleTranslator(source='auto', target='it').translate(entry.title)
        published = getattr(entry, "published", "N/A")
        link = entry.link

        news_items.append({
            "id": news_id,
            "title": title_it,
            "published": published,
            "link": link
        })

    return news_items

# ==============================
# SEND TELEGRAM
# ==============================
async def send_economy_news():
    news_items = fetch_economy_news()
    if not news_items:
        print("[INFO] Nessuna news da inviare")
        return

    for item in news_items:
        message = (
            f"📰 Economia News\n"
            f"{item['title']}\n"
            f"🕒 {item['published']}\n"
            f"🔗 {item['link']}"
        )
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_news.add(item["id"])
            print(f"[SENT] {item['title']}")
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

        await asyncio.sleep(300)  # ogni 5 minuti

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
