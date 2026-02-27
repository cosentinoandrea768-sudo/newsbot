import os
import json
import asyncio
import http.client
from datetime import datetime
from telegram import Bot

# ===============================
# Variabili d'ambiente
# ===============================
TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

bot = Bot(token=TELEGRAM_TOKEN)

# ===============================
# Funzione per inviare messaggi Telegram
# ===============================
async def send_telegram_message(message: str):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Telegram send: {e}")

# ===============================
# Fetch eventi da RapidAPI
# ===============================
def fetch_events():
    conn = http.client.HTTPSConnection("forexfactory1.p.rapidapi.com")
    payload = "{}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "forexfactory1.p.rapidapi.com",
        "Content-Type": "application/json"
    }
    conn.request("POST", "/api?function=get_list", payload, headers)
    res = conn.getresponse()
    data = res.read()
    try:
        data_json = json.loads(data)
    except json.JSONDecodeError:
        print("[ERROR] JSON decode failed")
        return []

    events_today = []
    for item in data_json:
        try:
            event_date = datetime.strptime(item.get("date"), "%Y-%m-%dT%H:%M:%S")
        except Exception:
            continue  # salta se data non valida

        # filtro solo high-impact USD/EUR
        if item.get("impact") == "high" and item.get("currency") in ["USD", "EUR"]:
            if event_date.date() == datetime.now().date():
                events_today.append({
                    "name": item.get("name"),
                    "currency": item.get("currency"),
                    "date": event_date,
                    "actual": item.get("actual"),
                    "forecast": item.get("forecast"),
                    "previous": item.get("previous")
                })
    print(f"[DEBUG] Eventi filtrati oggi: {len(events_today)}")
    return events_today

# ===============================
# Formatta messaggio Telegram
# ===============================
def format_event_message(events):
    messages = []
    for e in events:
        msg = (
            f"📅 <b>{e['date'].strftime('%d/%m/%Y %H:%M')}</b>\n"
            f"💹 <b>{e['currency']}</b> - {e['name']}\n"
            f"📊 Forecast: {e['forecast'] or '-'} | "
            f"Previous: {e['previous'] or '-'} | "
            f"Actual: {e['actual'] or '-'}"
        )
        messages.append(msg)
    return "\n\n".join(messages)

# ===============================
# Scheduler principale
# ===============================
async def send_daily():
    events = fetch_events()
    if not events:
        await send_telegram_message("📌 Nessuna news high-impact USD/EUR oggi.")
        return

    message = format_event_message(events)
    await send_telegram_message(message)

async def scheduler_loop():
    # Messaggio di avvio
    await send_telegram_message("🚀 Bot avviato correttamente")
    while True:
        await send_daily()
        await asyncio.sleep(300)  # ogni 5 minuti

# ===============================
# Main
# ===============================
if __name__ == "__main__":
    print("🚀 Bot avviato, loop scheduler in partenza...")
    asyncio.run(scheduler_loop())
