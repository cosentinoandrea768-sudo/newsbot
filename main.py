import os
import asyncio
from threading import Thread
from datetime import datetime
import pytz
import feedparser
from telegram import Bot
from flask import Flask
from impact_logic import evaluate_impact

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
    return "Bot attivo ✅"

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

# ==============================
# GLOBAL STATE
# ==============================
sent_events = {}

# ==============================
# FETCH RSS ECONOMIC INDICATORS
# ==============================
RSS_ECONOMIC_INDICATORS = "https://www.investing.com/economic-calendar/Service/Rss.ashx?timeZone=11"

def fetch_economic_indicators():
    feed = feedparser.parse(RSS_ECONOMIC_INDICATORS)
    events = []
    for entry in feed.entries:
        # Solo High Impact USD/EUR
        impact = getattr(entry, "impact", "").lower()
        currency = getattr(entry, "currency", "")
        if impact != "high" or currency not in ["USD", "EUR"]:
            continue

        previous = getattr(entry, "previous", "-")
        forecast = getattr(entry, "forecast", "-")
        actual = getattr(entry, "actual", "-")
        event_time = getattr(entry, "time", "??:??")

        events.append({
            "id": entry.id,
            "name": entry.title,
            "currency": currency,
            "time": event_time,
            "previous": previous,
            "forecast": forecast,
            "actual": actual
        })
    return events

# ==============================
# SEND TELEGRAM
# ==============================
async def send_message_test(text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
        print("[SENT] ", text)
    except Exception as e:
        print("[TELEGRAM ERROR]", e)

async def send_economic_indicators():
    events = fetch_economic_indicators()
    if not events:
        await send_message_test("⚪ Nessun high impact USD/EUR trovato nel feed")
        return

    for event in events:
        event_id = event["id"]
        prev_state = sent_events.get(event_id, {})

        if not prev_state or prev_state.get("actual") != event["actual"]:
            actual = event["actual"] if event["actual"] else "-"
            forecast = event["forecast"] if event["forecast"] else "-"
            previous = event["previous"] if event["previous"] else "-"

            if actual != "-" and forecast != "-":
                label, score = evaluate_impact(event["name"], actual, forecast)
            else:
                label, score = "⚪ Neutro", 0

            message = (
                f"📊 {event['name']} ({event['currency']})\n"
                f"🕒 {event['time']} UTC\n"
                f"Previous: {previous}\n"
                f"Forecast: {forecast}\n"
                f"Actual: {actual}\n"
                f"Impatto: {label}"
            )

            await send_message_test(message)
            sent_events[event_id] = event

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    # Messaggio di startup
    await send_message_test("🚀 Bot avviato correttamente")

    while True:
        await send_economic_indicators()
        await asyncio.sleep(300)  # ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(scheduler())
