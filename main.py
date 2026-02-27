import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from flask import Flask
from telegram.ext import ApplicationBuilder
import json

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI ForexFactory

TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# -----------------------------
# Bot Telegram asincrono
# -----------------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -----------------------------
# Flask keep-alive
# -----------------------------
app = Flask("bot")

@app.route("/")
def home():
    return "🤖 Bot economico attivo!"

import threading
threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
    daemon=True
).start()

# -----------------------------
# Keywords per filtraggio eventi
# -----------------------------
HIGH_IMPACT_KEYWORDS = ["ppi", "core ppi"]

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
    payload = {}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        data = response.json()
        # DEBUG primi 5 eventi
        print("DEBUG API RESPONSE:", json.dumps(data[:5], indent=2))
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    ts_now = int(datetime.now(TIMEZONE).timestamp())
    for item in data:
        currency = item.get("currency")
        headline = item.get("name")
        impact_value = str(item.get("impact", "")).lower()

        # Filtra solo USD/EUR e High Impact o parole chiave PPI/Core PPI
        if currency not in ["USD", "EUR"]:
            continue
        if impact_value != "high" and not any(k in headline.lower() for k in HIGH_IMPACT_KEYWORDS):
            continue

        events.append({
            "id": item.get("id", f"{headline}_{ts_now}"),
            "currency": currency,
            "headline": headline,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "impact": impact_value,
            "datetime": ts_now
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
            text="📅 Oggi non ci sono news High Impact USD/EUR."
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
# Notifica release con impatto
# -----------------------------
async def check_releases():
    events = fetch_events()
    for e in events:
        news_id = e["id"]
        if news_id in notified_events:
            continue

        actual = e.get("actual")
        forecast = e.get("forecast")

        # Notifica solo se actual disponibile
        if actual is None:
            continue

        msg = (
            f"📊 *{e['headline']}* ({e['currency']})\n\n"
            f"Actual: {actual}\n"
            f"Forecast: {forecast or 'N/D'}\n"
            f"Previous: {e.get('previous') or 'N/D'}\n"
            f"Impact: {e['impact'].capitalize()}"
        )

        await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        notified_events.add(news_id)

# -----------------------------
# Scheduler asincrono
# -----------------------------
async def scheduler_loop():
    print("🚀 Bot avviato correttamente")
    await application.bot.send_message(chat_id=CHAT_ID, text="✅ Bot avviato correttamente")
    await send_daily()
    await check_releases()

    schedule.every().day.at("06:00").do(lambda: asyncio.create_task(send_daily()))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_releases()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
