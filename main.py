import os
import requests
import asyncio
import schedule
import pytz
from datetime import datetime
from telegram import Bot
from flask import Flask
import threading
from bs4 import BeautifulSoup
from openai import OpenAI

# -----------------------------
# VARIABILI AMBIENTE
# -----------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not BOT_TOKEN or not CHAT_ID:
    raise ValueError("BOT_TOKEN o CHAT_ID mancanti!")

bot = Bot(token=BOT_TOKEN)
TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

# -----------------------------
# FLASK KEEP ALIVE
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
# SCRAPING FOREX FACTORY
# -----------------------------
def scrape_forex_factory():
    url = "https://www.forexfactory.com/calendar"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        events = []

        rows = soup.find_all("tr", class_="calendar__row")
        for row in rows:
            currency = row.find("td", class_="calendar__currency")
            impact = row.find("td", class_="calendar__impact")
            title = row.find("td", class_="calendar__event")

            if not currency or not impact or not title:
                continue

            currency_text = currency.text.strip()
            impact_icons = impact.find_all("span", class_="high")

            if currency_text not in ["USD", "EUR"]:
                continue

            if len(impact_icons) < 3:
                continue

            events.append({
                "id": title.text.strip(),
                "currency": currency_text,
                "title": title.text.strip()
            })

        return events

    except Exception as e:
        print("Errore scraping:", e)
        return []

# -----------------------------
# OPENAI RIASSUNTO
# -----------------------------
def summarize_text(text):
    if not client:
        return "OPENAI_API_KEY non impostata."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Riassumi in modo chiaro e professionale:\n\n{text}"}],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Errore OpenAI:", e)
        return "Riassunto non disponibile."

# -----------------------------
# CHECK EVENTI
# -----------------------------
async def check_events():
    events = scrape_forex_factory()
    print(f"Eventi trovati: {len(events)}")
    for event in events:
        if event["id"] in notified_events:
            continue

        message = f"📅 High Impact {event['currency']}\n\n📢 {event['title']}"
        await bot.send_message(chat_id=CHAT_ID, text=message)
        notified_events.add(event["id"])
        print("Inviato:", event["title"])

# -----------------------------
# LOOP PRINCIPALE
# -----------------------------
async def main_loop():
    await bot.send_message(chat_id=CHAT_ID, text="🤖 Bot Forex attivo (Scraping ForexFactory)")

    schedule.every(5).minutes.do(lambda: asyncio.create_task(check_events()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(30)

# -----------------------------
# AVVIO
# -----------------------------
if __name__ == "__main__":
    asyncio.run(main_loop())
