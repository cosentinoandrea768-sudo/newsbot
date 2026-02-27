import os
import asyncio
import schedule
import requests
import json
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram.ext import ApplicationBuilder
from impact_logic import evaluate_impact, calculate_surprise
import threading

# -----------------------------
# Config
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
API_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI ForexFactory
TIMEZONE = pytz.timezone("Europe/Rome")

NOTIFIED_FILE = "notified.json"
HIGH_IMPACT_KEYWORDS = ["ppi", "core ppi"]  # Eventi di interesse extra

# -----------------------------
# Telegram Bot
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
# Notifiche già inviate
# -----------------------------
if os.path.exists(NOTIFIED_FILE):
    with open(NOTIFIED_FILE, "r") as f:
        notified_events = set(json.load(f))
else:
    notified_events = set()

def save_notified():
    with open(NOTIFIED_FILE, "w") as f:
        json.dump(list(notified_events), f)

# -----------------------------
# Fetch eventi ForexFactory
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
    ts_now = datetime.now(TIMEZONE)
    for item in data:
        currency = item.get("currency")
        headline = item.get("name")
        impact_value = str(item.get("impact", "")).lower()
        graph = item.get("graph", [])

        # Filtra solo USD/EUR e high impact
        if currency not in ["USD", "EUR"]:
            continue
        if impact_value != "high" and not any(k in headline.lower() for k in HIGH_IMPACT_KEYWORDS):
            continue

        # Prendi il primo release con actual
        actual_data = next((g for g in graph if g.get("actual") is not None), None)
        if actual_data:
            date_str = actual_data.get("dateline")
            dt = datetime.fromisoformat(date_str).astimezone(TIMEZONE) if date_str else ts_now
            events.append({
                "id": item.get("id", f"{headline}_{dt.timestamp()}"),
                "currency": currency,
                "headline": headline,
                "actual": actual_data.get("actual"),
                "forecast": actual_data.get("forecast"),
                "previous": actual_data.get("previous"),
                "impact": impact_value,
                "datetime": dt
            })
    return events

# -----------------------------
# Daily message
# -----------------------------
async def send_daily():
    events = fetch_events()
    today = datetime.now(TIMEZONE).date()
    daily_events = [e for e in events if e["datetime"].date() == today]
    
    if not daily_events:
        await application.bot.send_message(chat_id=CHAT_ID, text="📅 Oggi non ci sono news High Impact USD/EUR.")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in daily_events:
        date_str = e["datetime"].strftime("%H:%M")
        actual = e["actual"] or "N/D"
        forecast = e["forecast"] or "N/D"
        previous = e["previous"] or "N/D"
        msg += f"*{e['headline']}* ({e['currency']})\n"
        msg += f"🕒 {date_str} | Forecast: {forecast} | Previous: {previous} | Actual: {actual}\n\n"

    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# -----------------------------
# Weekly message
# -----------------------------
async def send_weekly():
    events = fetch_events()
    today = datetime.now(TIMEZONE).date()
    start_week = today - timedelta(days=today.weekday())  # Monday
    weekly_events = [e for e in events if start_week <= e["datetime"].date() <= today]

    if not weekly_events:
        await application.bot.send_message(chat_id=CHAT_ID, text="📅 Nessuna news High Impact USD/EUR questa settimana.")
        return

    msg = "🗓️ *High Impact USD & EUR - Settimana*\n\n"
    for e in weekly_events:
        date_str = e["datetime"].strftime("%a %H:%M")
        actual = e["actual"] or "N/D"
        forecast = e["forecast"] or "N/D"
        previous = e["previous"] or "N/D"
        msg += f"*{e['headline']}* ({e['currency']})\n"
        msg += f"🕒 {date_str} | Forecast: {forecast} | Previous: {previous} | Actual: {actual}\n\n"

    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# -----------------------------
# Immediate release notifications
# -----------------------------
async def check_releases():
    events = fetch_events()
    for e in events:
        news_id = f"{e['id']}_{e['datetime'].isoformat()}"
        if news_id in notified_events:
            continue
        if e["actual"] is None:
            continue

        impact_label, _ = evaluate_impact(e["headline"], e["actual"], e["forecast"])
        surprise = calculate_surprise(e["actual"], e["forecast"])
        msg = (
            f"📊 *{e['headline']}* ({e['currency']})\n\n"
            f"Actual: {e['actual']}\n"
            f"Forecast: {e['forecast'] or 'N/D'}\n"
            f"Surprise: {round(surprise, 2)}%\n\n"
            f"Impact: {impact_label}"
        )
        await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
        notified_events.add(news_id)
        save_notified()

# -----------------------------
# Scheduler
# -----------------------------
async def scheduler_loop():
    print("🚀 Bot avviato correttamente")
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
