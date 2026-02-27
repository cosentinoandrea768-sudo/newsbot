import os
import json
import asyncio
import requests
import pytz
from datetime import datetime
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
print("[DEBUG] Startup Telegram OK")

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
# FETCH EVENTS DA RAPIDAPI (USD/EUR & High Impact)
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
    except requests.RequestException as e:
        print("[API ERROR]", e)
        return []

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[JSON ERROR] Risposta non valida")
        print(response.text)
        return []

    description = data.get("description", [])
    graph = data.get("graph", [])
    graph_map = {g.get("dateline"): g for g in graph if isinstance(g, dict)}

    events = []

    for item in description:
        if not isinstance(item, dict):
            continue

        currency = item.get("currency")
        impact = item.get("impact")
        dateline = item.get("next_dateline")
        name = item.get("name")

        # LOG DEBUG
        print(f"[DEBUG] News raw: {name} | {currency} | {impact} | {dateline}")

        # Filtro: solo USD/EUR e High impact
        if currency not in ["USD", "EUR"]:
            continue
        if impact != "High":
            continue
        if not dateline:
            continue

        try:
            event_time = datetime.fromisoformat(dateline.replace("Z", "+00:00"))
        except Exception:
            continue

        today = datetime.now(pytz.utc).date()
        if event_time.date() != today:
            continue

        graph_data = graph_map.get(dateline, {})
        actual = graph_data.get("actual_formatted") or graph_data.get("actual")
        forecast = graph_data.get("forecast_formatted") or graph_data.get("forecast")

        event = {
            "id": f"{name}_{dateline}",
            "name": name,
            "currency": currency,
            "actual": actual,
            "forecast": forecast,
            "time": event_time.strftime("%H:%M UTC")
        }

        events.append(event)

    print(f"[DEBUG] Eventi filtrati: {len(events)}")
    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = fetch_events()

    if not events:
        print("[INFO] Nessuna news oggi")
        return

    print(f"[INFO] Eventi trovati: {len(events)}")

    for event in events:
        if event["id"] in sent_events:
            continue

        label, score = evaluate_impact(
            event["name"],
            event["actual"],
            event["forecast"]
        )

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
# SCHEDULER ROBUSTO
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

    # Flask in thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Scheduler async nel main thread
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
