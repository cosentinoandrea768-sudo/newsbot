import os
import asyncio
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram import Bot
from impact_logic import evaluate_impact

# ==============================
# ENV VARS
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID non impostati")

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
# MOCK NEWS (per test e sviluppo)
# ==============================
def get_mock_events():
    today = datetime.now(pytz.utc)
    events = []
    for i in range(1, 8):  # 7 giorni
        event_time = today + timedelta(days=i)
        dateline = event_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        events.append({
            "id": f"Mock_Event_{i}_{dateline}",
            "name": f"Mock Event {i}",
            "currency": "USD" if i % 2 == 0 else "EUR",
            "actual": round(100 + i * 0.5, 2),
            "forecast": round(100 + i * 0.2, 2),
            "time": event_time.strftime("%H:%M UTC")
        })
    return events

# ==============================
# FUNZIONE FETCH EVENTS
# ==============================
async def fetch_events():
    """
    Qui puoi sostituire con la chiamata reale all'API.
    Per ora restituisce mock events.
    """
    # Esempio di utilizzo API reale:
    # events = call_real_api()
    # return events
    return get_mock_events()

# ==============================
# INVIO TELEGRAM
# ==============================
async def send_events():
    events = await fetch_events()

    if not events:
        print("[INFO] Nessuna news oggi")
        return

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
# SCHEDULER
# ==============================
async def scheduler():
    # Messaggio di startup
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
        print("[DEBUG] Messaggio di startup inviato")
    except Exception as e:
        print("[TELEGRAM ERROR] Startup:", e)

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

    # Avvia Flask in background
    def run_flask():
        app.run(host="0.0.0.0", port=PORT)

    Thread(target=run_flask).start()

    # Avvia scheduler
    asyncio.run(scheduler())
