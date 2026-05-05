import argparse
import re
from pathlib import Path

import yaml
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window


COIN_NAME_MAP = {
    "binance-coin": "binance-coin",
    "bitcoin": "bitcoin",
    "cardano": "cardano",
    "chainlink": "chainlink",
    "ethereum": "ethereum",
    "litecoin": "litecoin",
    "polkadot-new": "polkadot-new",
    "tether": "tether",
    "usd-coin": "usd-coin",
    "xrp": "xrp",
}


def load_config(config_path: str):
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def infer_coin_from_file(path: str) -> str:
    name = Path(path).name.lower()

    # File trên Bronze có dạng:
    # kaggle_2026-05-05T13-53-24Z_xxxxxxxx_ethereum.csv
    for coin in COIN_NAME_MAP:
        if name.endswith(f"{coin}.csv") or f"_{coin}.csv" in name:
            return COIN_NAME_MAP[coin]

    # fallback: bỏ prefix kaggle_..._ nếu có
    stem = Path(path).stem.lower()
    stem = re.sub(r"^kaggle_.*?_[0-9a-f]{8}_", "", stem)
    return stem


def normalize_column_name(col_name: str) -> str:
    return (
        col_name.strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/config.yaml")
    parser.add_argument(
        "--input",
        default="data/raw/kaggle/*.csv",
        help="Local input CSV glob. Example: data/raw/kaggle/*.csv",
    )
    parser.add_argument(
        "--output",
        default="data/silver/prices_daily",
        help="Local output path for Silver Parquet",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    spark = (
        SparkSession.builder
        .appName("CryptoScope Silver ETL Kaggle Local")
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    input_paths = [str(p) for p in Path(".").glob(args.input)]
    if not input_paths:
        raise FileNotFoundError(f"No CSV files found with pattern: {args.input}")

    print("Input files:")
    for p in input_paths:
        print(f" - {p}")

    all_dfs = []

    for file_path in input_paths:
        coin_id = infer_coin_from_file(file_path)

        df = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "true")
            .csv(file_path)
        )

        # Chuẩn hóa tên cột
        for old_col in df.columns:
            df = df.withColumnRenamed(old_col, normalize_column_name(old_col))

        # Dataset này thường có các cột:
        # date, open, high, low, close, volume, market_cap
        # Nhưng để an toàn, ta map một số tên phổ biến.
        col_map = {
            "date": "date",
            "timestamp": "date",
            "time": "date",
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "price": "close",
            "volume": "volume",
            "market_cap": "market_cap",
            "marketcap": "market_cap",
            "market_capitalization": "market_cap",
        }

        for c in list(df.columns):
            if c in col_map and c != col_map[c]:
                df = df.withColumnRenamed(c, col_map[c])

        required_any = ["date", "close"]
        missing_core = [c for c in required_any if c not in df.columns]
        if missing_core:
            raise ValueError(
                f"File {file_path} missing required columns {missing_core}. "
                f"Available columns: {df.columns}"
            )

        # Thêm cột thiếu nếu dataset không có đủ OHLCV/market_cap
        for c in ["open", "high", "low", "volume", "market_cap"]:
            if c not in df.columns:
                df = df.withColumn(c, F.lit(None).cast("double"))

        df = (
            df
            .withColumn("coin_id", F.lit(coin_id))
            .withColumn("date", F.to_date(F.col("date")))
            .withColumn("open", F.col("open").cast("double"))
            .withColumn("high", F.col("high").cast("double"))
            .withColumn("low", F.col("low").cast("double"))
            .withColumn("close", F.col("close").cast("double"))
            .withColumn("volume", F.col("volume").cast("double"))
            .withColumn("market_cap", F.col("market_cap").cast("double"))
            .withColumn("source", F.lit("kaggle"))
            .withColumn("ingestion_timestamp", F.current_timestamp())
        )

        df = df.select(
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
        )

        all_dfs.append(df)

    combined = all_dfs[0]
    for df in all_dfs[1:]:
        combined = combined.unionByName(df)

    # Loại bỏ bản ghi lỗi cơ bản
    cleaned = (
        combined
        .filter(F.col("date").isNotNull())
        .filter(F.col("close").isNotNull())
        .filter(F.col("close") >= 0)
        .filter((F.col("volume").isNull()) | (F.col("volume") >= 0))
    )

    # Dedup theo coin_id + date, giữ bản ghi mới nhất
    w = Window.partitionBy("coin_id", "date").orderBy(F.col("ingestion_timestamp").desc())

    deduped = (
        cleaned
        .withColumn("rn", F.row_number().over(w))
        .filter(F.col("rn") == 1)
        .drop("rn")
    )

    # Partition columns
    silver = (
        deduped
        .withColumn("year", F.year("date"))
        .withColumn("month", F.format_string("%02d", F.month("date")))
        .withColumn("day", F.format_string("%02d", F.dayofmonth("date")))
    )

    print("Silver schema:")
    silver.printSchema()

    print("Record count:", silver.count())

    print("Sample:")
    silver.orderBy("coin_id", "date").show(20, truncate=False)

    output_path = args.output

    (
        silver
        .write
        .mode("overwrite")
        .partitionBy("year", "month", "day", "coin_id")
        .parquet(output_path)
    )

    print(f"Silver written to local path: {output_path}")

    spark.stop()


if __name__ == "__main__":
    main()