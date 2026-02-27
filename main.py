import asyncio
import os
from datetime import datetime
import pytz
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
from impact_logic import evaluate_impact
import threading
import time

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
# FLASK
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
# ASYNC LOOP
# ==============================
async def bot_loop():
    await asyncio.sleep(5)

    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
    except Exception as e:
        print("Errore startup:", e)

    while True:
        print("Controllo RSS...")

        # ECONOMY NEWS
        feed = feedparser.parse(RSS_ECONOMY)
        print("News trovate:", len(feed.entries))

        for item in feed.entries[:3]:
            title = safe_translate(item.title)
            date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")
            msg = f"📰 {title}\n🕒 {date}\n🔗 {item.link}"

            try:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
                await asyncio.sleep(1.5)
            except Exception as e:
                print("Errore news:", e)

        # INDICATORS
        feed = feedparser.parse(RSS_INDICATORS)
        print("Indicatori trovati:", len(feed.entries))

        for item in feed.entries:
            title = item.title

            if "[USD]" not in title and "[EUR]" not in title:
                continue
            if "High Impact" not in title:
                continue

            title_it = safe_translate(title)
            date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")

            previous = getattr(item, "previous", "-")
            forecast = getattr(item, "forecast", "-")
            actual = getattr(item, "actual", "-")

            impact, _ = evaluate_impact(title, actual, forecast)

            msg = (
                f"📊 {title_it}\n"
                f"🕒 {date}\n"
                f"Previous: {previous}\n"
                f"Forecast: {forecast}\n"
                f"Actual: {actual}\n"
                f"Impact: {impact}"
            )

            try:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
                await asyncio.sleep(1.5)
            except Exception as e:
                print("Errore indicatori:", e)

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
