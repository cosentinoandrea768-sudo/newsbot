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
# FETCH EVENTS DA RAPIDAPI
# ==============================

def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/get_list"

    headers = {
        "x-rapidapi-host": "forexfactory1.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json={}, timeout=20)
        print("[DEBUG] Status code:", response.status_code)
        print("[DEBUG] Raw response:", response.text[:500])
        response.raise_for_status()
    except requests.RequestException as e:
        print("[API ERROR]", e)
        return []

    try:
        data = response.json()
    except json.JSONDecodeError:
        print("[JSON ERROR] Risposta non valida")
        return []

    description = data.get("description", [])
    graph = data.get("graph", [])

    print(f"[DEBUG] Description count: {len(description)}")
    print(f"[DEBUG] Graph count: {len(graph)}")

    graph_map = {g.get("dateline"): g for g in graph if isinstance(g, dict)}

    events = []

    for item in description:
        if not isinstance(item, dict):
            continue

        currency = item.get("currency")
        impact = item.get("impact")
        dateline = item.get("next_dateline")

        print(f"[DEBUG] Checking: {item.get('name')} | {currency} | {impact}")

        # Solo USD / EUR
        if currency not in ["USD", "EUR"]:
            continue

        # Solo High Impact (robusto)
        if not impact or "High" not in str(impact):
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
            "id": f"{item.get('name')}_{dateline}",
            "name": item.get("name"),
            "currency": currency,
            "actual": actual,
            "forecast": forecast,
            "time": event_time.strftime("%H:%M UTC")
        }

        events.append(event)

    print(f"[DEBUG] Filtered events today: {len(events)}")
    return events

# ==============================
# INVIO TELEGRAM
# ==============================

async def send_events():
    events = fetch_events()

    if not events:
        print("[INFO] Nessuna news filtrata oggi")
        return

    for event in events:

        if event["id"] in sent_events:
            continue

        try:
            label, score = evaluate_impact(
                event["name"],
                event["actual"],
                event["forecast"]
            )
        except Exception as e:
            print("[IMPACT ERROR]", e)
            label, score = "N/A", 0

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
    while True:
        try:
            await send_events()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(300)  # 5 minuti

# ==============================
# MAIN (Render-safe)
# ==============================

if __name__ == "__main__":

    async def main():
        # Test Telegram
        try:
            await bot.send_message(chat_id=CHAT_ID, text="✅ Bot avviato correttamente su Render")
            print("[DEBUG] Startup Telegram OK")
        except Exception as e:
            print("[STARTUP TELEGRAM ERROR]", e)

        # Avvia scheduler
        asyncio.create_task(scheduler())

        # Avvia Flask in executor (non blocca asyncio)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: app.run(host="0.0.0.0", port=PORT)
        )

    asyncio.run(main())
