import os
import json
import datetime
import pytz
import http.client
from flask import Flask
from impact_logic import evaluate_impact, calculate_surprise
from telegram.ext import ApplicationBuilder

# -----------------------------
# Config environment variables
# -----------------------------
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not RAPIDAPI_KEY:
    raise ValueError("⚠️ La variabile RAPIDAPI_KEY non è stata impostata!")
if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("⚠️ Le variabili BOT_TOKEN e CHAT_ID devono essere impostate!")

# -----------------------------
# Telegram bot setup
# -----------------------------
app_bot = ApplicationBuilder().token(BOT_TOKEN).build()

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)

# -----------------------------
# API helper functions
# -----------------------------
API_HOST = "forexfactory1.p.rapidapi.com"
API_ENDPOINT = "/api?function=get_list"

def fetch_events():
    """
    Fetch all news events from ForexFactory API using POST.
    Returns list of dictionaries with 'name', 'currency', 'actual', 'forecast', 'next_dateline'.
    """
    conn = http.client.HTTPSConnection(API_HOST)
    payload = "{}"
    headers = {
        "x-rapidapi-host": API_HOST,
        "x-rapidapi-key": RAPIDAPI_KEY,
        "Content-Type": "application/json"
    }

    conn.request("POST", API_ENDPOINT, payload, headers)
    res = conn.getresponse()
    data = res.read()
    conn.close()

    try:
        events_raw = json.loads(data)
    except json.JSONDecodeError:
        print("Errore decodifica JSON API")
        return []

    # Assumendo la struttura {"description": [...], "graph": [...]}
    events = []
    description_list = events_raw.get("description", [])
    graph_list = events_raw.get("graph", [])

    # Mappare dateline e actual dal graph
    graph_dict = {item["dateline"]: item for item in graph_list if "dateline" in item}

    for item in description_list:
        if not isinstance(item, dict):
            continue
        event = {
            "name": item.get("name"),
            "currency": item.get("currency"),
            "forecast": item.get("forecast") if "forecast" in item else None,
            "actual": item.get("actual") if "actual" in item else None,
            "next_dateline": item.get("next_dateline")
        }

        # Aggiorna actual dal graph se disponibile
        if event["next_dateline"] in graph_dict:
            event_graph = graph_dict[event["next_dateline"]]
            event["actual"] = event_graph.get("actual_formatted") or event_graph.get("actual")
            event["forecast"] = event_graph.get("forecast_formatted") or event_graph.get("forecast")

        events.append(event)

    return events

# -----------------------------
# Helper per filtrare news di oggi
# -----------------------------
def filter_today_events(events):
    """
    Filtra solo gli eventi della giornata corrente in UTC.
    """
    today = datetime.datetime.now(pytz.utc).date()
    today_events = []

    for event in events:
        dt_str = event.get("next_dateline")
        if not dt_str:
            continue
        try:
            dt_obj = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt_obj.date() == today:
            today_events.append(event)
    return today_events

# -----------------------------
# Funzione principale invio news
# -----------------------------
async def send_daily():
    events = fetch_events()
    if not events:
        print("⚪ Nessuna news trovata")
        return

    today_events = filter_today_events(events)
    if not today_events:
        print("⚪ Nessuna news prevista oggi")
        return

    for event in today_events:
        label, score = evaluate_impact(event["name"], event.get("actual"), event.get("forecast"))
        msg = f"{event['next_dateline']} | {event['currency']} | {event['name']}\n" \
              f"Forecast: {event.get('forecast')} | Actual: {event.get('actual')}\n" \
              f"Impact: {label}"
        await app_bot.bot.send_message(chat_id=CHAT_ID, text=msg)

# -----------------------------
# Scheduler loop
# -----------------------------
import asyncio

async def scheduler_loop():
    while True:
        await send_daily()
        # Controlla ogni 15 minuti
        await asyncio.sleep(900)

# -----------------------------
# Flask route semplice
# -----------------------------
@app.route("/")
def home():
    return "Bot attivo ✅"

# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        print("⚠️ Bot interrotto manualmente")
