import os, base64, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# --- CONFIG ---
TARGET_DATE = "26JAN15"
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

def get_dynamic_games(date_str):
    prefixes = ["KXNFLGAME", "KXNBAGAME", "KXNCAAMBGAME"]
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

                if date_str in ticker and "points" not in title.lower():
                    if event_ticker not in event_map:
                        event_map[event_ticker] = {"title": m.get("event_title") or title, "tickers": []}
                    team_code = ticker.split("-")[-1]
                    event_map[event_ticker]["tickers"].append((ticker, team_code))
            cursor = resp.get("cursor")
            if not cursor: break

    formatted = {"NFL": {}, "NBA": {}, "NCAAB": {}}
    for eid, data in event_map.items():
        if len(data["tickers"]) < 2: continue
        lg = "NFL" if "NFL" in eid else ("NBA" if "NBA" in eid else "NCAAB")
        clean_title = data["title"].split("win?")[0].replace("Will the ", "").strip()
        (t1_full, t1_code), (t2_full, t2_code) = data["tickers"][:2]
        formatted[lg][clean_title] = (t1_full, t2_full, t1_code, t2_code)
    return formatted

def get_effective_yes_exposure(ticker):
    min_ts = int((datetime.now() - timedelta(hours=LOOKBACK_HOURS)).timestamp())
    cursor = ""
    yes = {"vol": 0, "val": 0}
    opp = {"vol": 0, "val": 0}
    yes_prices = []

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
            cnt = t["count"]
            price = t["yes_price"]
            if t["taker_side"] == "yes":
                yes["vol"] += cnt
                yes["val"] += cnt * price / 100
                yes_prices.append((t["created_time"], price))
            else:
                opp["vol"] += cnt
                opp["val"] += cnt * (100 - price) / 100
                yes_prices.append((t["created_time"], price))
        cursor = resp.get("cursor")
        if not cursor: break

    open_p = curr_p = None
    if yes_prices:
        yes_prices.sort(key=lambda x: x[0])
        open_p, curr_p = yes_prices[0][1], yes_prices[-1][1]
    return yes, opp, open_p, curr_p

def process_league(league_name, games_dict):
    if not games_dict: return
    print(f"\n{'='*35} {league_name} {'='*35}")
    print(f"{'GAME':<22} | {'TEAM':<4} | {'VOL':<8} | {'TOTAL $':<9} | {'POT WIN':<9} | {'NET BIAS':<10} | {'PRICE'}")
    print("-" * 120)

    for game, (t1_ticker, t2_ticker, t1_code, t2_code) in games_dict.items():
        y1, o1, p1_o, p1_c = get_effective_yes_exposure(t1_ticker)
        y2, o2, p2_o, p2_c = get_effective_yes_exposure(t2_ticker)

        # ANCHOR LOGIC: Use T1 as source of truth for price synchronization
        # This prevents "76 and 56" nonsense.
        t1_open = p1_o if p1_o is not None else (100 - p2_o if p2_o is not None else 50)
        t1_curr = p1_c if p1_c is not None else (100 - p2_c if p2_c is not None else 50)
        t2_open, t2_curr = 100 - t1_open, 100 - t1_curr

        team1 = {"vol": y1["vol"] + o2["vol"], "val": y1["val"] + o2["val"], "o": t1_open, "c": t1_curr}
        team2 = {"vol": y2["vol"] + o1["vol"], "val": y2["val"] + o1["val"], "o": t2_open, "c": t2_curr}

        pwin1, pwin2 = team1["vol"] - team1["val"], team2["vol"] - team2["val"]
        net1, net2 = pwin1 - team2["val"], pwin2 - team1["val"]

        for team, d, nb in [(t1_code, team1, net1), (t2_code, team2, net2)]:
            marker = " [!]" if nb > 20000 else ""
            print(f"{game[:22]:<22} | {team:<4} | {d['vol']:<8} | ${d['val']:<8.0f} | ${d['vol']-d['val']:<8.0f} | ${nb:<9.0f}{marker} | {d['o']}->{d['c']}")

if __name__ == "__main__":
    all_data = get_dynamic_games(TARGET_DATE)
    for league in ["NFL", "NBA", "NCAAB"]:
        process_league(league, all_data.get(league, {}))