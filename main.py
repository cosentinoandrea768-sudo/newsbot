import asyncio
from datetime import datetime
import pytz
from flask import Flask
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
from impact_logic import evaluate_impact

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
    today = datetime.now(pytz.utc).date()
    events = []

    for item in feed.entries:
        pub_date = parse_rss_date(item.published_parsed)
        if pub_date.date() != today:
            continue
        img_url = None
        if 'media_content' in item and len(item.media_content) > 0:
            img_url = item.media_content[0].get('url')
        events.append({
            "id": item.link,
            "title": item.title,
            "link": item.link,
            "summary": getattr(item, "summary", ""),
            "image": img_url,
            "pub_date": pub_date.strftime("%Y-%m-%d %H:%M UTC")
        })
    return events

async def fetch_indicators():
    feed = feedparser.parse(RSS_INDICATORS)
    events = []
    for item in feed.entries:
        title = item.title
        # --- FILTRO HIGH IMPACT e USD/EUR ---
        if "[USD]" not in title and "[EUR]" not in title:
            continue
        if "High Impact" not in title:
            continue
        pub_date = parse_rss_date(item.published_parsed)
        events.append({
            "id": item.link,
            "name": title,
            "pub_date": pub_date,
            "previous": getattr(item, "previous","-"),
            "forecast": getattr(item, "forecast","-"),
            "actual": getattr(item, "actual","-"),
        })
    return events

# ==============================
# INVIO MESSAGGI
# ==============================
async def send_daily_news():
    events = await fetch_daily_news()
    for e in events:
        titolo_it = await safe_translate(e["title"])
        summary_it = await safe_translate(e.get("summary",""))
        msg = (
            f"📰 {titolo_it}\n"
            f"🕒 Pubblicato: {e['pub_date']}\n"
            f"{summary_it}\n"
            f"🔗 {e['link']}"
        )
        try:
            if e.get("image"):
                await bot.send_photo(chat_id=CHAT_ID, photo=e["image"], caption=msg)
            else:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
            await asyncio.sleep(1.5)  # delay per evitare flood
        except Exception as ex:
            print("[TELEGRAM ERROR NEWS]", ex)

async def send_indicators():
    events = await fetch_indicators()
    for e in events:
        actual = e.get("actual","-")
        label, score = evaluate_impact(e["name"], actual, e.get("forecast","-"))
        nome_it = await safe_translate(e["name"])
        msg = (
            f"📊 {nome_it}\n"
            f"🕒 Orario uscita: {e['pub_date'].strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Previous: {e.get('previous','-')}\n"
            f"Forecast: {e.get('forecast','-')}\n"
            f"Actual: {actual}\n"
            f"Impact: {label}"
        )
        try:
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            await asyncio.sleep(1.5)  # delay per evitare flood
        except Exception as ex:
            print("[TELEGRAM ERROR INDICATORS]", ex)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
    except Exception as e:
        print("[TELEGRAM ERROR STARTUP]", e)

    while True:
        try:
            await send_daily_news()
            await send_indicators()
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(600)  # controllo ogni 10 minuti

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
