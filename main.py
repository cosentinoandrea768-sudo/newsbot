import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from flask import Flask
from telegram.ext import ApplicationBuilder
from impact_logic import evaluate_impact, calculate_surprise

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")

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
# Fetch eventi via API ForexFactory
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
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:
        currency = item.get("currency")
        impact = str(item.get("impact", "")).lower()
        if currency not in ["USD", "EUR"]:
            continue
        if impact != "high":
            continue

        # timestamp corretto della news
        date_str = item.get("date")  # esempio: "2026-02-27 14:30"
        if date_str:
            try:
                ts = int(datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE).timestamp())
            except:
                ts = int(datetime.now(TIMEZONE).timestamp())
        else:
            ts = int(datetime.now(TIMEZONE).timestamp())

        news_id = f"{item.get('name')}_{currency}_{ts}"

        events.append({
            "id": news_id,
            "currency": currency,
            "headline": item.get("name"),
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "datetime": ts
        })

    print(f"DEBUG: trovate {len(events)} news high impact USD/EUR oggi")
    return events

# -----------------------------
# Messaggi daily / weekly
# -----------------------------
def format_event_msg(event):
    date_str = datetime.fromtimestamp(event["datetime"], TIMEZONE).strftime("%Y-%m-%d %H:%M")
    actual = event["actual"] or "N/D"
    forecast = event["forecast"] or "N/D"
    previous = event["previous"] or "N/D"
    return f"{date_str} | {event['headline']} ({event['currency']})\nForecast: {forecast} | Previous: {previous}\n"

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
        msg += format_event_msg(e) + "\n"

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
            text="📆 Questa settimana non ci sono news High Impact USD/EUR."
        )
        return

    msg = "📆 *High Impact USD & EUR - Settimana*\n\n"
    for e in events:
        msg += format_event_msg(e) + "\n"

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
            f"Previous: {e.get('previous') or 'N/D'}\n"
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
# Scheduler (Render usa UTC)
# -----------------------------
async def scheduler_loop():
    await application.bot.send_message(
        chat_id=CHAT_ID,
        text="🚀 Bot avviato correttamente"
    )

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
