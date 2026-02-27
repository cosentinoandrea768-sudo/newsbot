import os
import asyncio
import requests
import json
from datetime import datetime
import pytz
from flask import Flask
from telegram.ext import ApplicationBuilder

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")  # RapidAPI ForexFactory

TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# -----------------------------
# Bot Telegram async
# -----------------------------
application = ApplicationBuilder().token(BOT_TOKEN).build()

# -----------------------------
# Flask keep-alive
# -----------------------------
app = Flask("bot")

@app.route("/")
def home():
    return "🤖 Bot economico attivo!"

# -----------------------------
# Fetch eventi High Impact USD/EUR
# -----------------------------
def fetch_events():
    url = "https://forexfactory1.p.rapidapi.com/api?function=get_list"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": "forexfactory1.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    try:
        response = requests.post(url, headers=headers, json={}, timeout=10)
        data = response.json()
        # Debug dei primi eventi
        print("DEBUG API RESPONSE:", json.dumps(data[:5], indent=2))
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    for item in data:
        currency = item.get("currency")
        impact = str(item.get("impact", "")).lower()
        if currency not in ["USD", "EUR"] or impact != "high":
            continue

        ts = int(datetime.now(TIMEZONE).timestamp())
        headline = item.get("name") or item.get("title") or "–"

        event_id = item.get("id") or f"{headline}_{ts}"

        # Evita duplicazioni
        if event_id in notified_events:
            continue

        events.append({
            "id": event_id,
            "currency": currency,
            "headline": headline,
            "actual": item.get("actual"),
            "forecast": item.get("forecast"),
            "previous": item.get("previous"),
            "impact": impact,
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

        # Segna come notificato per evitare duplicazioni
        notified_events.add(e["id"])

    await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")

# -----------------------------
# Scheduler
# -----------------------------
async def scheduler_loop():
    print("🚀 Bot avviato correttamente")
    await application.bot.send_message(chat_id=CHAT_ID, text="✅ Bot avviato correttamente")

    # Invia subito il messaggio giornaliero
    await send_daily()

    # Loop scheduler ogni 5 minuti
    while True:
        await send_daily()
        await asyncio.sleep(300)  # 5 minuti

# -----------------------------
# Avvio Flask + Bot async
# -----------------------------
if __name__ == "__main__":
    # Avvio Flask in thread separato
    import threading
    port = int(os.environ.get("PORT", 10000))
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=port, debug=False), daemon=True).start()
    print(f"🚀 Bot avviato correttamente! In ascolto sulla porta {port}")

    # Avvio loop asyncio per Telegram
    asyncio.run(scheduler_loop())
