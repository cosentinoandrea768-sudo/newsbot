import http.client
import json
import datetime
import pytz
from flask import Flask
from impact_logic import evaluate_impact, calculate_surprise
from telegram.ext import ApplicationBuilder

# --- CONFIG BOT / TELEGRAM ---
TELEGRAM_TOKEN = "IL_TUO_TOKEN_TELEGRAM"
CHAT_ID = "IL_TUO_CHAT_ID"

# --- CONFIG API FOREXFACTORY ---
API_HOST = "forexfactory1.p.rapidapi.com"
API_KEY = "e2e8d057e2mshc4fed614afa27edp1826abjsne53cc7ed0c16"
API_ENDPOINT = "/api?function=get_list"

headers = {
    "x-rapidapi-host": API_HOST,
    "x-rapidapi-key": API_KEY,
    "Content-Type": "application/json"
}

# --- FLASK APP ---
app = Flask(__name__)

# --- FUNZIONI DI SUPPORTO ---
def fetch_events():
    """Chiama l'API e ritorna la lista di eventi del giorno"""
    conn = http.client.HTTPSConnection(API_HOST)
    payload = "{}"  # corpo vuoto
    try:
        conn.request("POST", API_ENDPOINT, payload, headers)
        res = conn.getresponse()
        data = res.read()
        events_raw = json.loads(data)
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    today = datetime.datetime.now(pytz.utc).date()

    for item in events_raw:
        # sicurezza se l'item non è dict
        if not isinstance(item, dict):
            continue

        name = item.get("name")
        currency = item.get("currency")
        next_dateline = item.get("next_dateline")

        # controllo data
        if next_dateline:
            try:
                event_date = datetime.datetime.fromisoformat(next_dateline).date()
            except ValueError:
                event_date = today  # se formato sconosciuto, consideralo oggi
        else:
            event_date = today

        if event_date == today:
            events.append({
                "name": name,
                "currency": currency,
                "actual": item.get("actual"),
                "forecast": item.get("forecast")
            })

    return events

async def send_daily():
    """Invia le news del giorno al canale Telegram"""
    events = fetch_events()
    if not events:
        print("⚪ Nessuna news oggi")
        return

    for e in events:
        label, score = evaluate_impact(e["name"], e.get("actual"), e.get("forecast"))
        message = f"{e['name']} ({e['currency']})\nImpact: {label}\nActual: {e.get('actual')} | Forecast: {e.get('forecast')}"
        print(message)
        # qui inserisci la logica per inviare Telegram usando ApplicationBuilder

# --- SCHEDULER LOOP ---
import asyncio
async def scheduler_loop():
    while True:
        await send_daily()
        await asyncio.sleep(60*60)  # ogni ora

# --- AVVIO BOT ---
if __name__ == "__main__":
    print("🚀 Bot avviato correttamente")
    asyncio.run(scheduler_loop())
