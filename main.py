import os
import json
import asyncio
import requests
from datetime import datetime, timezone
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

if not RAPIDAPI_KEY:
    raise ValueError("RAPIDAPI_KEY non impostata")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN non impostato")
if not CHAT_ID:
    raise ValueError("CHAT_ID non impostato")

bot = Bot(token=BOT_TOKEN)

# ==============================
# FLASK
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
    headers = {
        "x-rapidapi-host": "ultimate-economic-calendar.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    params = {
        "from": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "to": (datetime.now(timezone.utc) + pytz.timedelta(days=7)).strftime("%Y-%m-%d"),
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
    today = datetime.now(pytz.utc).date()

    for item in data:
        if not isinstance(item, dict):
            print("[DEBUG] Ignorato item non-dizionario:", item)
            continue

        currency = item.get("currency")
        importance = item.get("importance", 0)
        date_str = item.get("date")

        # Filtri base
        if currency not in ["USD", "EUR"]:
            continue
        if importance < 1:
            continue
        if not date_str:
            continue

        try:
            event_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            continue

        # Prendi solo eventi di oggi o futuri
        if event_time.date() < today:
            continue

        events.append({
            "id": f"{item.get('id')}_{date_str}",
            "name": item.get("title") or item.get("indicator") or item.get("id"),
            "currency": currency,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "time": event_time.strftime("%Y-%m-%d %H:%M UTC")
        })

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
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato correttamente!")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR]", e)

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
        await asyncio.sleep(300)  # 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
