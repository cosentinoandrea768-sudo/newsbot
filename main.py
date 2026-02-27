import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from flask import Flask
from impact_logic import evaluate_impact, calculate_surprise
from telegram.ext import ApplicationBuilder
import json

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI key per ForexFactory

TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# -----------------------------
# Bot Telegram
# -----------------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -----------------------------
# Flask keep-alive (Render)
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
# Fetch eventi via API ForexFactory (/api?function=get_list)
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
        print("DEBUG API RESPONSE:", json.dumps(data, indent=2))  # debug della struttura
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    ALWAYS_NOTIFY = ["PPI", "Core PPI", "CPI", "Non-Farm Payrolls"]

    # Aggiorna qui il ciclo se l'API restituisce la lista direttamente o dentro un campo
    # Per esempio: data.get("events", []) o data.get("calendar", [])
    for item in data.get("events", []):  # controlla il campo corretto con DEBUG
        currency = item.get("currency")
        if currency not in ["USD", "EUR"]:
            continue

        headline = item.get("title") or item.get("event")
        if not headline:
            continue

        impact_value = str(item.get("impact", "")).lower()
        ts = int(datetime.now(TIMEZONE).timestamp())

        # Notifica tutti high impact + eventi sempre importanti
        if not (impact_value == "high" or any(k.lower() in headline.lower() for k in ALWAYS_NOTIFY)):
            continue

        events.append({
            "id": item.get("id", f"{headline}_{ts}"),
            "currency": currency,
            "headline": headline,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "impact": impact_value,
            "datetime": ts
        })

    return events

# -----------------------------
# Messaggi daily / weekly
# -----------------------------
async def send_daily():
    events = fetch_events()
    if not events:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="📅 Oggi non ci sono news importanti USD/EUR."
        )
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"], TIMEZONE).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

async def send_weekly():
    events = fetch_events()
    if not events:
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="📆 Questa settimana non ci sono news importanti USD/EUR."
        )
        return

    msg = "📆 *High Impact USD & EUR - Settimana*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"], TIMEZONE).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

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
        impact_label, _ = evaluate_impact(e["headline"], actual, forecast)
        surprise = calculate_surprise(actual, forecast)

        msg = (
            f"📊 *{e['headline']}* ({e['currency']})\n\n"
            f"Actual: {actual or 'N/D'}\n"
            f"Forecast: {forecast or 'N/D'}\n"
            f"Surprise: {round(surprise, 2) if surprise else 0}%\n\n"
            f"Impact: {impact_label}"
        )

        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode="Markdown"
        )

        notified_events.add(news_id)

# -----------------------------
# Scheduler
# -----------------------------
async def scheduler_loop():
    await application.bot.send_message(chat_id=CHAT_ID, text="✅ Bot avviato correttamente")
    await send_daily()
    await check_releases()

    schedule.every().day.at("06:00").do(lambda: asyncio.create_task(send_daily()))
    schedule.every().monday.at("06:00").do(lambda: asyncio.create_task(send_weekly()))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_releases()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
