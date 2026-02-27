import os
import requests
import time
from datetime import datetime
from flask import Flask
from telegram import Bot
from threading import Thread

# ----------------------
# Config
# ----------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

# ----------------------
# Funzioni helper
# ----------------------
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/api?function=get_list"  # Endpoint reale RapidAPI
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "forexfactory1.p.rapidapi.com"  # <--- CORRETTO
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    return data.get("events", [])
    
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

def send_daily():
    events = fetch_events()
    if not events:
        bot.send_message(chat_id=CHAT_ID, text="⚠️ Nessuna news ad alto impatto disponibile oggi.")
        return

    for e in events:
        msg = format_event(e)
        bot.send_message(chat_id=CHAT_ID, text=msg)

def scheduler_loop():
    while True:
        try:
            send_daily()
        except Exception as ex:
            print("Errore scheduler:", ex)
        time.sleep(300)  # ogni 5 minuti

# ----------------------
# Flask route
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

    # Avvia scheduler in un thread separato
    Thread(target=scheduler_loop, daemon=True).start()

    # Avvia Flask
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
