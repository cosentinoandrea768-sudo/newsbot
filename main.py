import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
import requests
from telegram import Bot

# ===== CONFIG =====
API_KEY = os.getenv("RAPIDAPI_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Timezone italiana
TIMEZONE = timezone(timedelta(hours=1))

# ===== BOT INIT =====
bot = Bot(token=TELEGRAM_TOKEN)

# ===== FETCH NEWS =====
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
        data = response.json()  # lista di stringhe JSON
    except Exception as e:
        print("Errore API:", e)
        return []

    events = []
    ids_seen = set()

    for raw_item in data:
        try:
            item = json.loads(raw_item)  # decodifica JSON
        except:
            continue

        # Filtra solo high impact USD/EUR
        currency = item.get("currency")
        impact = str(item.get("impact", "")).lower()
        if currency not in ["USD", "EUR"]:
            continue
        if impact != "high":
            continue

        # Timestamp
        date_str = item.get("date")
        if date_str:
            try:
                ts = int(datetime.strptime(date_str, "%Y-%m-%d %H:%M").replace(tzinfo=TIMEZONE).timestamp())
            except:
                ts = int(datetime.now(TIMEZONE).timestamp())
        else:
            ts = int(datetime.now(TIMEZONE).timestamp())

        news_id = f"{item.get('name')}_{currency}_{ts}"
        if news_id in ids_seen:
            continue
        ids_seen.add(news_id)

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

# ===== FORMAT MESSAGGIO TELEGRAM =====
def format_event_message(event):
    dt = datetime.fromtimestamp(event["datetime"], tz=TIMEZONE).strftime("%Y-%m-%d %H:%M")
    actual = event["actual"] if event["actual"] is not None else "-"
    forecast = event["forecast"] if event["forecast"] is not None else "-"
    previous = event["previous"] if event["previous"] is not None else "-"

    msg = (
        f"📰 {event['headline']} ({event['currency']})\n"
        f"📅 Orario: {dt}\n"
        f"💡 Forecast: {forecast}\n"
        f"📊 Previous: {previous}\n"
        f"🔔 Actual: {actual}\n"
    )
    return msg

# ===== INVIO NEWS =====
async def send_daily():
    events = fetch_events()
    if not events:
        print("Nessuna news high impact oggi.")
        return

    for event in events:
        msg = format_event_message(event)
        try:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
        except Exception as e:
            print("Errore invio Telegram:", e)

# ===== SCHEDULER =====
async def scheduler_loop():
    print("🚀 Bot avviato correttamente")
    while True:
        await send_daily()
        await asyncio.sleep(300)  # ogni 5 minuti

# ===== MAIN =====
if __name__ == "__main__":
    asyncio.run(scheduler_loop())
