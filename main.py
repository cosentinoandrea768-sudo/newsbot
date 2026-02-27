import os
import json
import asyncio
import requests
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram import Bot
from impact_logic import evaluate_impact

# ==============================
# ENV VARS
# ==============================
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

if not RAPIDAPI_KEY or not BOT_TOKEN or not CHAT_ID:
    raise ValueError("RAPIDAPI_KEY, BOT_TOKEN e CHAT_ID devono essere impostati")

bot = Bot(token=BOT_TOKEN)

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
sent_events = set()

# ==============================
# FETCH EVENTS - Ultimate Economic Calendar
# ==============================
def fetch_events():
    url = "https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview"

    headers = {
        "x-rapidapi-host": "ultimate-economic-calendar.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    today = datetime.utcnow().date()
    params = {
        "from": today.strftime("%Y-%m-%d"),
        "to": (today + timedelta(days=7)).strftime("%Y-%m-%d"),
        "countries": "US,EU"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("[API ERROR]", e)
        return []

    events = []
    for item in data.get("events", []):
        # Filtro High Impact USD/EUR
        if item.get("impact") != "High":
            continue
        currency = item.get("currency")
        if currency not in ["USD", "EUR"]:
            continue

        date_utc = item.get("dateUtc")
        if not date_utc:
            continue

        try:
            event_time = datetime.fromisoformat(date_utc.replace("Z", "+00:00"))
        except Exception:
            continue

        events.append({
            "id": f"{item.get('name')}_{date_utc}",
            "name": item.get("name"),
            "currency": currency,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "time": event_time.strftime("%H:%M UTC")
        })

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = fetch_events()

    if not events:
        print("[INFO] Nessuna news High Impact USD/EUR trovata")
        return

    for event in events:
        if event["id"] in sent_events:
            continue

        label, score = evaluate_impact(event["name"], event["actual"], event["forecast"])
        message = (
            f"📊 {event['currency']} HIGH IMPACT\n"
            f"{event['name']}\n"
            f"🕒 {event['time']}\n"
            f"Actual: {event['actual']}\n"
            f"Forecast: {event['forecast']}\n"
            f"Impact Score: {score} ({label})"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_events.add(event["id"])
            print(f"[SENT] {event['name']}")
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# MESSAGGIO DI TEST ALL'AVVIO
# ==============================
async def startup_message():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente!")
    except Exception as e:
        print("[TELEGRAM STARTUP ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    await startup_message()
    while True:
        try:
            await send_events()
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(300)  # controlla ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Avvia Flask in un thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler async nel main thread
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
        
