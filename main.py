import os
import json
import asyncio
import datetime
import pytz
from flask import Flask
from impact_logic import evaluate_impact, calculate_surprise
from telegram.ext import ApplicationBuilder
import http.client

app = Flask(__name__)

# Legge la porta da Render (variabile d'ambiente PORT)
PORT = int(os.getenv("PORT", 10000))  # fallback a 10000 se non esiste

# Telegram Bot setup
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
rapidapi_key = os.getenv("RAPIDAPI_KEY")

# Esempio: funzione per fetch eventi dall'API ForexFactory
def fetch_events():
    conn = http.client.HTTPSConnection("forexfactory1.p.rapidapi.com")
    payload = "{}"
    headers = {
        'x-rapidapi-key': rapidapi_key,
        'x-rapidapi-host': "forexfactory1.p.rapidapi.com",
        'Content-Type': "application/json"
    }
    conn.request("POST", "/api?function=get_list", payload, headers)
    res = conn.getresponse()
    data = res.read()
    items = json.loads(data)
    return items

# Scheduler loop esempio
async def scheduler_loop():
    while True:
        await send_daily()
        await asyncio.sleep(60*60)  # ogni ora (esempio)

async def send_daily():
    events = fetch_events()
    # qui va la logica per filtrare eventi odierni, calcolare impact, inviare Telegram, ecc.
    print(f"Fetched {len(events)} events")

# Flask route base
@app.route("/")
def index():
    return "Bot running", 200

if __name__ == "__main__":
    from threading import Thread

    # Avvia Flask in un thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Avvia lo scheduler nel main thread
    try:
        asyncio.run(scheduler_loop())
    except KeyboardInterrupt:
        print("⚠️ Bot interrotto manualmente")
