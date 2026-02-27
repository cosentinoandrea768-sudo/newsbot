import os
import asyncio
import http.client
import json
from datetime import datetime
from telegram import Bot

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")

if not BOT_TOKEN or not CHAT_ID or not RAPIDAPI_KEY:
    raise ValueError("⚠️ BOT_TOKEN, CHAT_ID o RAPIDAPI_KEY non impostati")

bot = Bot(token=BOT_TOKEN)
print("🚀 Bot avviato correttamente")

# -----------------------------
# Costanti e filtri
# -----------------------------
API_HOST = "forexfactory1.p.rapidapi.com"
HIGH_IMPACT_CURRENCIES = ["USD", "EUR"]

# -----------------------------
# Fetch eventi
# -----------------------------
def fetch_events():
    conn = http.client.HTTPSConnection(API_HOST)
    payload = "{}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": API_HOST,
        "Content-Type": "application/json"
    }

    conn.request("POST", "/api?function=get_list", payload, headers)
    res = conn.getresponse()
    raw_data = res.read()
    data = json.loads(raw_data)

    events = []
    seen = set()
    for item in data:
        if isinstance(item, dict):
            currency = item.get("currency")
            impact = item.get("impact")
            name = item.get("name")
            date = item.get("date")
            key = (name, date, currency)
            if key not in seen and currency in HIGH_IMPACT_CURRENCIES and impact == "High":
                seen.add(key)
                events.append(item)
    return events

# -----------------------------
# Formattazione messaggio
# -----------------------------
def format_message(events):
    if not events:
        return "📌 Nessuna news high impact oggi."

    msg = f"📅 News high impact ({datetime.now().strftime('%d/%m/%Y')}):\n\n"
    for ev in events:
        date_str = ev.get("date", "??:??")
        name = ev.get("name", "Unknown")
        currency = ev.get("currency", "")
        forecast = ev.get("forecast", "N/A")
        previous = ev.get("previous", "N/A")
        msg += f"🕒 {date_str} | {currency} | {name}\n"
        msg += f"   Forecast: {forecast} | Previous: {previous}\n\n"
    return msg

# -----------------------------
# Invia messaggio
# -----------------------------
async def send_daily():
    events = fetch_events()
    msg = format_message(events)
    await bot.send_message(chat_id=CHAT_ID, text=msg)

# -----------------------------
# Scheduler loop
# -----------------------------
async def scheduler_loop():
    while True:
        await send_daily()
        await asyncio.sleep(60*60*24)  # ogni 24h, modificabile per test

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
