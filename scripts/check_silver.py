import pandas as pd

SILVER_PATH = "gs://bigdata-project-495412-silver/prices_daily/prices_daily.parquet"

df = pd.read_parquet(SILVER_PATH)

print("Shape:", df.shape)
print("\nColumns:")
print(df.columns.tolist())

print("\nCoin counts:")
print(df["coin_id"].value_counts())

print("\nDate range by coin:")
print(
    df.groupby("coin_id")["date"]
    .agg(["min", "max", "count"])
    .sort_index()
)

print("\nNull rate:")
print(df.isna().mean().sort_values(ascending=False))

print("\nDuplicate coin_id + date:")
print(df.duplicated(subset=["coin_id", "date"]).sum())

print("\nSample:")
print(df.head(20))