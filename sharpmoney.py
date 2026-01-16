import os, base64, time, requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
# --- CONFIG ---
TARGET_DATE = ("26JAN15")
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

# --------------------------------------------------
# Market discovery
# --------------------------------------------------
def get_dynamic_games(date_str):
    prefixes = ["KXNFLGAME", "KXNBAGAME", "KXNCAAFGAME"]
    event_map = {}

    for prefix in prefixes:
        cursor = ""
        while True:
            ts = str(int(time.time() * 1000))
            path = f"{API_PREFIX}/markets"
            params = {"series_ticker": prefix, "status": "open", "limit": 100}
            if cursor:
                params["cursor"] = cursor

            sig = sign_request(ts, "GET", path)
            headers = {
                "KALSHI-ACCESS-KEY": API_KEY_ID,
                "KALSHI-ACCESS-SIGNATURE": sig,
                "KALSHI-ACCESS-TIMESTAMP": ts
            }

            resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
            markets = resp.get("markets", [])
            if not markets:
                break

            for m in markets:
                ticker = m["ticker"]
                title = m["title"]
                event_ticker = m.get("event_ticker")

                if (
                        date_str in ticker
                        and "win" in title.lower()
                        and "points" not in title.lower()
                ):
                    if event_ticker not in event_map:
                        event_map[event_ticker] = {"title": title, "tickers": []}
                    team_code = ticker.split("-")[-1]
                    event_map[event_ticker]["tickers"].append((ticker, team_code))

            cursor = resp.get("cursor")
            if not cursor:
                break

    formatted = {"NFL": {}, "NBA": {}, "NCAAF": {}}
    for eid, data in event_map.items():
        if len(data["tickers"]) < 2:
            continue
        lg = "NFL" if "NFL" in eid else ("NBA" if "NBA" in eid else "NCAAF")
        clean_title = (
            data["title"]
            .split("win?")[0]
            .replace("Will the ", "")
            .strip()
        )
        (t1_full, t1_code), (t2_full, t2_code) = data["tickers"][:2]
        formatted[lg][clean_title] = (t1_full, t2_full, t1_code, t2_code)

    return formatted

# --------------------------------------------------
# Trade aggregation:
#   - YES + NO folded into effective exposure
#   - YES-only prices preserved for open → curr
# --------------------------------------------------
def get_effective_yes_exposure(ticker):
    min_ts = int((datetime.now() - timedelta(hours=LOOKBACK_HOURS)).timestamp())
    cursor = ""

    yes = {"vol": 0, "val": 0}
    opp = {"vol": 0, "val": 0}
    yes_prices = []  # (created_time, yes_price)

    while True:
        ts = str(int(time.time() * 1000))
        path = f"{API_PREFIX}/markets/trades"
        params = {"ticker": ticker, "min_ts": min_ts, "limit": 1000}
        if cursor:
            params["cursor"] = cursor

        sig = sign_request(ts, "GET", path)
        headers = {
            "KALSHI-ACCESS-KEY": API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts
        }

        resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
        trades = resp.get("trades", [])
        if not trades:
            break

        for t in trades:
            cnt = t["count"]
            price = t["yes_price"]

            if t["taker_side"] == "yes":
                yes["vol"] += cnt
                yes["val"] += cnt * price / 100
                yes_prices.append((t["created_time"], price))
            else:
                # NO trade → YES exposure on opponent
                opp["vol"] += cnt
                opp["val"] += cnt * (100 - price) / 100

        cursor = resp.get("cursor")
        if not cursor:
            break

    open_price = curr_price = None
    if yes_prices:
        yes_prices.sort(key=lambda x: x[0])
        open_price = yes_prices[0][1]
        curr_price = yes_prices[-1][1]

    return yes, opp, open_price, curr_price

# --------------------------------------------------
# Reporting
# --------------------------------------------------
def process_league(league_name, games_dict):
    if not games_dict:
        return

    print(f"\n{'='*35} {league_name} {'='*35}")
    print(
        f"{'GAME':<22} | {'TEAM':<4} | {'VOL':<8} | {'TOTAL $':<9} | "
        f"{'POT WIN':<9} | {'NET BIAS':<10} | {'PRICE'}"
    )
    print("-" * 120)

    for game, (t1_ticker, t2_ticker, t1_code, t2_code) in games_dict.items():
        y1, o1, p1_open, p1_curr = get_effective_yes_exposure(t1_ticker)
        y2, o2, p2_open, p2_curr = get_effective_yes_exposure(t2_ticker)

        team1 = {
            "vol": y1["vol"] + o2["vol"],
            "val": y1["val"] + o2["val"],
            "open": p1_open,
            "curr": p1_curr
        }
        team2 = {
            "vol": y2["vol"] + o1["vol"],
            "val": y2["val"] + o1["val"],
            "open": p2_open,
            "curr": p2_curr
        }

        pwin1 = team1["vol"] - team1["val"]
        pwin2 = team2["vol"] - team2["val"]

        net1 = pwin1 - team2["val"]
        net2 = pwin2 - team1["val"]

        for team, d, nb in [
            (t1_code, team1, net1),
            (t2_code, team2, net2),
        ]:
            price_str = (
                f"{d['open']}->{d['curr']}"
                if d["open"] is not None
                else "N/A"
            )
            marker = " [!]" if nb > 20000 else ""
            print(
                f"{game[:22]:<22} | {team:<4} | {d['vol']:<8} | "
                f"${d['val']:<8.0f} | ${d['vol']-d['val']:<8.0f} | "
                f"${nb:<9.0f}{marker} | {price_str}"
            )

# --------------------------------------------------
# Main
# --------------------------------------------------
if __name__ == "__main__":
    print(f"🚀 Pulling NFL, NBA, and NCAAF for {TARGET_DATE}...")
    print("✔ Exposure uses YES + NO trades")
    print("✔ Price movement uses YES trades only")

    all_data = get_dynamic_games(TARGET_DATE)

    process_league("NFL", all_data["NFL"])
    process_league("COLLEGE FOOTBALL", all_data["NCAAF"])
    process_league("NBA", all_data["NBA"])

# import os, base64, time, requests
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# from cryptography.hazmat.primitives import hashes, serialization
# from cryptography.hazmat.primitives.asymmetric import padding
#
# # --- CONFIG ---
# TARGET_DATE = "26JAN06"
# LOOKBACK_HOURS = 240
#
# load_dotenv()
# API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
# PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")
# BASE_URL = "https://api.elections.kalshi.com"
# API_PREFIX = "/trade-api/v2"
#
# with open(PRIVATE_KEY_PATH, "rb") as f:
#     private_key = serialization.load_pem_private_key(f.read(), password=None)
#
# def sign_request(timestamp, method, full_path):
#     message = f"{timestamp}{method}{full_path}"
#     signature = private_key.sign(
#         message.encode("utf-8"),
#         padding.PSS(padding.MGF1(hashes.SHA256()), padding.PSS.DIGEST_LENGTH),
#         hashes.SHA256()
#     )
#     return base64.b64encode(signature).decode("utf-8")
#
# # Helper to handle the varying precision in Kalshi's ISO timestamps
# def parse_kalshi_time(ts_str):
#     # Remove 'Z', handle fractional seconds by taking only the first 19 chars (YYYY-MM-DDTHH:MM:SS)
#     # This avoids the "Invalid isoformat string" error with varying decimal lengths
#     base_time = ts_str.split('.')[0].replace('Z', '')
#     return datetime.strptime(base_time, "%Y-%m-%dT%H:%M:%S")
#
# # --------------------------------------------------
# # Market discovery
# # --------------------------------------------------
# def get_dynamic_games(date_str):
#     prefixes = ["KXNFLGAME", "KXNBAGAME", "KXNCAAFGAME", "KXNCAABGAME"]
#     event_map = {}
#
#     for prefix in prefixes:
#         cursor = ""
#         while True:
#             ts = str(int(time.time() * 1000))
#             path = f"{API_PREFIX}/markets"
#             params = {"series_ticker": prefix, "status": "open", "limit": 100}
#             if cursor: params["cursor"] = cursor
#
#             sig = sign_request(ts, "GET", path)
#             headers = {
#                 "KALSHI-ACCESS-KEY": API_KEY_ID,
#                 "KALSHI-ACCESS-SIGNATURE": sig,
#                 "KALSHI-ACCESS-TIMESTAMP": ts
#             }
#
#             resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
#             markets = resp.get("markets", [])
#             if not markets: break
#
#             for m in markets:
#                 ticker = m["ticker"]
#                 title = m["title"]
#                 event_ticker = m.get("event_ticker")
#
#                 if (date_str in ticker and "win" in title.lower() and "points" not in title.lower()):
#                     if event_ticker not in event_map:
#                         event_map[event_ticker] = {"title": title, "tickers": []}
#                     team_code = ticker.split("-")[-1]
#                     event_map[event_ticker]["tickers"].append((ticker, team_code))
#
#             cursor = resp.get("cursor")
#             if not cursor: break
#
#     formatted = {"NFL": {}, "NBA": {}, "NCAAF": {}, "NCAAB": {}}
#     for eid, data in event_map.items():
#         if len(data["tickers"]) < 2: continue
#
#         if "NFL" in eid: lg = "NFL"
#         elif "NBA" in eid: lg = "NBA"
#         elif "NCAAF" in eid: lg = "NCAAF"
#         elif "NCAAB" in eid: lg = "NCAAB"
#         else: continue
#
#         clean_title = data["title"].split("win?")[0].replace("Will the ", "").strip()
#         (t1_full, t1_code), (t2_full, t2_code) = data["tickers"][:2]
#         formatted[lg][clean_title] = (t1_full, t2_full, t1_code, t2_code)
#
#     return formatted
#
# # --------------------------------------------------
# # Trade aggregation
# # --------------------------------------------------
# def get_detailed_trades(ticker):
#     lookback_cutoff = datetime.now() - timedelta(hours=LOOKBACK_HOURS)
#     cursor = ""
#
#     yes_vol = 0
#     yes_val = 0
#     yes_bets = []
#     no_bets = []
#     yes_prices = []
#
#     while True:
#         ts = str(int(time.time() * 1000))
#         path = f"{API_PREFIX}/markets/trades"
#         params = {"ticker": ticker, "limit": 1000}
#         if cursor: params["cursor"] = cursor
#
#         sig = sign_request(ts, "GET", path)
#         headers = {
#             "KALSHI-ACCESS-KEY": API_KEY_ID,
#             "KALSHI-ACCESS-SIGNATURE": sig,
#             "KALSHI-ACCESS-TIMESTAMP": ts
#         }
#
#         resp = requests.get(BASE_URL + path, headers=headers, params=params).json()
#         trades = resp.get("trades", [])
#         if not trades: break
#
#         for t in trades:
#             # Using the new helper function to parse time safely
#             dt_obj = parse_kalshi_time(t["created_time"])
#
#             if dt_obj < lookback_cutoff:
#                 break
#
#             cnt = t["count"]
#             price = t["yes_price"]
#             trade_time = dt_obj.strftime('%m/%d %H:%M')
#
#             if t["taker_side"] == "yes":
#                 trade_dollars = cnt * (price / 100)
#                 yes_vol += cnt
#                 yes_val += trade_dollars
#                 yes_bets.append({"val": trade_dollars, "price": price, "time": trade_time})
#                 yes_prices.append((dt_obj, price))
#             else:
#                 opp_price = 100 - price
#                 opp_trade_dollars = cnt * (opp_price / 100)
#                 no_bets.append({"val": opp_trade_dollars, "price": opp_price, "time": trade_time})
#
#         cursor = resp.get("cursor")
#         if not cursor: break
#
#         # Check if the last trade in this batch is already past our lookback
#         if trades and parse_kalshi_time(trades[-1]["created_time"]) < lookback_cutoff:
#             break
#
#     open_p = curr_p = None
#     if yes_prices:
#         yes_prices.sort(key=lambda x: x[0])
#         open_p, curr_p = yes_prices[0][1], yes_prices[-1][1]
#
#     return {
#         "vol": yes_vol, "val": yes_val, "open": open_p,
#         "curr": curr_p, "yes_list": yes_bets, "no_list": no_bets
#     }
#
# # --------------------------------------------------
# # Reporting
# # --------------------------------------------------
# def process_league(league_name, games_dict):
#     if not games_dict: return
#
#     print(f"\n{'='*55} {league_name} {'='*55}")
#
#     for game, (t1_ticker, t2_ticker, t1_code, t2_code) in games_dict.items():
#         m1 = get_detailed_trades(t1_ticker)
#         m2 = get_detailed_trades(t2_ticker)
#
#         t1_all_bets = m1["yes_list"] + m2["no_list"]
#         t1_total_val = sum(b['val'] for b in t1_all_bets)
#
#         t2_all_bets = m2["yes_list"] + m1["no_list"]
#         t2_total_val = sum(b['val'] for b in t2_all_bets)
#
#         print(f"\nGAME: {game}")
#         print(f"{'-'*140}")
#         print(f"{'SIDE':<10} | {'TOTAL $':<12} | {'TOP 10 WAGERS (Size @ Price on Date/Time)'}")
#         print(f"{'-'*140}")
#
#         for code, total_val, all_bets in [
#             (t1_code, t1_total_val, t1_all_bets),
#             (t2_code, t2_total_val, t2_all_bets)
#         ]:
#             top_10 = sorted(all_bets, key=lambda x: x['val'], reverse=True)[:10]
#             top_10_str = " | ".join([f"${b['val']:,.0f}@{b['price']}¢ ({b['time']})" for b in top_10])
#             print(f"{code:<10} | ${total_val:<11,.0f} | {top_10_str}")
#
# # --------------------------------------------------
# # Main
# # --------------------------------------------------
# if __name__ == "__main__":
#     print(f"🚀 Analyzing Large Wagers for {TARGET_DATE}...")
#     all_data = get_dynamic_games(TARGET_DATE)
#
#     process_league("NFL", all_data["NFL"])
#     process_league("COLLEGE FOOTBALL", all_data["NCAAF"])
#     process_league("COLLEGE BASKETBALL", all_data["NCAAB"])
#     process_league("NBA", all_data["NBA"])