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
    return "Bot Economy News TEST attivo ✅"

# ==============================
# GLOBAL STATE
# ==============================
sent_news = set()

# ==============================
# TRANSLATOR (istanza unica)
# ==============================
translator = GoogleTranslator(source='auto', target='it')

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
# FUNZIONE TRADUZIONE SICURA
# ==============================
def translate_text(text):
    try:
        return translator.translate(text)
    except:
        return text

# ==============================
# STARTUP TEST FEEDS
# ==============================
async def test_all_feeds():
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            if not feed.entries:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"⚠️ Nessuna news trovata:\n{feed_url}"
                )
                continue

            entry = feed.entries[0]

            title_it = translate_text(entry.title)

            summary_raw = getattr(entry, "summary", "")
            summary_text = (
                unescape(summary_raw)
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )
            summary_it = translate_text(summary_text) if summary_text else ""

            message = (
                f"🧪 TEST RSS\n"
                f"{feed_url}\n\n"
                f"{title_it}\n"
                f"{summary_it}\n"
                f"🕒 {getattr(entry, 'published', 'N/A')}\n"
                f"🔗 {entry.link}"
            )

            await bot.send_message(chat_id=CHAT_ID, text=message)

        except Exception as e:
            await bot.send_message(
                chat_id=CHAT_ID,
                text=f"❌ ERRORE feed:\n{feed_url}\n{e}"
            )

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

            title_it = translate_text(entry.title)

            summary_raw = getattr(entry, "summary", "")
            summary_text = (
                unescape(summary_raw)
                .replace("<p>", "")
                .replace("</p>", "")
                .strip()
            )
            summary_it = translate_text(summary_text) if summary_text else ""

            news_items.append({
                "id": news_id,
                "title": title_it,
                "summary": summary_it,
                "published": getattr(entry, "published", "N/A"),
                "link": entry.link
            })

    return news_items

# ==============================
# SEND NEWS
# ==============================
async def send_news():
    news_items = fetch_news()

    if not news_items:
        print("[DEBUG] Nessuna nuova news")
        return

    for item in news_items:
        message = (
            f"📰 BitPath News TEST\n"
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

    # Startup
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text="🚀 Bot Economy News TEST avviato"
        )

        # 🔥 Test immediato di tutti i feed
        await test_all_feeds()

        print("[DEBUG] Test feed completato")

    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

    # ⚠️ MODALITÀ TEST:
    # NON registriamo subito le news per vedere se funzionano

    while True:
        try:
            await send_news()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(120)  # 2 minuti per test rapido

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()
    asyncio.run(scheduler())
