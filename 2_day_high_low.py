import datetime as dt
import pytz
import time
import os
import sys
import requests
from dotenv import load_dotenv

def find_and_load_dotenv(base_dir) -> bool:
	for root, dirs, files in os.walk(base_dir):
		if '.env' in files:
			dotenv_path = os.path.join(root, '.env')
			load_dotenv(dotenv_path)
			print(f"✅ .env file loaded from: {dotenv_path}")
			return True
	return False

print("🔍 Searching for .env file...")
script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
found_dotenv = find_and_load_dotenv(script_dir)
if not found_dotenv:
	cwd_dir = os.getcwd()
	found_dotenv = find_and_load_dotenv(cwd_dir)
if not found_dotenv:
	print("⚠️  No .env file found. This is ok if you are using environment variables or secrets, but if you are not, please create a .env file in the root directory of the project.")

ALPACA_API_KEY = os.getenv("ALPACA_TEST_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_TEST_API_SECRET")
ALPACA_BASE_URL = os.getenv("BASE_URL", "https://paper-api.alpaca.markets")
STOCK_SYMBOL = os.getenv("STOCK_SYMBOL", "AAPL")

# --- Market Open Utilities ---
def is_market_open(now):
	if now.weekday() >= 5:
		return False
	open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
	close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
	return open_time <= now < close_time

def seconds_until_market_open(now):
	next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
	if now.time() >= next_open.time():
		next_open += dt.timedelta(days=1)
	while next_open.weekday() >= 5:
		next_open += dt.timedelta(days=1)
	return (next_open - now).total_seconds()

def get_bars(symbol, timeframe, limit=2):
	url = f"{ALPACA_BASE_URL}/v2/stocks/{symbol}/bars"
	headers = {
		"APCA-API-KEY-ID": ALPACA_API_KEY,
		"APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
	}
	params = {"timeframe": timeframe, "limit": limit}
	response = requests.get(url, headers=headers, params=params)
	response.raise_for_status()
	return response.json()["bars"]

def place_order(symbol, qty, side):
	url = f"{ALPACA_BASE_URL}/v2/orders"
	headers = {
		"APCA-API-KEY-ID": ALPACA_API_KEY,
		"APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
		"Content-Type": "application/json"
	}
	order = {
		"symbol": symbol,
		"qty": qty,
		"side": side,
		"type": "market",
		"time_in_force": "day"
	}
	response = requests.post(url, headers=headers, json=order)
	if response.status_code == 200:
		print(f"Order placed: {side} {qty} {symbol} (~$1.00)")
	else:
		print(f"Order failed: {response.text}")

def calculate_shares_for_dollar_amount(price, dollar_amount=1.0):
	"""Calculate the number of shares to buy/sell for a specific dollar amount"""
	shares = dollar_amount / price
	# Round to 6 decimal places (Alpaca supports fractional shares)
	return round(shares, 6)

def two_day_high_low(symbol):
	bars = get_bars(symbol, "1Day", 2)
	highs = [bar["h"] for bar in bars]
	lows = [bar["l"] for bar in bars]
	two_day_high = max(highs)
	two_day_low = min(lows)
	print(f"2-day high: {two_day_high}, 2-day low: {two_day_low}")
	return two_day_high, two_day_low

def get_last_price(symbol):
	bars = get_bars(symbol, "1Min", 1)
	return bars[-1]["c"]

if __name__ == "__main__":
	print(f"Alpaca API Key present: {bool(ALPACA_API_KEY)}")
	print(f"Alpaca API Secret present: {bool(ALPACA_SECRET_KEY)}")
	while True:
		now = dt.datetime.now(pytz.timezone('America/New_York'))
		if not is_market_open(now):
			seconds = seconds_until_market_open(now)
			hours = int(seconds // 3600)
			minutes = int((seconds % 3600) // 60)
			print(f"Market is closed. Sleeping for {hours}h {minutes}m until next open.")
			time.sleep(seconds)
		else:
			break
	two_high, two_low = two_day_high_low(STOCK_SYMBOL)
	print("Waiting for price to break 2-day high/low...")
	triggered = False
	while not triggered:
		price = get_last_price(STOCK_SYMBOL)
		print(f"Current price: {price}")
		if price > two_high:
			shares_to_buy = calculate_shares_for_dollar_amount(price, 1.0)
			print(f"Breakout above 2-day high! Buying ${1.0} worth of {STOCK_SYMBOL} ({shares_to_buy} shares).")
			place_order(STOCK_SYMBOL, shares_to_buy, "buy")
			triggered = True
		elif price < two_low:
			shares_to_sell = calculate_shares_for_dollar_amount(price, 1.0)
			print(f"Breakdown below 2-day low! Selling ${1.0} worth of {STOCK_SYMBOL} ({shares_to_sell} shares).")
			place_order(STOCK_SYMBOL, shares_to_sell, "sell")
			triggered = True
		else:
			time.sleep(60)
