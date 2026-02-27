import os
import asyncio
import requests
from datetime import datetime
from flask import Flask
from telegram import Bot

# ----------------------
# Config
# ----------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

if not BOT_TOKEN or not CHAT_ID or not RAPIDAPI_KEY:
    raise ValueError("Variabili BOT_TOKEN, CHAT_ID e RAPIDAPI_KEY devono essere impostate!")

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# ----------------------
# Funzioni helper
# ----------------------
def fetch_events():
    url = "https://api.example.com/economic-events"  # Inserisci l'endpoint reale RapidAPI
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "api.example.com"
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    
    # Filtra solo news ad alto impatto USD/EUR
    events = []
    for item in data.get("events", []):
        currency = item.get("currency")
        impact = item.get("impact")
        if currency in ["USD", "EUR"] and impact == "high":
            events.append(item)
    return events

def format_event(event):
    dt = event.get("date") or ""
    title = event.get("title") or ""
    actual = event.get("actual") or "–"
    forecast = event.get("forecast") or "–"
    previous = event.get("previous") or "–"
    return f"📅 {dt}\n💹 {title}\nActual: {actual} | Forecast: {forecast} | Previous: {previous}"

async def send_daily():
    events = fetch_events()
    if not events:
        await send_message("⚠️ Nessuna news ad alto impatto disponibile oggi.")
        return

    for e in events:
        msg = format_event(e)
        await send_message(msg)

async def send_message(text):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, bot.send_message, CHAT_ID, text)

# ----------------------
# Scheduler loop
# ----------------------
async def scheduler_loop():
    while True:
        try:
            await send_daily()
        except Exception as ex:
            print("Errore scheduler:", ex)
        await asyncio.sleep(300)  # ogni 5 minuti

# ----------------------
# Flask routes (health check)
# ----------------------
@app.route("/")
def index():
    return "Bot attivo e in ascolto!"

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Bot avviato correttamente! In ascolto sulla porta {port}")

    async def main_loop():
        # Avvia scheduler in background
        asyncio.create_task(scheduler_loop())
        # Avvia Flask in thread separato
        from threading import Thread
        Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)).start()
        # Mantieni vivo il loop
        while True:
            await asyncio.sleep(3600)

    asyncio.run(main_loop())
