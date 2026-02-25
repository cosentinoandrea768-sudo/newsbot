import os
import requests
import time
import schedule
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from impact_logic import evaluate_impact

# Variabili ambiente
TE_API_KEY = os.getenv("TE_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)

BASE_URL = "https://api.tradingeconomics.com/calendar"
TIMEZONE = pytz.timezone("Europe/Rome")

notified_events = set()

# Messaggio di startup
bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato e pronto a inviare notifiche!")

# Funzione sicura per chiamate API
def safe_request(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("API ERROR:", e)
        return []

# Eventi di oggi
def get_today_events():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    url = f"{BASE_URL}?c={TE_API_KEY}&importance=3&start={today}&end={today}"
    return safe_request(url)

# Eventi della settimana
def get_week_events():
    today = datetime.now(TIMEZONE)
    start = today.strftime("%Y-%m-%d")
    end = (today + timedelta(days=6)).strftime("%Y-%m-%d")
    url = f"{BASE_URL}?c={TE_API_KEY}&importance=3&start={start}&end={end}"
    return safe_request(url)

# Filtra solo USD ed EUR
def filter_usd_eur(events):
    return [e for e in events if e.get("Currency") in ["USD", "EUR"]]

# Messaggio settimanale
def send_weekly():
    events = filter_usd_eur(get_week_events())
    if not events:
        print("No weekly events")
        return

    msg = "📅 *High Impact USD & EUR - Settimana*\n\n"
    for e in events:
        msg += f"{e['Date']} - {e['Event']} ({e['Currency']})\n"

    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Weekly sent")

# Messaggio giornaliero
def send_daily():
    events = filter_usd_eur(get_today_events())
    if not events:
        print("No daily events")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        msg += f"{e['Date']} - {e['Event']} ({e['Currency']})\n"

    bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Daily sent")

# Notifiche quando escono dati
def check_releases():
    events = filter_usd_eur(get_today_events())

    for e in events:
        if e.get("Actual"):
            event_id = str(e.get("CalendarId"))
            if event_id not in notified_events:
                impact = evaluate_impact(e.get("Event"), e.get("Actual"), e.get("Forecast"))
                msg = f"""📊 {e.get("Event")} ({e.get("Currency")})

Actual: {e.get("Actual")}
Forecast: {e.get("Forecast")}
Previous: {e.get("Previous")}

Impatto: {impact}
"""
                bot.send_message(chat_id=CHAT_ID, text=msg)
                notified_events.add(event_id)
                print("Release sent:", e.get("Event"))

# Scheduler
schedule.every().monday.at("07:00").do(send_weekly)
schedule.every().day.at("07:00").do(send_daily)
schedule.every(5).minutes.do(check_releases)

print("Bot started...")

while True:
    schedule.run_pending()
    time.sleep(30)
