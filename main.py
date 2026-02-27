import os
import json
import asyncio
import requests
from datetime import datetime, timedelta, timezone
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
    raise ValueError("RAPIDAPI_KEY, BOT_TOKEN o CHAT_ID non impostati")

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
# FETCH NEWS
# ==============================
def fetch_events(from_date=None, to_date=None):
    """
    Recupera le news dall'Ultimate Economic Calendar API
    """
    if from_date is None:
        from_date = datetime.now(timezone.utc).date()
    if to_date is None:
        to_date = from_date

    url = f"https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview?from={from_date}&to={to_date}&countries=US,EU"

    headers = {
        "x-rapidapi-host": "ultimate-economic-calendar.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("[API ERROR]", e)
        return []

    events = []
    today = datetime.now(timezone.utc).date()

    for item in data.get("events", []):
        # Filtra solo USD/EUR e High Impact
        if item.get("currency") not in ["USD", "EUR"]:
            continue
        if item.get("impact") != "High":
            continue

        # Data evento
        try:
            event_time = datetime.fromisoformat(item.get("date")[:-1] + "+00:00")
        except Exception:
            continue

        # Filtro solo eventi da today in poi
        if event_time.date() < today:
            continue

        actual = item.get("actual")
        forecast = item.get("forecast")

        events.append({
            "id": f"{item.get('title')}_{item.get('date')}",
            "name": item.get("title"),
            "currency": item.get("currency"),
            "actual": actual,
            "forecast": forecast,
            "time": event_time.strftime("%Y-%m-%d %H:%M UTC")
        })

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events(events):
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
# STARTUP MESSAGE + NEWS SETTIMANA
# ==============================
async def startup_send():
    # Messaggio di avvio
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato correttamente!")
    except Exception as e:
        print("[TELEGRAM ERROR STARTUP]", e)

    # Prende tutte le news della settimana
    from_date = datetime.now(timezone.utc).date()
    to_date = from_date + timedelta(days=7)
    events = fetch_events(from_date, to_date)
    if events:
        print(f"[INFO] Inviando {len(events)} news della settimana")
        await send_events(events)
    else:
        print("[INFO] Nessuna news della settimana da inviare")

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    while True:
        try:
            # Controlla solo eventi di oggi
            events = fetch_events()
            if events:
                await send_events(events)
            else:
                print("[INFO] Nessuna news oggi")
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(300)  # ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Flask in thread separato
    Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()

    # Avvia startup + scheduler
    async def main():
        await startup_send()
        await scheduler()

    asyncio.run(main())
