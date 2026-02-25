import os
import asyncio
import schedule
import requests
from datetime import datetime
import pytz
from telegram import Bot
from flask import Flask
import threading
from bs4 import BeautifulSoup
from impact_logic import evaluate_impact

# -----------------------------
# Variabili ambiente
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
bot = Bot(token=BOT_TOKEN)
TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# -----------------------------
# Flask keep alive
# -----------------------------
app = Flask("bot")

@app.route("/")
def home():
    return "🤖 Bot attivo!"

threading.Thread(
    target=lambda: app.run(host="0.0.0.0", port=10000),
    daemon=True
).start()

# -----------------------------
# Scraping HTML Forex Factory
# -----------------------------
def get_today_events():
    url = "https://www.forexfactory.com/calendar.php?week=this"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.forexfactory.com/"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print("Request ERROR:", e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("tr.calendar__row")

    events = []

    for row in rows:
        impact = row.select_one(".impact")
        if not impact:
            continue

        # solo high impact (3 bull icons)
        if "High Impact Expected" not in impact.get("title", ""):
            continue

        currency = row.select_one(".calendar__currency")
        if not currency:
            continue

        currency = currency.text.strip()
        if currency not in ["USD", "EUR"]:
            continue

        title = row.select_one(".calendar__event")
        actual = row.select_one(".calendar__actual")
        forecast = row.select_one(".calendar__forecast")
        previous = row.select_one(".calendar__previous")
        time_cell = row.select_one(".calendar__time")

        if not title:
            continue

        event = {
            "headline": title.text.strip(),
            "currency": currency,
            "actual": actual.text.strip() if actual else None,
            "forecast": forecast.text.strip() if forecast else None,
            "previous": previous.text.strip() if previous else None,
            "time": time_cell.text.strip() if time_cell else ""
        }

        events.append(event)

    return events


# -----------------------------
# Messaggi daily
# -----------------------------
async def send_daily():
    events = get_today_events()
    if not events:
        print("No daily events")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        msg += f"{e['time']} - {e['headline']}\n"

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Daily sent")


# -----------------------------
# Notifiche release
# -----------------------------
async def check_releases():
    events = get_today_events()

    for e in events:
        news_id = f"{e['headline']}_{e['time']}"
        if news_id in notified_events:
            continue

        impact = evaluate_impact(
            e["headline"],
            e["actual"],
            e["forecast"]
        )

        msg = (
            f"📊 {e['headline']}\n\n"
            f"Actual: {e['actual'] or '⚪ Non disponibile'}\n"
            f"Forecast: {e['forecast'] or '⚪ Non disponibile'}\n"
            f"Previous: {e['previous'] or '⚪ Non disponibile'}\n\n"
            f"Impatto: {impact}"
        )

        await bot.send_message(chat_id=CHAT_ID, text=msg)
        notified_events.add(news_id)
        print("Release sent:", e["headline"])


# -----------------------------
# Loop principale
# -----------------------------
async def main_loop():
    await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato!")

    schedule.every().day.at("07:00").do(
        lambda: asyncio.create_task(send_daily())
    )

    schedule.every(5).minutes.do(
        lambda: asyncio.create_task(check_releases())
    )

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)


# -----------------------------
# TEST MANUALE
# -----------------------------
async def manual_test():
    print("=== TEST AVVIATO ===")
    events = get_today_events()
    print("News trovate:", len(events))

    if events:
        first = events[0]
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📰 TEST:\n{first['headline']}"
        )

    print("=== TEST COMPLETATO ===")


# -----------------------------
# Avvio
# -----------------------------
if __name__ == "__main__":
    asyncio.run(manual_test())
