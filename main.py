import os
import asyncio
from datetime import datetime
from threading import Thread

import pytz
import requests
from bs4 import BeautifulSoup
from telegram import Bot

from impact_logic import evaluate_impact

# ==============================
# ENV VARS
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID non impostati")

bot = Bot(token=BOT_TOKEN)

# ==============================
# GLOBAL STATE
# ==============================
sent_events = {}

# ==============================
# FLASK
# ==============================
from flask import Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# SCRAPING INVESTING
# ==============================
INVESTING_CALENDAR_URL = "https://www.investing.com/economic-calendar/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def fetch_investing_indicators():
    """
    Ritorna una lista di eventi high impact USD/EUR
    con struttura:
    {
        "id": event_id,
        "name": name,
        "currency": currency,
        "time": time,
        "previous": previous,
        "forecast": forecast,
        "actual": actual
    }
    """
    response = requests.get(INVESTING_CALENDAR_URL, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    events = []

    # Trova le righe del calendario (qui bisogna adattare il parser secondo il sito)
    rows = soup.select("tr.js-event-item")
    for row in rows:
        impact = row.get("data-impact")
        currency = row.get("data-currency")
        if impact != "3" or currency not in ["USD", "EUR"]:
            continue  # solo High Impact USD/EUR

        event_id = row.get("data-event-id")
        name = row.get("data-event")
        time = row.get("data-time")
        previous = row.get("data-previous", "-")
        forecast = row.get("data-forecast", "-")
        actual = row.get("data-actual", "-")

        events.append({
            "id": event_id,
            "name": name,
            "currency": currency,
            "time": time,
            "previous": previous,
            "forecast": forecast,
            "actual": actual
        })
    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_economic_indicators():
    events = fetch_investing_indicators()

    for event in events:
        event_id = event["id"]
        prev_state = sent_events.get(event_id, {})

        # Se non inviato prima o se i dati actual sono cambiati
        if not prev_state or prev_state.get("actual") != event["actual"]:
            actual = event["actual"] if event["actual"] else "-"
            forecast = event["forecast"] if event["forecast"] else "-"
            previous = event["previous"] if event["previous"] else "-"

            # Calcola impatto solo se actual disponibile
            if actual != "-" and forecast != "-":
                label, score = evaluate_impact(event["name"], actual, forecast)
            else:
                label, score = "⚪ Neutro", 0

            message = (
                f"📊 {event['name']} ({event['currency']})\n"
                f"🕒 {event['time']} UTC\n"
                f"Previous: {previous}\n"
                f"Forecast: {forecast}\n"
                f"Actual: {actual}\n"
                f"Impatto: {label}"
            )

            try:
                await bot.send_message(chat_id=CHAT_ID, text=message)
                sent_events[event_id] = event
                print(f"[SENT] {event['name']}")
            except Exception as e:
                print("[TELEGRAM ERROR]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    while True:
        try:
            await send_economic_indicators()
        except Exception as e:
            print("[LOOP ERROR]", e)

        await asyncio.sleep(300)  # controlla ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    # Avvia Flask in background
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler
    asyncio.run(scheduler())
