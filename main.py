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

# Per evitare duplicazioni
sent_event_ids = set()

# ----------------------
# Funzioni helper
# ----------------------
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/api?function=get_list"  # Endpoint corretto
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "forexfactory1.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    payload = {}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:
        # Filtra USD/EUR high impact
        if item.get("currency") not in ["USD", "EUR"]:
            continue
        if str(item.get("impact", "")).lower() != "high":
            continue

        event_id = item.get("id") or f"{item.get('name')}_{item.get('datetime', time.time())}"
        if event_id in sent_event_ids:
            continue  # evita duplicati
        sent_event_ids.add(event_id)

        events.append({
            "id": event_id,
            "currency": item.get("currency"),
            "headline": item.get("name"),
            "date": item.get("date") or "",
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous")
        })
    return events

def format_event(event):
    dt = event.get("date")
    try:
        dt_str = datetime.fromisoformat(dt).strftime("%H:%M") if dt else "–"
    except:
        dt_str = dt or "–"

    headline = event.get("headline") or "–"
    actual = event.get("actual") or "–"
    forecast = event.get("forecast") or "–"
    previous = event.get("previous") or "–"

    return (
        f"📅 {dt_str}\n"
        f"💹 {headline} ({event.get('currency')})\n"
        f"Actual: {actual} | Forecast: {forecast} | Previous: {previous}\n"
        f"------------------------------"
    )

def send_daily():
    events = fetch_events()
    if not events:
        bot.send_message(chat_id=CHAT_ID, text="⚠️ Nessuna news ad alto impatto disponibile oggi.")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        msg += format_event(e) + "\n"

    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

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
