import os
import json
import asyncio
import gc
from datetime import date
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
# COSTANTI
# ==============================
STORAGE_FILE = "sent_news.json"
DAILY_COUNTS_FILE = "daily_counts.json"
MAX_SENT_NEWS = 200
INIT_FEED_LIMIT = 5
FETCH_LIMIT = 5
DAILY_LIMIT_PER_FEED = 5  # max news al giorno per feed

# ==============================
# PERSISTENZA - NEWS GIÀ INVIATE
# ==============================
def load_sent_news():
    if os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, "r") as f:
            try:
                return set(json.load(f))
            except:
                return set()
    return set()

def save_sent_news(data):
    with open(STORAGE_FILE, "w") as f:
        json.dump(list(data), f)

sent_news = set()

# ==============================
# PERSISTENZA - CONTATORE GIORNALIERO
# ==============================
def load_daily_counts():
    if os.path.exists(DAILY_COUNTS_FILE):
        with open(DAILY_COUNTS_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_daily_counts(data):
    with open(DAILY_COUNTS_FILE, "w") as f:
        json.dump(data, f)

def get_today():
    return str(date.today())  # es. "2026-05-05"

def can_send_from_feed(daily_counts, feed_url):
    today = get_today()
    entry = daily_counts.get(feed_url, {"date": "", "count": 0})
    if entry["date"] != today:
        return True  # nuovo giorno → resetta automaticamente
    return entry["count"] < DAILY_LIMIT_PER_FEED

def increment_feed_count(daily_counts, feed_url):
    today = get_today()
    entry = daily_counts.get(feed_url, {"date": "", "count": 0})
    if entry["date"] != today:
        daily_counts[feed_url] = {"date": today, "count": 1}
    else:
        daily_counts[feed_url]["count"] += 1

# ==============================
# TRANSLATOR
# ==============================
translator = GoogleTranslator(source="auto", target="it")

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
    "https://www.investing.com/rss/news_11.rss"
]

# ==============================
# FETCH NUOVE NEWS
# ==============================
def fetch_new_news():
    new_items = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:FETCH_LIMIT]:
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
                "feed_url": feed_url,  # traccia la fonte per il limite giornaliero
                "title": title_it,
                "summary": summary_it,
                "published": getattr(entry, "published", "N/A"),
                "link": entry.link
            })

    return new_items

# ==============================
# INVIO NEWS
# ==============================
async def send_news():
    global sent_news

    daily_counts = load_daily_counts()
    news_items = fetch_new_news()

    if not news_items:
        print("[DEBUG] Nessuna nuova news")
        return

    for item in news_items:
        feed_url = item["feed_url"]

        # Controlla limite giornaliero per questo feed
        if not can_send_from_feed(daily_counts, feed_url):
            print(f"[SKIP] Limite giornaliero raggiunto per {feed_url}")
            sent_news.add(item["id"])  # marca come visto così non ricompare
            continue

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
            increment_feed_count(daily_counts, feed_url)
            save_daily_counts(daily_counts)

            if len(sent_news) > MAX_SENT_NEWS:
                sent_news = set(list(sent_news)[-100:])

            save_sent_news(sent_news)

            print(f"[SENT] {item['title']}")

        except Exception as e:
            print("[TELEGRAM ERROR]", e)

    gc.collect()

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    global sent_news

    await bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 Bot Economy News LIVE avviato"
    )

    # Carica storico news già inviate
    sent_news.update(load_sent_news())
    print(f"[DEBUG] Caricati {len(sent_news)} ID dal file")

    # Registra feed correnti senza inviare (evita flood all'avvio)
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:INIT_FEED_LIMIT]:
            news_id = getattr(entry, "id", entry.link)
            sent_news.add(news_id)

    if len(sent_news) > MAX_SENT_NEWS:
        sent_news = set(list(sent_news)[-100:])

    save_sent_news(sent_news)
    print("[DEBUG] Storico iniziale registrato (limitato)")

    while True:
        try:
            await send_news()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(300)  # ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()
    asyncio.run(scheduler())
