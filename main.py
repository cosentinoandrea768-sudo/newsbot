import os
import asyncio
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram import Bot
from impact_logic import evaluate_impact
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
translator = GoogleTranslator(source='en', target='it')

# ==============================
# FLASK
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# GLOBAL STATE
# ==============================
sent_daily = set()
sent_weekly = dict()

# ==============================
# RSS URL
# ==============================
RSS_ECONOMY = "https://www.investing.com/rss/news_14.rss"
RSS_INDICATORS = "https://www.investing.com/rss/news_95.rss"

# ==============================
# FETCH NEWS
# ==============================
def parse_rss_date(datestr):
    try:
        return datetime(*datestr[:6], tzinfo=pytz.utc)
    except:
        return datetime.now(pytz.utc)

async def fetch_daily_news():
    feed = feedparser.parse(RSS_ECONOMY)
    events = []

    for item in feed.entries:
        pub_date = parse_rss_date(item.published_parsed)
        img_url = None
        if 'media_content' in item and len(item.media_content) > 0:
            img_url = item.media_content[0].get('url')
        events.append({
            "id": item.link,
            "title": item.title,
            "link": item.link,
            "summary": getattr(item, "summary", ""),
            "image": img_url
        })
    return events

async def fetch_weekly_indicators():
    feed = feedparser.parse(RSS_INDICATORS)
    events = []

    for item in feed.entries:
        pub_date = parse_rss_date(item.published_parsed)
        img_url = None
        if 'media_content' in item and len(item.media_content) > 0:
            img_url = item.media_content[0].get('url')
        events.append({
            "id": item.link,
            "name": item.title,
            "link": item.link,
            "pub_date": pub_date,
            "previous": getattr(item, "previous", "-"),
            "forecast": getattr(item, "forecast", "-"),
            "actual": getattr(item, "actual", "-"),
            "image": img_url
        })
    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_daily_news():
    events = await fetch_daily_news()
    for e in events:
        if e["id"] in sent_daily:
            continue

        # Traduzione titolo e summary
        try:
            titolo_it = translator.translate(e["title"])
            summary_it = translator.translate(e.get("summary",""))
        except Exception as ex:
            print("[TRANSLATION ERROR]", ex)
            titolo_it = e["title"]
            summary_it = e.get("summary","")

        msg = f"📰 {titolo_it}\n{summary_it}\n🔗 {e['link']}"

        try:
            if e.get("image"):
                await bot.send_photo(chat_id=CHAT_ID, photo=e["image"], caption=msg)
            else:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
            sent_daily.add(e["id"])
        except Exception as ex:
            print("[TELEGRAM ERROR]", ex)

async def send_weekly_indicators():
    events = await fetch_weekly_indicators()
    for e in events:
        prev_data = sent_weekly.get(e["id"], {"actual":"-", "impact":"⚪ Neutro"})
        actual = e.get("actual", "-") or prev_data["actual"]
        label, score = evaluate_impact(e["name"], actual, e.get("forecast", "-"))

        # Traduzione nome indicatore
        try:
            nome_it = translator.translate(e['name'])
        except Exception as ex:
            print("[TRANSLATION ERROR]", ex)
            nome_it = e['name']

        msg = (
            f"📊 {nome_it}\n"
            f"🕒 Orario uscita: {e['pub_date'].strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Previous: {e.get('previous','-')}\n"
            f"Forecast: {e.get('forecast','-')}\n"
            f"Actual: {actual}\n"
            f"Impact: {label}\n"
            f"🔗 {e['link']}"
        )

        try:
            if e.get("image"):
                await bot.send_photo(chat_id=CHAT_ID, photo=e["image"], caption=msg)
            else:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
            sent_weekly[e["id"]] = {"actual": actual, "impact": label}
        except Exception as ex:
            print("[TELEGRAM ERROR]", ex)

# ==============================
# SCHEDULER TEST
# ==============================
async def scheduler():
    # Messaggio di startup
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente (TEST RSS ITALIANO)")
    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

    # Invio immediato per test
    print("[DEBUG] Invio news giornaliere tradotte...")
    await send_daily_news()
    print("[DEBUG] Invio indicatori settimanali tradotti...")
    await send_weekly_indicators()

    # Loop opzionale
    while True:
        await asyncio.sleep(3600)

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()
    asyncio.run(scheduler())
