import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from flask import Flask, request
from impact_logic import evaluate_impact, calculate_surprise
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI key
DOMAIN = os.getenv("DOMAIN")  # es: newsbot-4yd0.onrender.com

TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()
weekly_score = {"USD": 0, "EUR": 0}

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

# Webhook route
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    asyncio.create_task(application.update_queue.put(update))
    return "OK"

# -----------------------------
# Fetch eventi via API
# -----------------------------
def fetch_events():
    url = "https://trader-calendar.p.rapidapi.com/api/calendar"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "trader-calendar.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    payload = {"country": "USA"}  # Usa "EUR" per EUR

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:
        currency = item.get("currency")
        if currency not in ["USD", "EUR"]:
            continue
        if item.get("impact") != "High":
            continue
        ts = int(datetime.now(TIMEZONE).timestamp())
        events.append({
            "id": item.get("id", f"{item.get('event')}_{ts}"),
            "currency": currency,
            "headline": item.get("event"),
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "datetime": ts
        })
    return events

# -----------------------------
# Messaggi daily / weekly
# -----------------------------
async def send_daily():
    events = fetch_events()
    if not events:
        return
    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"]).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"
    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

async def send_weekly():
    msg = "📊 *Weekly Bias Report*\n\n"
    for currency, score in weekly_score.items():
        bias = "🟢 Rialzista" if score > 0 else "🔴 Ribassista" if score < 0 else "⚪ Neutro"
        msg += f"{currency}: {score} → {bias}\n"
    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    weekly_score["USD"] = 0
    weekly_score["EUR"] = 0

# -----------------------------
# Controllo news / impatto
# -----------------------------
async def check_releases():
    events = fetch_events()
    for e in events:
        news_id = e["id"]
        if news_id in notified_events:
            continue

        actual = e.get("actual")
        forecast = e.get("forecast")
        impact_label, score = evaluate_impact(e["headline"], actual, forecast)
        surprise = calculate_surprise(actual, forecast)

        weekly_score[e["currency"]] += score

        msg = (
            f"📊 *{e['headline']}* ({e['currency']})\n\n"
            f"Actual: {actual or 'N/D'}\n"
            f"Forecast: {forecast or 'N/D'}\n"
            f"Surprise: {round(surprise,2)}%\n\n"
            f"Impact: {impact_label}"
        )
        await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        notified_events.add(news_id)

# -----------------------------
# Scheduler async
# -----------------------------
async def scheduler_loop():
    schedule.every().day.at("07:00").do(lambda: asyncio.create_task(send_daily()))
    schedule.every().monday.at("07:00").do(lambda: asyncio.create_task(send_weekly()))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_releases()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# Avvio bot + scheduler
# -----------------------------
async def main():
    # Imposta webhook Telegram
    webhook_url = f"https://{DOMAIN}/{BOT_TOKEN}"
    await application.bot.set_webhook(webhook_url)
    print(f"Webhook impostato su {webhook_url}")

    # Avvia scheduler in background
    asyncio.create_task(scheduler_loop())

if __name__ == "__main__":
    # Avvia Flask (serve webhook) + scheduler
    import threading
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000))),
        daemon=True
    ).start()
    asyncio.run(main())
