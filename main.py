import os
import asyncio
from datetime import datetime
import pytz
from telegram import Bot
import feedparser
from deep_translator import GoogleTranslator
from impact_logic import evaluate_impact

# ==============================
# ENV VARS
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID non impostati")

bot = Bot(token=BOT_TOKEN)
translator = GoogleTranslator(source='en', target='it')

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
            "image": img_url
        })
    return events

async def fetch_indicators():
    feed = feedparser.parse(RSS_INDICATORS)
    events = []
    for item in feed.entries:
        pub_date = parse_rss_date(item.published_parsed)
        events.append({
            "id": item.link,
            "name": item.title,
            "pub_date": pub_date,
            "previous": getattr(item, "previous","-"),
            "forecast": getattr(item, "forecast","-"),
            "actual": getattr(item, "actual","-")
        })
    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_daily_news():
    events = await fetch_daily_news()
    for e in events:
        try:
            titolo_it = translator.translate(e["title"])
            summary_it = translator.translate(e.get("summary",""))
        except:
            titolo_it = e["title"]
            summary_it = e.get("summary","")
        msg = f"📰 {titolo_it}\n{summary_it}\n🔗 {e['link']}"
        try:
            if e.get("image"):
                await bot.send_photo(chat_id=CHAT_ID, photo=e["image"], caption=msg)
            else:
                await bot.send_message(chat_id=CHAT_ID, text=msg)
        except Exception as ex:
            print("[TELEGRAM ERROR]", ex)

async def send_indicators():
    events = await fetch_indicators()
    for e in events:
        actual = e.get("actual","-")
        label, score = evaluate_impact(e["name"], actual, e.get("forecast","-"))
        try:
            nome_it = translator.translate(e["name"])
        except:
            nome_it = e["name"]
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
        except Exception as ex:
            print("[TELEGRAM ERROR]", ex)

# ==============================
# TEST SCHEDULER
# ==============================
async def test():
    await send_daily_news()
    await send_indicators()

if __name__ == "__main__":
    asyncio.run(test())
