import requests
from datetime import datetime
import pytz

# Chiave pubblica TE
TE_API_KEY = "guest:guest"
BASE_URL = "https://api.tradingeconomics.com/calendar"
TIMEZONE = pytz.timezone("Europe/Rome")

def safe_request(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("API ERROR:", e)
        return []

def test_today_events():
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    url = f"{BASE_URL}?c={TE_API_KEY}&importance=3&start={today}&end={today}"
    events = safe_request(url)
    if not events:
        print("Nessun evento high impact oggi")
    else:
        print(f"Trovati {len(events)} eventi oggi (guest:guest):")
        for e in events:
            print(f"{e.get('Date')} - {e.get('Event')} ({e.get('Currency')})")

if __name__ == "__main__":
    test_today_events()
