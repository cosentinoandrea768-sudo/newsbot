import os
import json
import asyncio
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
from html import unescape

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
    return "Bot Economy News LIVE ✅"

# ==============================
# FILE PERSISTENZA
# ==============================
STORAGE_FILE = "sent_news.json"

def load_sent_news():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_sent_news(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(list(data), f)

sent_news = set()  # inizialmente vuoto
# ==============================
# TRANSLATOR
# ==============================
translator = GoogleTranslator(source='auto', target='it')

def translate_text(text):
    try:
        return translator.translate(text)
    except:
        return text

# ==============================
# RSS FEEDS
# ==============================
RSS_FEEDS = [
    "https://www.investing.com/rss/news_14.rss",
    "https://www.investing.com/rss/news_301.rss",
    "https://www.investing.com/rss/news_355.rss",
    "https://www.investing.com/rss/news_357.rss",
    "https://www.investing.com/rss/news_11.rss"
]

# ==============================
# FETCH NEW NEWS
# ==============================
def fetch_new_news():
    new_items = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            news_id = getattr(entry, "id", entry.link)

            if news_id in sent_news:
                continue

            title_it = translate_text(entry.title)

            summary_raw = getattr(entry, "summary", "")
            summary_text = (
                unescape(summary_raw)
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )
            summary_it = translate_text(summary_text) if summary_text else ""

            new_items.append({
                "id": news_id,
                "title": title_it,
                "summary": summary_it,
                "published": getattr(entry, "published", "N/A"),
                "link": entry.link
            })

    return new_items

# ==============================
# SEND NEWS
# ==============================
async def send_news():
    news_items = fetch_new_news()

    if not news_items:
        print("[DEBUG] Nessuna nuova news")
        return

    for item in news_items:
        message = (
            f"📰 BitPath News\n"
            f"{item['title']}\n"
            f"{item['summary']}\n"
            f"🕒 {item['published']}\n"
            f"🔗 {item['link']}"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_news.add(item["id"])
            save_sent_news(sent_news)
            print(f"[SENT] {item['title']}")
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():

    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 Bot Economy News LIVE avviato"
    )

    # 🔹 Inizializzazione: carica storico dal file e aggiunge feed correnti
    sent_news.update(load_sent_news())
    print(f"[DEBUG] Caricati {len(sent_news)} news dal file")

    # 🔹 Salva ID correnti dei feed senza inviare nulla
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            news_id = getattr(entry, "id", entry.link)
            sent_news.add(news_id)
    save_sent_news(sent_news)
    print(f"[DEBUG] Storico iniziale registrato senza invio")

    while True:
        try:
            await send_news()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(300)  # 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()
    asyncio.run(scheduler())
