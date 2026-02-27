import os
import requests
import time
import json
from datetime import datetime
from flask import Flask
from telegram import Bot
from threading import Thread

# ----------------------
# Config
# ----------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
API_KEY = os.environ.get("RAPIDAPI_KEY")  # RapidAPI ForexFactory

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

sent_event_ids = set()  # per evitare duplicati

# ----------------------
# Funzioni helper
# ----------------------
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/api?function=get_list"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "forexfactory1.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json={}, timeout=10)
        data = response.json()
        # DEBUG: mostra i primi 5 eventi
        print("DEBUG API RESPONSE:", json.dumps(data[:5], indent=2))
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:  # prende direttamente data come lista
        currency = item.get("currency")
        impact_value = str(item.get("impact", "")).lower()
        headline = item.get("name", "")

        if currency not in ["USD", "EUR"]:
            continue
        if impact_value != "high":
            continue

        # Genera ID univoco per evitare duplicati
        event_id = item.get("id") or f"{headline}_{item.get('date', '')}"
        if event_id in sent_event_ids:
            continue
        sent_event_ids.add(event_id)

        events.append({
            "id": event_id,
            "currency": currency,
            "headline": headline,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "datetime": item.get("date")
        })

    return events

def format_event(event):
    dt = event.get("datetime") or ""
    title = event.get("headline") or ""
    actual = event.get("actual") or "N/D"
    forecast = event.get("forecast") or "N/D"
    previous = event.get("previous") or "N/D"
    return f"📅 {dt}\n💹 {title} ({event['currency']})\nActual: {actual} | Forecast: {forecast} | Previous: {previous}"

def send_daily():
    events = fetch_events()
    if not events:
        bot.send_message(chat_id=CHAT_ID, text="📅 Oggi non ci sono news High Impact USD/EUR.")
        return

    msg = "📅 High Impact USD & EUR - Oggi\n\n"
    for e in events:
        msg += format_event(e) + "\n\n"

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
    return "🤖 Bot attivo e in ascolto!"

# ----------------------
# Main
# ----------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Bot avviato correttamente! In ascolto sulla porta {port}")
    bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente e in ascolto!")

    # Avvia scheduler in un thread separato
    Thread(target=scheduler_loop, daemon=True).start()

    # Avvia Flask
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
