import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from flask import Flask
from impact_logic import evaluate_impact, calculate_surprise
from telegram.ext import ApplicationBuilder

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
# Fetch eventi via API
# -----------------------------
def fetch_events():
    print("\n🔎 Chiamata API in corso...")
    
    url = "https://trader-calendar.p.rapidapi.com/api/calendar"
    headers = {
        "X-RapidAPI-Key": API_KEY,
        "X-RapidAPI-Host": "trader-calendar.p.rapidapi.com",
        "Content-Type": "application/json"
    }

    payload = {"country": "USA"}  # puoi estendere se vuoi anche EUR

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print("Status code API:", response.status_code)

        data = response.json()

        if not data:
            print("⚠️ API ha restituito lista vuota")
            return []

    except Exception as e:
        print("❌ Errore API:", e)
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

    print(f"✅ Eventi filtrati trovati: {len(events)}")
    return events

# -----------------------------
# Messaggi daily / weekly
# -----------------------------
async def send_daily():
    print("\n📅 Eseguo send_daily()")

    events = fetch_events()

    if not events:
        print("ℹ️ Nessun evento High Impact oggi")
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="📅 Oggi non ci sono news High Impact USD/EUR."
        )
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"

    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"]).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

    print("✅ Messaggio daily inviato")

async def send_weekly():
    print("\n📆 Eseguo send_weekly()")

    events = fetch_events()

    if not events:
        print("ℹ️ Nessun evento High Impact questa settimana")
        await application.bot.send_message(
            chat_id=CHAT_ID,
            text="📆 Questa settimana non ci sono news High Impact USD/EUR."
        )
        return

    msg = "📆 *High Impact USD & EUR - Settimana*\n\n"

    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"]).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=msg,
        parse_mode="Markdown"
    )

    print("✅ Messaggio weekly inviato")

# -----------------------------
# Controllo release con impatto
# -----------------------------
async def check_releases():
    print("\n⏳ Controllo nuove release...")

    events = fetch_events()

    if not events:
        print("ℹ️ Nessuna release trovata")
        return

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
            f"Surprise: {round(surprise,2) if surprise else 0}%\n\n"
            f"Impact: {impact_label}"
        )

        await application.bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode="Markdown"
        )

        notified_events.add(news_id)
        print(f"✅ Notifica inviata per {e['headline']}")

# -----------------------------
# Scheduler
# -----------------------------
async def scheduler_loop():
    print("🚀 Bot avviato")
    print("Ora server UTC:", datetime.utcnow())
    print("Ora Roma:", datetime.now(TIMEZONE))

    # Test immediato all'avvio
    await application.bot.send_message(
        chat_id=CHAT_ID,
        text="✅ Bot avviato correttamente su Render"
    )

    await send_daily()
    await check_releases()

    schedule.every().day.at("07:00").do(
        lambda: asyncio.create_task(send_daily())
    )

    schedule.every().monday.at("07:00").do(
        lambda: asyncio.create_task(send_weekly())
    )

    schedule.every(5).minutes.do(
        lambda: asyncio.create_task(check_releases())
    )

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
