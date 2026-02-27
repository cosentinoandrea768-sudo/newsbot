import os
import asyncio
import requests
from datetime import datetime
import pytz
from flask import Flask
from telegram.ext import ApplicationBuilder
import json
import schedule
import threading

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI ForexFactory

TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# -----------------------------
# Bot Telegram
# -----------------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -----------------------------
# Flask keep-alive
# -----------------------------
app = Flask("bot")

@app.route("/")
def home():
    return "🤖 Bot economico attivo!"

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
    daemon=True
).start()

# -----------------------------
# Fetch eventi filtrati High Impact USD/EUR
# -----------------------------
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/api?function=get_list"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "forexfactory1.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    payload = "{}"

    try:
        response = requests.post(url, headers=headers, data=payload, timeout=10)
        data = response.json()
        # DEBUG primi eventi
        print("DEBUG API RESPONSE:", json.dumps(data[:5], indent=2))
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:
        currency = item.get("currency")
        impact_value = str(item.get("impact", "")).lower()
        if currency not in ["USD", "EUR"]:
            continue
        if impact_value != "high":
            continue

        ts = int(datetime.now(TIMEZONE).timestamp())
        events.append({
            "id": item.get("id", f"{item.get('name', '')}_{ts}"),
            "currency": currency,
            "headline": item.get("name"),
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "impact": impact_value,
            "datetime": ts
        })

    return events

# -----------------------------
# Messaggio giornaliero leggibile
# -----------------------------
async def send_daily():
    events = fetch_events()
    if not events:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="📅 Nessuna news High Impact USD/EUR disponibile oggi."
        )
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"], TIMEZONE).strftime("%H:%M")
        actual = e["actual"] or "N/D"
        forecast = e["forecast"] or "N/D"
        previous = e["previous"] or "N/D"

        msg += f"*{e['headline']}* ({e['currency']})\n"
        msg += f"🕒 {date_str} | Forecast: {forecast} | Previous: {previous} | Actual: {actual}\n\n"

    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# -----------------------------
# Scheduler loop
# -----------------------------
async def scheduler_loop():
    print("🚀 Bot avviato correttamente")
    await application.bot.send_message(chat_id=CHAT_ID, text="✅ Bot avviato correttamente")
    await send_daily()

    schedule.every(5).minutes.do(lambda: asyncio.create_task(send_daily()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
