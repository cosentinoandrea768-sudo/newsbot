import os
import asyncio
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram import Bot
from impact_logic import evaluate_impact  # usa la tua versione esistente

# ==============================
# ENV VARS
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID non impostati!")

bot = Bot(token=BOT_TOKEN)

# ==============================
# FLASK
# ==============================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

# ==============================
# GLOBAL STATE
# ==============================
sent_events = set()

# ==============================
# MOCK NEWS
# ==============================
def get_mock_events():
    today = datetime.now(pytz.utc).date()
    events = []
    for i in range(1, 8):  # prossimi 7 giorni
        day = today + timedelta(days=i)
        events.append({
            "id": f"Mock Event {i}_{day.isoformat()}",
            "name": f"Mock Event {i}",
            "currency": "USD" if i % 2 == 0 else "EUR",
            "actual": round(100 + i * 1.5, 2),
            "forecast": round(100 + i * 1.2, 2),
            "time": day.strftime("%Y-%m-%d 12:30 UTC")
        })
    return events

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = get_mock_events()

    for event in events:
        if event["id"] in sent_events:
            continue

        label, score = evaluate_impact(event["name"], event["actual"], event["forecast"])
        message = (
            f"📊 {event['currency']} HIGH IMPACT\n"
            f"{event['name']}\n"
            f"🕒 {event['time']}\n"
            f"Actual: {event['actual']}\n"
            f"Forecast: {event['forecast']}\n"
            f"Impact Score: {score} ({label})"
        )

        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
            sent_events.add(event["id"])
            print(f"[SENT] {event['name']}")
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

# ==============================
# MESSAGGIO DI AVVIO
# ==============================
async def send_startup_message():
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente (mock mode)")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR STARTUP]", e)

# ==============================
# SCHEDULER
# ==============================
async def scheduler():
    await send_startup_message()
    while True:
        try:
            await send_events()
        except Exception as e:
            print("[LOOP ERROR]", e)
        await asyncio.sleep(300)  # controlla ogni 5 minuti

# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    from threading import Thread

    # Avvia Flask in un thread separato
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler async nel main thread
    try:
        asyncio.run(scheduler())
    except Exception as e:
        print("[FATAL ERROR]", e)
