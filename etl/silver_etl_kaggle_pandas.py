import argparse
import re
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd


COINS = [
    "binance-coin",
    "bitcoin",
    "cardano",
    "chainlink",
    "ethereum",
    "litecoin",
    "polkadot-new",
    "tether",
    "usd-coin",
    "xrp",
]


def infer_coin_id(file_path: str) -> str:
    name = Path(file_path).name.lower()

    for coin in COINS:
        if name.endswith(f"{coin}.csv") or f"_{coin}.csv" in name:
            return coin

    stem = Path(file_path).stem.lower()
    stem = re.sub(r"^kaggle_.*?_[0-9a-f]{8}_", "", stem)
    return stem


def normalize_col(col: str) -> str:
    return (
        col.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )


def normalize_dataframe(df: pd.DataFrame, coin_id: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_col(c) for c in df.columns]

    rename_map = {
        "timestamp": "date",
        "time": "date",
        "price": "close",
        "marketcap": "market_cap",
        "market_capitalization": "market_cap",
    }
    df = df.rename(columns=rename_map)

    if "date" not in df.columns:
        raise ValueError(f"Missing required column: date. Columns={list(df.columns)}")

    if "close" not in df.columns:
        raise ValueError(f"Missing required column: close. Columns={list(df.columns)}")

    for c in ["open", "high", "low", "volume", "market_cap"]:
        if c not in df.columns:
            df[c] = pd.NA

    df["coin_id"] = coin_id
    df["date"] = pd.to_datetime(df["date"], errors="coerce", utc=True).dt.date

    for c in ["open", "high", "low", "close", "volume", "market_cap"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["source"] = "kaggle"
    df["ingestion_timestamp"] = datetime.now(timezone.utc)

    df = df[
        [
            "coin_id",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "market_cap",
            "source",
            "ingestion_timestamp",
        ]
    ]

    df = df.dropna(subset=["date", "close"])
    df = df[df["close"] >= 0]
    df = df[(df["volume"].isna()) | (df["volume"] >= 0)]

    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/raw/kaggle")
    parser.add_argument("--output", default="data/silver/prices_daily")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    files = sorted(input_dir.glob("*.csv"))

    if not files:
        raise FileNotFoundError(f"No CSV files found in {input_dir}")

    dfs = []

    for file in files:
        coin_id = infer_coin_id(str(file))
        print(f"Reading {file} -> coin_id={coin_id}")

        df = pd.read_csv(file)
        df = normalize_dataframe(df, coin_id)
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)

    combined = combined.sort_values(
        ["coin_id", "date", "ingestion_timestamp"],
        ascending=[True, True, False],
    )

    combined = combined.drop_duplicates(
        subset=["coin_id", "date"],
        keep="first",
    )

    combined["date"] = pd.to_datetime(combined["date"])
    combined["year"] = combined["date"].dt.year
    combined["month"] = combined["date"].dt.month.astype(str).str.zfill(2)
    combined["day"] = combined["date"].dt.day.astype(str).str.zfill(2)
    combined["date"] = combined["date"].dt.date

    print("Record count:", len(combined))
    print("Columns:", list(combined.columns))
    print(combined.head(20))

    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / "prices_daily.parquet"

    combined.to_parquet(
        output_file,
        index=False,
        engine="pyarrow",
    )

    print(f"Silver Parquet written to: {output_file}")


if __name__ == "__main__":
    main()