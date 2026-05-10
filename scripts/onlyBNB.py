import pandas as pd

url = "https://raw.githubusercontent.com/coinmetrics/data/master/csv/bnb.csv"
df = pd.read_csv(url)

print(df.columns.tolist())
print(df.head())
print(df.tail())
df["date"] = pd.to_datetime(df["time"])

sub = df[
    (df["date"] >= "2024-03-01") &
    (df["date"] <= "2024-12-31")
]

for col in ["CapMrktCurUSD", "CapMrktEstUSD", "SplyCur", "ReferenceRateUSD"]:
    if col in sub.columns:
        print(col, "non-null:", sub[col].notna().sum())