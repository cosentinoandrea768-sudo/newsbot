import asyncio
import os
from datetime import datetime
import pytz
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
from impact_logic import evaluate_impact

# ==============================
# CONFIG (usa variabili Render!)
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
# ECONOMY NEWS
# ==============================
async def send_economy_news():
    feed = feedparser.parse(RSS_ECONOMY)
    print("News trovate:", len(feed.entries))

    for item in feed.entries[:3]:  # solo 3 per test
        title = safe_translate(item.title)
        date = parse_date(item).strftime("%Y-%m-%d %H:%M UTC")

        msg = (
            f"📰 {title}\n"
            f"🕒 {date}\n"
            f"🔗 {item.link}"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            await asyncio.sleep(1.5)
        except Exception as e:
            print("Errore news:", e)

# ==============================
# ECONOMIC INDICATORS
# ==============================
async def send_indicators():
    feed = feedparser.parse(RSS_INDICATORS)
    print("Indicatori trovati:", len(feed.entries))

    for item in feed.entries:
        title = item.title

        # filtro High Impact + USD/EUR
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

# ==============================
# BACKGROUND LOOP
# ==============================
async def background_loop():
    await asyncio.sleep(5)  # aspetta che Flask sia pronto

    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
    except Exception as e:
        print("Errore startup:", e)

    while True:
        print("Controllo RSS...")
        await send_economy_news()
        await send_indicators()
        await asyncio.sleep(600)  # ogni 10 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(background_loop())
    app.run(host="0.0.0.0", port=PORT)
