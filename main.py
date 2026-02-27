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
# FETCH EVENTS
# ==============================
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/get_list"
    headers = {
        "x-rapidapi-host": "forexfactory1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json={}, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print("[API ERROR]", e)
        return []

    description = data.get("description", [])
    graph = data.get("graph", [])
    graph_map = {g.get("dateline"): g for g in graph if isinstance(g, dict)}

    events = []
    today = datetime.now(pytz.utc).date()
    week_later = today + timedelta(days=7)

    for item in description:
        if not isinstance(item, dict):
            continue

        currency = item.get("currency")
        impact = item.get("impact")
        dateline = item.get("next_dateline")
        if currency not in ["USD", "EUR"] or impact != "High" or not dateline:
            continue

        try:
            event_time = datetime.fromisoformat(dateline.replace("Z", "+00:00"))
        except Exception:
            continue

        # Prende tutti gli eventi della settimana
        if not (today <= event_time.date() <= week_later):
            continue

        graph_data = graph_map.get(dateline, {})
        actual = graph_data.get("actual_formatted") or graph_data.get("actual")
        forecast = graph_data.get("forecast_formatted") or graph_data.get("forecast")

        events.append({
            "id": f"{item.get('name')}_{dateline}",
            "name": item.get("name"),
            "currency": currency,
            "actual": actual,
            "forecast": forecast,
            "time": event_time.strftime("%Y-%m-%d %H:%M UTC")
        })

    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = fetch_events()
    if not events:
        print("[INFO] Nessuna news per la settimana prossima")
        return

    print(f"[DEBUG] Eventi totali trovati: {len(events)}")
    for e in events:
        print(e)

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
# SCHEDULER
# ==============================
async def scheduler():
    # Messaggio di test all’avvio
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente e pronto a inviare news!")
    except Exception as e:
        print("[TELEGRAM ERROR INIT]", e)

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

    # Avvia Flask in un thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler async nel main thread
    asyncio.run(scheduler())
