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
# FETCH EVENTS DA Ultimate Economic Calendar
# ==============================
def fetch_events(days_ahead=0):
    """
    Ritorna eventi da oggi fino a days_ahead (0 = oggi, 7 = settimana prossima)
    """
    today_utc = datetime.now(pytz.utc).date()
    to_date = today_utc + timedelta(days=days_ahead)

    url = "https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview"
    params = {
        "from": today_utc.isoformat(),
        "to": to_date.isoformat(),
        "countries": "US,EU"  # filtra solo USD / EUR
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
        # filtro currency
        if item.get("currency") not in ["USD", "EUR"]:
            continue
        # filtro importanza (High Impact)
        if item.get("importance", 0) < 1:
            continue

        try:
            event_time = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
        except Exception:
            continue

        event = {
            "id": item.get("id"),
            "name": item.get("indicator") or item.get("title"),
            "currency": item.get("currency"),
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "time": event_time.strftime("%H:%M UTC")
        }

        events.append(event)

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events(events):
    if not events:
        print("[INFO] Nessuna news da inviare")
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
# MESSAGGIO DI TEST
# ==============================
async def send_startup_message():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente!")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    # invia messaggio di startup
    await send_startup_message()
    # invia tutte le news della settimana prossima (7 giorni)
    events = fetch_events(days_ahead=7)
    await send_events(events)

    # loop continuo ogni 5 minuti
    while True:
        try:
            events = fetch_events(days_ahead=0)
            await send_events(events)
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(300)

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Flask in un thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Scheduler async nel main thread
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
