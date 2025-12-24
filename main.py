import os
import base64
import time
import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# ------------------------------------------------------------
# Load env
# ------------------------------------------------------------
load_dotenv()

API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
PRIVATE_KEY_PATH = os.getenv("KALSHI_PRIVATE_KEY_PATH")

if not API_KEY_ID or not PRIVATE_KEY_PATH:
    raise RuntimeError("Missing KALSHI_API_KEY_ID or KALSHI_PRIVATE_KEY_PATH")

# ------------------------------------------------------------
# Base URL (production, migrated host)
# ------------------------------------------------------------
BASE_URL = "https://api.elections.kalshi.com"
API_PREFIX = "/trade-api/v2"

# ------------------------------------------------------------
# Load private key
# ------------------------------------------------------------
with open(PRIVATE_KEY_PATH, "rb") as f:
    private_key = serialization.load_pem_private_key(f.read(), password=None)

# ------------------------------------------------------------
# Signing function
# ------------------------------------------------------------
def sign_request(private_key, timestamp, method, full_path, body=""):
    message = f"{timestamp}{method}{full_path}{body}"

    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    return base64.b64encode(signature).decode("utf-8")

# ------------------------------------------------------------
# Get balance
# ------------------------------------------------------------
def get_balance():
    method = "GET"
    resource_path = "/portfolio/balance"
    full_path = API_PREFIX + resource_path
    body = ""

    timestamp = str(int(time.time()))  # seconds

    signature = sign_request(
        private_key,
        timestamp,
        method,
        full_path,
        body,
    )

    headers = {
        "KALSHI-ACCESS-KEY": API_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
    }

    response = requests.get(BASE_URL + full_path, headers=headers)

    if response.status_code != 200:
        raise RuntimeError(
            f"Request Failed ({response.status_code}): {response.text}"
        )

    data = response.json()
    balance_cents = data.get("balance", 0)

    print("---- Kalshi Portfolio ----")
    print(f"Available Balance: ${balance_cents / 100:,.2f}")

# ------------------------------------------------------------
# Run
# ------------------------------------------------------------
if __name__ == "__main__":
    get_balance()
