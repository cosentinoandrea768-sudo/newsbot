import os
import asyncio
import json
from datetime import datetime, timezone
import http.client
import pytz
from telegram import Bot
from flask import Flask

# -----------------------------
# Variabili d'ambiente
# -----------------------------
TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")

if not all([TELEGRAM_TOKEN, CHAT_ID, RAPIDAPI_KEY]):
    raise ValueError("Assicurati che BOT_TOKEN, CHAT_ID e RAPIDAPI_KEY siano impostati!")

bot = Bot(token=TELEGRAM_TOKEN)
tz = pytz.timezone("Europe/Rome")  # Orario italiano

# -----------------------------
# Funzioni di fetch e formatting
# -----------------------------
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
    data_raw = res.read()
    try:
        data = json.loads(data_raw)
    except json.JSONDecodeError:
        print("Errore parsing JSON")
        return []

    # Filtra solo eventi oggi ad alto impatto USD/EUR
    today = datetime.now(tz).date()
    events = []
    for item in data:
        # Assumendo item abbia 'currency', 'impact', 'name', 'date'
        if not isinstance(item, dict):
            continue
        currency = item.get("currency")
        impact = item.get("impact")
        date_str = item.get("date")
        if not date_str:
            continue
        try:
            event_date = datetime.fromisoformat(date_str).astimezone(tz)
        except:
            continue

        if event_date.date() == today and currency in ["USD", "EUR"] and impact == "High":
            events.append(item)
    return events

def format_event_message(event):
    name = event.get("name", "Unknown")
    currency = event.get("currency", "")
    date_str = event.get("date")
    if date_str:
        try:
            event_time = datetime.fromisoformat(date_str).astimezone(tz).strftime("%H:%M")
        except:
            event_time = "??:??"
    else:
        event_time = "??:??"

    actual = event.get("actual", "–")
    forecast = event.get("forecast", "–")
    previous = event.get("previous", "–")

    msg = f"📰 {currency} | {name}\n"
    msg += f"🕒 Ora: {event_time}\n"
    msg += f"📊 Forecast: {forecast} | Previous: {previous} | Actual: {actual}\n"
    return msg

# -----------------------------
# Funzione principale scheduler
# -----------------------------
async def send_daily():
    events = fetch_events()
    if not events:
        print("Nessuna news oggi ad alto impatto USD/EUR")
        return

    for event in events:
        msg = format_event_message(event)
        try:
            bot.send_message(chat_id=CHAT_ID, text=msg)
            print(f"Inviato messaggio: {event.get('name')}")
        except Exception as e:
            print(f"Errore invio Telegram: {e}")

async def scheduler_loop():
    print("🚀 Scheduler avviato, controllo eventi ogni 5 minuti...")
    while True:
        await send_daily()
        await asyncio.sleep(300)  # 5 minuti

# -----------------------------
# Flask Web per Render
# -----------------------------
app = Flask(__name__)

@app.route("/")
def index():
    return "Bot attivo e scheduler in esecuzione!"

# -----------------------------
# Avvio main
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Bot avviato correttamente! In ascolto sulla porta {port}")
    # Avvia loop asyncio scheduler
    asyncio.create_task(scheduler_loop())
    # Avvia Flask per endpoint
    app.run(host="0.0.0.0", port=port)
