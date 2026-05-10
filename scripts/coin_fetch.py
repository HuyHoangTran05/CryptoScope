import os
import time
import requests
import pandas as pd
from datetime import datetime, timezone

# =========================
# 1. Danh sách coin cần lấy
# =========================
COIN_IDS = [
    "binancecoin",
    "bitcoin",
    "cardano",
    "dogecoin",
    "ethereum",
    "figure-heloc",
    "hyperliquid",
    "litecoin",
    "ripple",
    "solana",
    "tether",
    "tron",
    "usd-coin",
    "usds",
    "whitebit",
    "zcash",
]

# =========================
# 2. Giai đoạn cần lấy
# 01/03/2024 -> 31/12/2024
# =========================
START_DATE = "2024-03-01"
END_DATE = "2024-12-31"

def to_unix(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

FROM_TS = to_unix(START_DATE)
TO_TS = to_unix("2025-01-01")  # lấy đến hết 31/12/2024

# =========================
# 3. Hàm tải dữ liệu từ CoinGecko
# =========================
def fetch_coin_market_data(coin_id, vs_currency="usd"):
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart/range"

    params = {
        "vs_currency": vs_currency,
        "from": FROM_TS,
        "to": TO_TS,
    }

    response = requests.get(url, params=params, timeout=30)

    if response.status_code != 200:
        print(f"[ERROR] {coin_id}: {response.status_code} - {response.text[:200]}")
        return None

    data = response.json()

    prices = data.get("prices", [])
    market_caps = data.get("market_caps", [])
    volumes = data.get("total_volumes", [])

    if not prices or not market_caps:
        print(f"[WARNING] {coin_id}: thiếu prices hoặc market_caps")
        return None

    df_price = pd.DataFrame(prices, columns=["timestamp_ms", "price"])
    df_mcap = pd.DataFrame(market_caps, columns=["timestamp_ms", "market_cap"])
    df_vol = pd.DataFrame(volumes, columns=["timestamp_ms", "total_volume"])

    df = df_price.merge(df_mcap, on="timestamp_ms", how="left")
    df = df.merge(df_vol, on="timestamp_ms", how="left")

    df["date"] = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True).dt.date
    df["coin_id"] = coin_id

    df = df[[
        "date",
        "coin_id",
        "price",
        "market_cap",
        "total_volume",
        "timestamp_ms"
    ]]

    df = df.sort_values("date").reset_index(drop=True)

    return df

# =========================
# 4. Lưu từng coin thành thư mục coin=...
# =========================
OUTPUT_DIR = "crypto_marketcap_2024_03_12"
os.makedirs(OUTPUT_DIR, exist_ok=True)

all_dfs = []

for coin_id in COIN_IDS:
    print(f"Fetching {coin_id}...")

    df = fetch_coin_market_data(coin_id)

    if df is not None:
        coin_folder = os.path.join(OUTPUT_DIR, f"coin={coin_id}")
        os.makedirs(coin_folder, exist_ok=True)

        output_path = os.path.join(coin_folder, "data.csv")
        df.to_csv(output_path, index=False)

        all_dfs.append(df)

        print(f"Saved: {output_path} | rows={len(df)}")

    time.sleep(2)  # tránh bị rate limit

# =========================
# 5. Lưu file tổng hợp
# =========================
if all_dfs:
    combined = pd.concat(all_dfs, ignore_index=True)
    combined.to_csv(os.path.join(OUTPUT_DIR, "all_coins_marketcap_2024_03_12.csv"), index=False)

    print("Done.")
    print(combined.head())
else:
    print("Không tải được dữ liệu nào.")