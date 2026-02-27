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
    raise ValueError("RAPIDAPI_KEY, BOT_TOKEN o CHAT_ID non impostati correttamente")

bot = Bot(token=BOT_TOKEN)

# ==============================
# FLASK (Render richiede porta)
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# GLOBAL STATE (anti-duplicati)
# ==============================
sent_events = set()

# ==============================
# FETCH EVENTS DA ULTIMATE ECONOMIC CALENDAR
# ==============================
def fetch_events():
    url = "https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview"

    today = datetime.now(pytz.utc).date()
    to_date = today + timedelta(days=7)

    params = {
        "from": today.isoformat(),
        "to": to_date.isoformat(),
        "countries": "US,EUR"  # Puoi aggiungere altri se vuoi
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

    events = []
    for item in data:
        if not isinstance(item, dict):
            print("[SKIP] item non dict:", item)
            continue
        try:
            currency = item.get("currency")
            importance = item.get("importance", 0)
            date_str = item.get("date")
            name = item.get("title") or item.get("indicator") or "No Title"

            if not date_str:
                continue

            event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            # Optional: filtro solo USD/EUR e High importance
            if currency not in ["USD", "EUR"]:
                continue
            if importance <= 0:
                continue

            actual = item.get("actual")
            forecast = item.get("forecast")

            events.append({
                "id": f"{name}_{date_str}",
                "name": name,
                "currency": currency,
                "actual": actual,
                "forecast": forecast,
                "time": event_time.strftime("%Y-%m-%d %H:%M UTC")
            })

        except Exception as e:
            print("[PARSE ERROR]", e, "item:", item)
            continue

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = fetch_events()

    if not events:
        print("[INFO] Nessuna news trovata")
        return

    print(f"[INFO] Eventi trovati: {len(events)}")

    for event in events:
        if event["id"] in sent_events:
            continue
        try:
            label, score = evaluate_impact(event["name"], event["actual"], event["forecast"])
            message = (
                f"📊 {event['currency']} HIGH IMPACT\n"
                f"{event['name']}\n"
                f"🕒 {event['time']}\n"
                f"Actual: {event['actual']}\n"
                f"Forecast: {event['forecast']}\n"
                f"Impact Score: {score} ({label})"
            )
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_events.add(event["id"])
            print(f"[SENT] {event['name']}")
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    # Messaggio di startup
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

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

    # Avvia scheduler async nel main thread (Python 3.14 safe)
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
