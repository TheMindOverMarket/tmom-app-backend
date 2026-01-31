import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
API_SECRET = os.getenv("ALPACA_API_SECRET")
# Explicitly use paper API
BASE_URL = "https://paper-api.alpaca.markets"

headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": API_SECRET
}

def place_order():
    url = f"{BASE_URL}/v2/orders"
    payload = {
        "symbol": "BTC/USD",
        "qty": "0.001",  # Small amount
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc"
    }
    
    print(f"Sending Market BUY for 0.001 BTC/USD to {url}...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        print(f"Order SUCCESS: {response.json().get('id')}")
    else:
        print(f"Order FAILED ({response.status_code}): {response.text}")

if __name__ == "__main__":
    place_order()
