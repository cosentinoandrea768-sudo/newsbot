import asyncio
import os
import threading
from datetime import datetime
import pytz
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
translator = GoogleTranslator(source="en", target="it")

RSS_ECONOMY = "https://www.investing.com/rss/news_14.rss"
RSS_INDICATORS = "https://www.investing.com/rss/news_95.rss"

# ==============================
# FLASK SERVER (Render)
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# HELPERS
# ==============================
def parse_date(entry):
    try:
        return datetime(*entry.published_parsed[:6], tzinfo=pytz.utc)
    except:
        return datetime.now(pytz.utc)

def safe_translate(text):
    try:
        return translator.translate(text)
    except:
        return text

# ==============================
# ASYNC BOT LOOP
# ==============================
async def bot_loop():
    await asyncio.sleep(5)

    # Messaggio avvio
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente (TEST MODE)")
    except Exception as e:
        print("Errore startup:", e)

    while True:
        print("===================================")
        print("Controllo RSS...")

        # =====================================
        # ECONOMY NEWS TEST
        # =====================================
        print("Controllo Economy News...")
        feed_news = feedparser.parse(RSS_ECONOMY)
        print("News trovate:", len(feed_news.entries))

        for item in feed_news.entries[:3]:
            title = safe_translate(item.title)
            date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")

            msg = (
                f"📰 *ECONOMY NEWS TEST*\n\n"
                f"{title}\n"
                f"🕒 {date}\n\n"
                f"🔗 {item.link}"
            )

            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1.5)
            except Exception as e:
                print("Errore news:", e)

        # =====================================
        # ECONOMIC INDICATORS TEST
        # =====================================
        print("Controllo Economic Indicators...")
        feed_ind = feedparser.parse(RSS_INDICATORS)
        print("Indicatori trovati:", len(feed_ind.entries))

        for item in feed_ind.entries[:3]:
            title = safe_translate(item.title)
            date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")

            msg = (
                f"📊 *INDICATOR NEWS TEST*\n\n"
                f"{title}\n"
                f"🕒 {date}\n\n"
                f"🔗 {item.link}"
            )

            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=msg,
                    parse_mode="Markdown"
                )
                await asyncio.sleep(1.5)
            except Exception as e:
                print("Errore indicatori:", e)

        print("Attendo 10 minuti...\n")
        await asyncio.sleep(600)

# ==============================
# THREAD RUNNER
# ==============================
def start_async_loop():
    asyncio.run(bot_loop())

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    threading.Thread(target=start_async_loop).start()
    app.run(host="0.0.0.0", port=PORT)
