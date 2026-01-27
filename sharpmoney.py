import os, base64, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- CONFIG ---
TARGET_DATE = "26JAN25"
LOOKBACK_HOURS = 240

load_dotenv()
API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")
BASE_URL = "https://api.elections.kalshi.com"
API_PREFIX = "/trade-api/v2"

with open(PRIVATE_KEY_PATH, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

def sign_request(timestamp, method, full_path):
    message = f"{timestamp}{method}{full_path}"
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(padding.MGF1(hashes.SHA256()), padding.PSS.DIGEST_LENGTH),
        hashes.SHA256()
    )
    return base64.b64encode(signature).decode("utf-8")

def get_dynamic_markets(date_str):
    # Added Championship prefixes
    prefixes = ["KXNFLGAME", "KXNBAGAME", "KXNCAAFGAME", "KXNFLNFCCHAMP", "KXNFLAFCCHAMP"]
    event_map = {}

    for prefix in prefixes:
        cursor = ""
        while True:
            ts = str(int(time.time() * 1000))
            path = f"{API_PREFIX}/markets"
            params = {"series_ticker": prefix, "status": "open", "limit": 100}
            if cursor: params["cursor"] = cursor

            sig = sign_request(ts, "GET", path)
            headers = {"KALSHI-ACCESS-KEY": API_KEY_ID, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts}

            resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
            markets = resp.get("markets", [])
            if not markets: break

            for m in markets:
                ticker = m["ticker"]
                title = m["title"]
                event_ticker = m.get("event_ticker")

                # Filter for the specific date or the Championship year suffix (-25)
                is_champ = "CHAMP" in ticker
                if (date_str in ticker or (is_champ and date_str[-2:] in ticker)) and "win" in title.lower():
                    if event_ticker not in event_map:
                        event_map[event_ticker] = {"title": title, "tickers": []}
                    team_code = ticker.split("-")[-1]
                    event_map[event_ticker]["tickers"].append((ticker, team_code))

            cursor = resp.get("cursor")
            if not cursor: break

    # Separate Games (binary) from Championships (multi-outcome)
    formatted = {"NFL": {}, "NBA": {}, "NCAAF": {}, "CHAMPS": {}}
    for eid, data in event_map.items():
        if "CHAMP" in eid:
            clean_title = data["title"].split("win?")[0].replace("Which team will win the ", "").strip()
            formatted["CHAMPS"][clean_title] = data["tickers"]
        elif len(data["tickers"]) >= 2:
            lg = "NFL" if "NFL" in eid else ("NBA" if "NBA" in eid else "NCAAF")
            clean_title = data["title"].split("win?")[0].replace("Will the ", "").strip()
            # Only take the first two for a standard head-to-head game
            (t1_full, t1_code), (t2_full, t2_code) = data["tickers"][:2]
            formatted[lg][clean_title] = (t1_full, t2_full, t1_code, t2_code)

    return formatted

def get_exposure(ticker):
    min_ts = int((datetime.now() - timedelta(hours=LOOKBACK_HOURS)).timestamp())
    cursor = ""
    yes = {"vol": 0, "val": 0}
    opp = {"vol": 0, "val": 0}
    prices = []

    while True:
        ts = str(int(time.time() * 1000))
        path = f"{API_PREFIX}/markets/trades"
        params = {"ticker": ticker, "min_ts": min_ts, "limit": 1000}
        if cursor: params["cursor"] = cursor

        sig = sign_request(ts, "GET", path)
        headers = {"KALSHI-ACCESS-KEY": API_KEY_ID, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": ts}
        resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
        trades = resp.get("trades", [])
        if not trades: break

        for t in trades:
            cnt, price = t["count"], t["yes_price"]
            if t["taker_side"] == "yes":
                yes["vol"] += cnt
                yes["val"] += cnt * price / 100
                prices.append(price)
            else:
                opp["vol"] += cnt
                opp["val"] += cnt * (100 - price) / 100

        cursor = resp.get("cursor")
        if not cursor: break

    open_p = prices[0] if prices else None
    curr_p = prices[-1] if prices else None
    return yes, opp, open_p, curr_p

def process_championships(champs_dict):
    for event_name, teams in champs_dict.items():
        print(f"\n{'='*35} {event_name.upper()} {'='*35}")
        print(f"{'TEAM':<6} | {'VOL':<8} | {'TOTAL $':<10} | {'PRICE':<12}")
        print("-" * 50)
        for ticker, code in teams:
            yes, _, open_p, curr_p = get_exposure(ticker)
            price_str = f"{open_p}->{curr_p}" if open_p else "N/A"
            print(f"{code:<6} | {yes['vol']:<8} | ${yes['val']:<9.0f} | {price_str}")

def process_league(league_name, games_dict):
    if not games_dict: return
    print(f"\n{'='*35} {league_name} {'='*35}")
    print(f"{'GAME':<22} | {'TEAM':<4} | {'VOL':<8} | {'TOTAL $':<9} | {'NET BIAS':<10} | {'PRICE'}")
    print("-" * 95)
    for game, (t1, t2, c1, c2) in games_dict.items():
        y1, o1, p1o, p1c = get_exposure(t1)
        y2, o2, p2o, p2c = get_exposure(t2)

        # Aggregate logic
        for code, vol, val, op, cp in [(c1, y1['vol']+o2['vol'], y1['val']+o2['val'], p1o, p1c),
                                       (c2, y2['vol']+o1['vol'], y2['val']+o1['val'], p2o, p2c)]:
            price_str = f"{op}->{cp}" if op else "N/A"
            print(f"{game[:22]:<22} | {code:<4} | {vol:<8} | ${val:<8.0f} | ${vol-val:<9.0f} | {price_str}")

if __name__ == "__main__":
    print(f"🚀 Pulling NFL, NBA, NCAAF & Conference Markets for {TARGET_DATE}...")
    data = get_dynamic_markets(TARGET_DATE)

    process_league("NFL GAMES", data["NFL"])
    process_championships(data["CHAMPS"])
    process_league("COLLEGE FOOTBALL", data["NCAAF"])
    process_league("NBA", data["NBA"])