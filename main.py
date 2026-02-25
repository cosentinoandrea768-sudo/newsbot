import os
import asyncio
import schedule
from datetime import datetime
import pytz
from telegram import Bot
from flask import Flask
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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
# Flask per mantenere il Web Service attivo
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
# Selenium setup headless
# -----------------------------
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=chrome_options)

# -----------------------------
# Funzioni utility
# -----------------------------
def safe_request(url):
    try:
        driver.get(url)
        return driver.page_source
    except Exception as e:
        print("Selenium ERROR:", e)
        return ""

# -----------------------------
# Scraping Forex Factory
# -----------------------------
def get_today_events():
    url = "https://www.forexfactory.com/calendar.php?week=this"
    html = safe_request(url)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    events = []
    rows = soup.select("tr.calendar__row.calendar__row--impact--3")
    for row in rows:
        currency = row.get("data-currency")
        if currency not in ["USD", "EUR"]:
            continue
        headline_tag = row.select_one(".calendar__event")
        headline = headline_tag.get_text(strip=True) if headline_tag else "Unknown"
        actual = row.get("data-actual")
        forecast = row.get("data-forecast")
        previous = row.get("data-previous")
        ts = row.get("data-timestamp")
        events.append({
            "currency": currency,
            "headline": headline,
            "actual": actual,
            "forecast": forecast,
            "previous": previous,
            "datetime": int(ts) if ts else int(datetime.now(TIMEZONE).timestamp())
        })
    return events

def get_week_events():
    return get_today_events()

# -----------------------------
# Messaggi daily/weekly
# -----------------------------
async def send_weekly():
    events = get_week_events()
    if not events:
        print("No weekly events")
        return
    msg = "📅 *High Impact USD & EUR - Settimana*\n\n"
    for e in events:
        date_str = datetime.fromtimestamp(e["datetime"]).strftime("%Y-%m-%d %H:%M")
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
        date_str = datetime.fromtimestamp(e["datetime"]).strftime("%Y-%m-%d %H:%M")
        msg += f"{date_str} - {e['headline']}\n"
    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Daily sent")

# -----------------------------
# Controllo news e impatto
# -----------------------------
async def check_releases():
    events = get_today_events()
    for e in events:
        news_id = f"{e['headline']}_{e['datetime']}"
        if news_id in notified_events:
            continue

        actual = e.get("actual")
        forecast = e.get("forecast")
        previous = e.get("previous")

        if actual or forecast or previous:
            impact = evaluate_impact(e["headline"], actual, forecast)
            msg = f"""📊 {e['headline']}

Actual: {actual or '⚪ Non disponibile'}
Forecast: {forecast or '⚪ Non disponibile'}
Previous: {previous or '⚪ Non disponibile'}

Impatto: {impact}
"""
        else:
            # Nessun valore numerico → riassunto disattivato per ora
            msg = f"📢 {e['headline']}\n⚪ Nessun valore numerico disponibile"

        await bot.send_message(chat_id=CHAT_ID, text=msg)
        notified_events.add(news_id)
        print("Release sent:", e["headline"])

# -----------------------------
# Loop principale async
# -----------------------------
async def main_loop():
    await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot avviato e pronto a inviare notifiche!")

    schedule.every().monday.at("07:00").do(lambda: asyncio.create_task(send_weekly()))
    schedule.every().day.at("07:00").do(lambda: asyncio.create_task(send_daily()))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_releases()))

    print("Bot started...")
    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# FUNZIONE TEST MANUALE
# -----------------------------
async def manual_test():
    print("=== TEST AVVIATO ===")
    await bot.send_message(chat_id=CHAT_ID, text="✅ Test Telegram OK")
    events = get_today_events()
    print(f"News trovate: {len(events)}")
    if events:
        first = events[0]
        await bot.send_message(chat_id=CHAT_ID, text=f"📰 Test News:\n{first['headline']}")
    print("=== TEST COMPLETATO ===")

# -----------------------------
# Avvio bot
# -----------------------------
if __name__ == "__main__":
    asyncio.run(manual_test())
