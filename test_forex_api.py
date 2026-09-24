import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
from dotenv import load_dotenv
import os
load_dotenv()

api_key = os.getenv("TWELVE_DATA_API_KEY")
print(f"API Key: {api_key}")

url = "https://api.twelvedata.com/time_series"
params = {
    "symbol": "EUR/USD",
    "interval": "1day",
    "outputsize": 5,
    "apikey": api_key
}

print(f"Request: {url}")
r = requests.get(url, params=params, timeout=15)
print(f"Status: {r.status_code}")
print(f"Response: {r.text[:500]}")
