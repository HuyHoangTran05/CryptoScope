import argparse
import numpy as np
import pandas as pd


def add_features_for_coin(group: pd.DataFrame) -> pd.DataFrame:
    group = group.sort_values("date").copy()

    # Basic returns
    group["daily_return"] = group["close"].pct_change()
    group["log_return"] = np.log(group["close"] / group["close"].shift(1))

    # Rolling volatility
    group["volatility_7d"] = group["log_return"].rolling(window=7, min_periods=3).std()
    group["volatility_14d"] = group["log_return"].rolling(window=14, min_periods=5).std()
    group["volatility_30d"] = group["log_return"].rolling(window=30, min_periods=10).std()

    # Momentum
    group["momentum_7d"] = group["close"] / group["close"].shift(7) - 1
    group["momentum_14d"] = group["close"] / group["close"].shift(14) - 1
    group["momentum_30d"] = group["close"] / group["close"].shift(30) - 1

    # Moving averages
    group["sma_7"] = group["close"].rolling(window=7, min_periods=3).mean()
    group["sma_14"] = group["close"].rolling(window=14, min_periods=5).mean()
    group["sma_30"] = group["close"].rolling(window=30, min_periods=10).mean()

    group["ema_7"] = group["close"].ewm(span=7, adjust=False).mean()
    group["ema_14"] = group["close"].ewm(span=14, adjust=False).mean()
    group["ema_30"] = group["close"].ewm(span=30, adjust=False).mean()

    # Drawdown
    rolling_max = group["close"].rolling(window=30, min_periods=10).max()
    group["drawdown_30d"] = (group["close"] - rolling_max) / rolling_max

    # Volume feature
    group["volume_change_1d"] = group["volume"].pct_change()
    group["volume_zscore_30d"] = (
        (group["volume"] - group["volume"].rolling(window=30, min_periods=10).mean())
        / group["volume"].rolling(window=30, min_periods=10).std()
    )

    # Simple trend signals
    group["price_above_sma_30"] = group["close"] > group["sma_30"]
    group["sma_7_above_sma_30"] = group["sma_7"] > group["sma_30"]

    return group


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="gs://bigdata-project-495412-silver/prices_daily/prices_daily.parquet",
    )
    parser.add_argument(
        "--output",
        default="gs://bigdata-project-495412-gold/features_daily/features_daily.parquet",
    )
    args = parser.parse_args()

    print(f"Reading Silver data from: {args.input}")
    df = pd.read_parquet(args.input)

    print("Silver shape:", df.shape)
    print("Silver columns:", df.columns.tolist())

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["coin_id", "date"])

    feature_df = (
        df.groupby("coin_id", group_keys=False)
        .apply(add_features_for_coin)
        .reset_index(drop=True)
    )

    # Clean inf values
    feature_df = feature_df.replace([np.inf, -np.inf], np.nan)

    # Add metadata
    feature_df["feature_version"] = "v1"
    feature_df["feature_created_at"] = pd.Timestamp.utcnow()

    print("Gold feature shape:", feature_df.shape)
    print("Gold feature columns:")
    print(feature_df.columns.tolist())

    print("\nSample:")
    print(feature_df.head(20))

    print("\nNull rate top 20:")
    print(feature_df.isna().mean().sort_values(ascending=False).head(20))

    print("\nDuplicate coin_id + date:")
    print(feature_df.duplicated(subset=["coin_id", "date"]).sum())

    print(f"Writing Gold features to: {args.output}")
    feature_df.to_parquet(args.output, index=False, engine="pyarrow")

    print("Gold feature engineering SUCCESS")


if __name__ == "__main__":
    main()