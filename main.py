import os
import json
import asyncio
import requests
from datetime import datetime
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
# FETCH EVENTS - DEBUG VERSIONE SENZA FILTRI
# ==============================
def fetch_events():
    url = "https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview"
    today = datetime.utcnow().date()
    to_date = (datetime.utcnow() + timedelta(days=7)).date()

    params = {
        "from": today.isoformat(),
        "to": to_date.isoformat(),
        # "countries": "US,IT"  # opzionale, per ora tutto
    }

    headers = {
        "x-rapidapi-host": "ultimate-economic-calendar.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("[API ERROR]", e)
        return []

    print(f"[DEBUG] Totale eventi RAW ricevuti: {len(data)}")
    for e in data[:10]:  # stampo solo i primi 10 per debug
        print(e)

    events = []
    for item in data:
        # ID univoco basato su titolo + data
        event_id = f"{item.get('title')}_{item.get('date')}"
        events.append({
            "id": event_id,
            "name": item.get("title"),
            "currency": item.get("currency"),
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "time": item.get("date")
        })

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = fetch_events()
    if not events:
        print("[INFO] Nessun evento ricevuto")
        return

    # Messaggio di debug startup
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato correttamente - invio eventi ricevuti")
    except Exception as e:
        print("[TELEGRAM ERROR STARTUP]", e)

    for event in events:
        if event["id"] in sent_events:
            continue

        label, score = evaluate_impact(event["name"], event["actual"], event["forecast"])

        message = (
            f"📊 {event['currency'] or 'N/A'} - Event Debug\n"
            f"{event['name']}\n"
            f"🕒 {event['time']}\n"
            f"Actual: {event['actual']}\n"
            f"Forecast: {event['forecast']}\n"
            f"Impact Score: {score} ({label})"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_events.add(event["id"])
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    while True:
        try:
            await send_events()
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(300)  # ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread
    from datetime import timedelta

    # Avvia Flask in background
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
