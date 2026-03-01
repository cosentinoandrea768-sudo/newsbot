import os
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
    return "Bot Economy News attivo ✅"

# ==============================
# GLOBAL STATE
# ==============================
sent_news = set()

# ==============================
# FEED RSS MULTIPLI
# ==============================
RSS_FEEDS = [
    "https://www.investing.com/rss/news_14.rss",   # Economy
    "https://www.investing.com/rss/news_301.rss",
    "https://www.investing.com/rss/news_355.rss",
    "https://www.investing.com/rss/news_357.rss",
    "https://www.investing.com/rss/news_11.rss"
]

# ==============================
# FETCH NEWS
# ==============================
def fetch_news():
    news_items = []

    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)

        for entry in feed.entries:
            news_id = getattr(entry, "id", entry.link)

            if news_id in sent_news:
                continue

            # Traduzione titolo
            try:
                title_it = GoogleTranslator(source='auto', target='it').translate(entry.title)
            except:
                title_it = entry.title

            # Riassunto breve
            summary_raw = getattr(entry, "summary", "")
            summary_text = (
                unescape(summary_raw)
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )

            try:
                summary_it = (
                    GoogleTranslator(source='auto', target='it').translate(summary_text)
                    if summary_text else ""
                )
            except:
                summary_it = summary_text

            published = getattr(entry, "published", "N/A")
            link = entry.link

            news_items.append({
                "id": news_id,
                "title": title_it,
                "summary": summary_it,
                "published": published,
                "link": link
            })

    return news_items

# ==============================
# SEND TELEGRAM
# ==============================
async def send_news():
    news_items = fetch_news()
    if not news_items:
        return

    for item in news_items:
        message = (
            f"📰 BitPath News by Investing.com\n"
            f"{item['title']}\n"
            f"{item['summary']}\n"
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
    # Messaggio di avvio
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🚀 Bot Economy News avviato correttamente"
        )
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

    # Registriamo le news già presenti in TUTTI i feed
    for feed_url in RSS_FEEDS:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries:
            news_id = getattr(entry, "id", entry.link)
            sent_news.add(news_id)

    # Loop continuo
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
