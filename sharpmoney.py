import os, base64, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- CONFIG ---
TARGET_DATE = "25DEC29"

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

def get_dynamic_games(date_str):
    prefixes = ["KXNFLGAME", "KXNBAGAME", "KXNCAAFGAME"]
    event_map = {}

    for prefix in prefixes:
        cursor = ""
        while True:
            timestamp = str(int(time.time() * 1000))
            path = f"{API_PREFIX}/markets"
            params = {"series_ticker": prefix, "status": "open", "limit": 100}
            if cursor: params["cursor"] = cursor

            sig = sign_request(timestamp, "GET", path)
            headers = {"KALSHI-ACCESS-KEY": API_KEY_ID, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": timestamp}

            resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
            markets = resp.get("markets", [])
            if not markets: break

            for m in markets:
                ticker = m['ticker']
                title = m['title']
                event_ticker = m.get('event_ticker')

                if date_str in ticker and "win" in title.lower() and "points" not in title.lower():
                    if event_ticker not in event_map:
                        event_map[event_ticker] = {"title": title, "tickers": []}
                    team_code = ticker.split('-')[-1]
                    event_map[event_ticker]["tickers"].append((ticker, team_code))

            cursor = resp.get("cursor")
            if not cursor: break

    formatted = {"NFL": {}, "NBA": {}, "NCAAF": {}}
    for eid, data in event_map.items():
        if len(data["tickers"]) < 2: continue
        lg = "NFL" if "NFL" in eid else ("NBA" if "NBA" in eid else "NCAAF")
        clean_title = data["title"].split("win?")[0].replace("Will the ", "").strip()
        t1_full, t1_code = data["tickers"][0]
        t2_full, t2_code = data["tickers"][1]
        formatted[lg][clean_title] = (t1_full, t2_full, t1_code, t2_code)

    return formatted

def get_market_metrics(ticker):
    min_ts = int((datetime.now() - timedelta(hours=240)).timestamp())
    all_yes_trades = []
    cursor = ""

    while True:
        timestamp = str(int(time.time() * 1000))
        path = f"{API_PREFIX}/markets/trades"
        params = {"ticker": ticker, "min_ts": min_ts, "limit": 1000}
        if cursor: params["cursor"] = cursor

        sig = sign_request(timestamp, "GET", path)
        headers = {"KALSHI-ACCESS-KEY": API_KEY_ID, "KALSHI-ACCESS-SIGNATURE": sig, "KALSHI-ACCESS-TIMESTAMP": timestamp}

        try:
            resp = requests.get(BASE_URL + path, headers=headers, params=params)
            data = resp.json()
            trades = data.get("trades", [])
            if not trades: break
            all_yes_trades.extend([t for t in trades if t.get("taker_side") == "yes"])
            cursor = data.get("cursor")
            if not cursor: break
        except Exception: break

    if not all_yes_trades:
        return {"vol": 0, "val": 0, "avg": 0, "open": 0, "curr": 0}

    total_contracts = sum(t['count'] for t in all_yes_trades)
    total_val_usd = sum((t['count'] * t['yes_price']) / 100 for t in all_yes_trades)
    avg_bet = total_val_usd / len(all_yes_trades)
    sorted_trades = sorted(all_yes_trades, key=lambda x: x['created_time'])

    return {
        "vol": total_contracts,
        "val": total_val_usd,
        "avg": avg_bet,
        "open": sorted_trades[0]['yes_price'],
        "curr": sorted_trades[-1]['yes_price']
    }

def process_league(league_name, games_dict):
    if not games_dict: return
    print(f"\n{'='*35} {league_name} {'='*35}")
    # Added POT WIN to the header
    print(f"{'GAME':<22} | {'TEAM':<4} | {'VOL':<8} | {'TOTAL $':<10} | {'POT WIN':<10} | {'AVG BET':<9} | {'PRICE'}")
    print("-" * 115)

    for game, (t1_ticker, t2_ticker, t1_code, t2_code) in games_dict.items():
        m1 = get_market_metrics(t1_ticker)
        m2 = get_market_metrics(t2_ticker)

        for team, d, opp in [(t1_code, m1, m2), (t2_code, m2, m1)]:
            label = ""
            if d['avg'] > opp['avg'] * 1.5 and d['curr'] > d['open'] and d['vol'] > 100:
                label = "🔥 STEAM"
            elif d['val'] > opp['val'] and d['curr'] <= d['open'] and d['vol'] > 1000:
                label = "🎯 ABSORP"

            # Potential Win Calculation:
            # Total Payout (vol * $1) minus Total Cost (val)
            potential_win = d['vol'] - d['val']

            # Print including the new potential_win column
            print(f"{game[:22]:<22} | {team:<4} | {d['vol']:<8} | ${d['val']:<9.0f} | ${potential_win:<9.0f} | ${d['avg']:<8.2f} | {d['open']}->{d['curr']} | {label}")

if __name__ == "__main__":
    print(f"🚀 Pulling NFL, NBA, and NCAAF for {TARGET_DATE}...")
    all_data = get_dynamic_games(TARGET_DATE)

    process_league("NFL", all_data["NFL"])
    process_league("COLLEGE FOOTBALL", all_data["NCAAF"])
    process_league("NBA", all_data["NBA"])