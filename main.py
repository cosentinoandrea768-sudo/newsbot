import os
import json
import asyncio
import requests
from datetime import datetime, timedelta
import pytz
from flask import Flask
from telegram import Bot

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PORT = int(os.getenv("PORT", 10000))

bot = Bot(token=BOT_TOKEN)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot attivo ✅"

async def send_debug():
    today = datetime.now(pytz.utc).date()
    to_date = today + timedelta(days=7)
    url = "https://ultimate-economic-calendar.p.rapidapi.com/economic-events/tradingview"
    headers = {
        "x-rapidapi-host": "ultimate-economic-calendar.p.rapidapi.com",
        "x-rapidapi-key": RAPIDAPI_KEY
    }
    params = {"from": today.isoformat(), "to": to_date.isoformat()}

    try:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print("[API ERROR]", e)
        return

    print("[DEBUG] Numero eventi ricevuti:", len(data))
    for item in data:
        print(item)  # log completo di ogni evento
        title = item.get("title") or item.get("indicator") or "No title"
        date = item.get("date") or "No date"
        message = f"{title} - {date}"
        try:
            await bot.send_message(chat_id=CHAT_ID, text=message)
        except Exception as e:
            print("[TELEGRAM ERROR]", e)

async def scheduler():
    # Messaggio di avvio
    await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot avviato correttamente")
    await send_debug()

if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=PORT)).start()
    asyncio.run(scheduler())
