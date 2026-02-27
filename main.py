import asyncio
from datetime import datetime
import pytz
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = "INSERISCI_IL_TUO_BOT_TOKEN"
CHAT_ID = "INSERISCI_IL_TUO_CHAT_ID"
PORT = 10000

bot = Bot(token=BOT_TOKEN)
translator = GoogleTranslator(source='en', target='it')

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
def parse_rss_date(datestr):
    try:
        return datetime(*datestr[:6], tzinfo=pytz.utc)
    except:
        return datetime.now(pytz.utc)

async def safe_translate(text):
    try:
        return translator.translate(text)
    except:
        return text

# ==============================
# FETCH NEWS
# ==============================
async def fetch_daily_news():
    feed = feedparser.parse(RSS_ECONOMY)
    print("[DEBUG] Numero news RSS Economy:", len(feed.entries))
    return feed.entries

async def fetch_indicators():
    feed = feedparser.parse(RSS_INDICATORS)
    print("[DEBUG] Numero news RSS Indicators:", len(feed.entries))
    return feed.entries

# ==============================
# INVIO MESSAGGI
# ==============================
async def send_test_messages():
    # Messaggi di prova
    for i in range(3):
        try:
            await bot.send_message(chat_id=CHAT_ID, text=f"🚀 Messaggio di test {i+1}")
            await asyncio.sleep(1.5)
        except Exception as e:
            print("[TEST ERROR]", e)

async def send_rss_preview():
    news = await fetch_daily_news()
    for item in news[:3]:  # solo prime 3 news per test
        title = await safe_translate(item.title)
        pub_date = parse_rss_date(item.published_parsed).strftime("%Y-%m-%d %H:%M UTC")
        msg = f"📰 {title}\n🕒 Pubblicato: {pub_date}\n🔗 {item.link}"
        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            await asyncio.sleep(1.5)
        except Exception as e:
            print("[TELEGRAM ERROR NEWS]", e)

    indicators = await fetch_indicators()
    for item in indicators[:3]:  # prime 3 indicatori
        title = await safe_translate(item.title)
        pub_date = parse_rss_date(item.published_parsed).strftime("%Y-%m-%d %H:%M UTC")
        msg = f"📊 {title}\n🕒 Orario uscita: {pub_date}"
        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            await asyncio.sleep(1.5)
        except Exception as e:
            print("[TELEGRAM ERROR INDICATORS]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente - test in corso")
    except Exception as e:
        print("[TELEGRAM ERROR STARTUP]", e)

    while True:
        await send_test_messages()
        await send_rss_preview()
        await asyncio.sleep(600)  # ogni 10 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Flask in background
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler
    asyncio.run(scheduler())
