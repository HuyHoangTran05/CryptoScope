import pandas as pd

GOLD_PATH = "gs://bigdata-project-495412-gold/features_daily/features_daily.parquet"

df = pd.read_parquet(GOLD_PATH)

print("Shape:", df.shape)

print("\nColumns:")
print(df.columns.tolist())

print("\nCoin counts:")
print(df["coin_id"].value_counts())

print("\nDate range:")
print(
    df.groupby("coin_id")["date"]
    .agg(["min", "max", "count"])
    .sort_index()
)

print("\nDuplicate coin_id + date:")
print(df.duplicated(subset=["coin_id", "date"]).sum())

print("\nNull rate top 20:")
print(df.isna().mean().sort_values(ascending=False).head(20))

print("\nSample:")
print(df.head(20))