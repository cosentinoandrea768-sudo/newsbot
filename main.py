import os
import requests
import asyncio
import schedule
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from flask import Flask
import threading

# Variabili ambiente
TE_API_KEY = os.getenv("TE_API_KEY", "hZNeehWvHVI5wgzPn5UCbIbup3HWeLSl")  # Usa la tua API privata se non impostata
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)
TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# Flask per mantenere il Web Service attivo
app = Flask("bot")

@app.route("/")
def home():
    return "🤖 Bot attivo!"

threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()

# Funzione sicura per chiamate API Finnhub/AlphaVantage/FMP
def safe_request(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("API ERROR:", e)
        return []

# Ottieni news Forex (USD/EUR) di oggi
def get_today_events():
    today_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    # Endpoint Finnhub esempio, adattabile ad altre API
    url = f"https://finnhub.io/api/v1/news?category=forex&token={TE_API_KEY}"
    events = safe_request(url)
    # Filtra solo news USD/EUR
    return [e for e in events if "USD" in e.get("headline","") or "EUR" in e.get("headline","")]

# Ottieni news Forex della settimana
def get_week_events():
    events = get_today_events()  # Finnhub non permette filtro start/end nella free key
    # In alternativa potresti salvare eventi giornalieri in locale e aggregarli
    return events

# Messaggi weekly/daily async
async def send_weekly():
    events = get_week_events()
    if not events:
        print("No weekly events")
        return

    msg = "📅 *High Impact USD & EUR - Settimana*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e.get("datetime",0)).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Weekly sent")

async def send_daily():
    events = get_today_events()
    if not events:
        print("No daily events")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e.get("datetime",0)).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Daily sent")

# Notifiche quando escono nuove news
async def check_releases():
    events = get_today_events()

    for e in events:
        news_id = e.get("id") or e.get("datetime")  # usa id unico se disponibile
        if news_id not in notified_events:
            msg = f"""📊 {e.get("headline")}

Link: {e.get("url")}
"""
            await bot.send_message(chat_id=CHAT_ID, text=msg)
            notified_events.add(news_id)
            print("Release sent:", e.get("headline"))

# Loop principale async
async def main_loop():
    # Messaggio di startup
    await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato e pronto a inviare notifiche!")

    # Scheduler daily/weekly
    schedule.every().monday.at("07:00").do(lambda: asyncio.create_task(send_weekly()))
    schedule.every().day.at("07:00").do(lambda: asyncio.create_task(send_daily()))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_releases()))

    print("Bot started...")

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# Avvio
asyncio.run(main_loop())
