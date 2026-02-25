import os
import requests
import asyncio
import schedule
from datetime import datetime, timedelta
import pytz
from telegram import Bot
from flask import Flask
import threading
from openai import OpenAI

# -----------------------------
# Variabili ambiente
# -----------------------------
TE_API_KEY = os.getenv("TE_API_KEY", "hZNeehWvHVI5wgzPn5UCbIbup3HWeLSl")  # tua API FMP
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # chiave OpenAI per riassunti
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

bot = Bot(token=BOT_TOKEN)
TIMEZONE = pytz.timezone("Europe/Rome")
notified_events = set()

# Client OpenAI nuovo
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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
# Funzioni utility
# -----------------------------
def safe_request(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("API ERROR:", e)
        return []

def summarize_text(text: str) -> str:
    if not client:
        return "⚪ OPENAI_API_KEY non impostata o quota esaurita, impossibile fare riassunto."
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"Riassumi in modo chiaro e professionale i punti principali di questo testo:\n\n{text}"
            }],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("Errore riassunto GPT:", e)
        return "⚪ Riassunto non disponibile o quota esaurita"

# -----------------------------
# Eventi Forex USD/EUR (FMP)
# -----------------------------
def get_today_events():
    url = f"https://financialmodelingprep.com/api/v4/forex-news?apikey={TE_API_KEY}"
    events = safe_request(url)
    return [
        e for e in events
        if "USD" in e.get("title", "") or "EUR" in e.get("title", "")
    ]

def get_week_events():
    # FMP free non permette filtro start/end → ritorna eventi di oggi
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
        ts = e.get("publishedDate", 0)
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"
        msg += f"{date_str} - {e.get('title')}\n"

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Weekly sent")

async def send_daily():
    events = get_today_events()
    if not events:
        print("No daily events")
        return

    msg = "📅 *High Impact USD & EUR - Oggi*\n\n"
    for e in events:
        ts = e.get("publishedDate", 0)
        date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "Unknown"
        msg += f"{date_str} - {e.get('title')}\n"

    await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
    print("Daily sent")

# -----------------------------
# Controllo news e discorsi
# -----------------------------
async def check_releases():
    events = get_today_events()

    for e in events:
        news_id = e.get("id") or e.get("publishedDate")
        if news_id in notified_events:
            continue

        actual = e.get("actual")
        forecast = e.get("forecast")
        previous = e.get("previous")

        if actual or forecast or previous:
            impact = "⚪ Non disponibile"
            msg = f"""📊 {e.get('title')}

Actual: {actual}
Forecast: {forecast}
Previous: {previous}

Impatto: {impact}
"""
        else:
            news_link = e.get("url")
            transcript = ""
            if news_link:
                try:
                    r = requests.get(news_link, timeout=10)
                    if r.status_code == 200:
                        transcript = r.text[:5000]  # limita dimensione
                except Exception as ex:
                    print("Errore fetch transcript:", ex)

            summary = summarize_text(transcript) if transcript else f"⚪ Testo non disponibile. Link: {news_link}"
            msg = f"📢 {e.get('title')}\n\n{summary}"

        await bot.send_message(chat_id=CHAT_ID, text=msg)
        notified_events.add(news_id)
        print("Release sent:", e.get("title"))

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
    print("Test Telegram inviato")

    events = get_today_events()
    print(f"News trovate: {len(events)}")

    if events:
        first = events[0]
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"📰 Test News:\n{first.get('title')}"
        )
        print("Test News inviato")

    test_text = """
    The Federal Reserve decided to keep interest rates unchanged.
    Chair Powell said inflation remains elevated and further tightening could be considered.
    """

    summary = summarize_text(test_text)

    await bot.send_message(
        chat_id=CHAT_ID,
        text=f"🤖 Test Riassunto GPT:\n\n{summary}"
    )

    print("=== TEST COMPLETATO ===")

# -----------------------------
# Avvio bot
# -----------------------------
if __name__ == "__main__":
    asyncio.run(manual_test())
