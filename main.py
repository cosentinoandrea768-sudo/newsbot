import os
import asyncio
import json
import pytz
from datetime import datetime
from flask import Flask
from telegram import Bot
from telegram.ext import ApplicationBuilder
import requests
from impact_logic import evaluate_impact, calculate_surprise

# -----------------------------
# Config e variabili ambiente
# -----------------------------
RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

if not RAPIDAPI_KEY or not BOT_TOKEN or not CHAT_ID:
    raise ValueError("Assicurati che le env vars RAPIDAPI_KEY, BOT_TOKEN e CHAT_ID siano settate.")

# -----------------------------
# Flask app per Render
# -----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot running!"

# -----------------------------
# Funzioni bot
# -----------------------------
async def send_daily():
    events = fetch_events()
    bot = Bot(token=BOT_TOKEN)
    for event in events:
        name = event.get("event")
        actual = event.get("actual")
        forecast = event.get("forecast")
        label, score = evaluate_impact(name, actual, forecast)
        message = f"{name}\nActual: {actual}\nForecast: {forecast}\nImpact: {label} ({score})"
        await bot.send_message(chat_id=CHAT_ID, text=message)

def fetch_events():
    url = "https://mcp.rapidapi.com/get_list"
    headers = {
        "x-api-host": "forexfactory1.p.rapidapi.com",
        "x-api-key": RAPIDAPI_KEY,
        "Content-Type": "application/json"
    }
    body = {"some_param": "value"}  # eventuale payload richiesto dalla tua API
    response = requests.post(url, headers=headers, json=body)
    data = response.json()
    
    # Assicuriamoci di avere una lista di dict
    events = []
    for item in data.get("events", []):
        if isinstance(item, dict):
            events.append(item)
    return events

async def scheduler_loop():
    while True:
        await send_daily()
        await asyncio.sleep(60*60)  # controlla ogni ora

# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render richiede PORT
    # Avvio Flask
    from threading import Thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=port)).start()
    # Avvio bot loop
    asyncio.run(scheduler_loop())
