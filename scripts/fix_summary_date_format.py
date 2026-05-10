import pandas as pd

INPUT_FILE = "data/quality_reports/full_coin/full_coin_quality_summary.csv"
OUTPUT_FILE = "data/quality_reports/full_coin/full_coin_quality_summary_fixed.csv"

df = pd.read_csv(INPUT_FILE)

date_cols = ["min_date", "max_date"]

for col in date_cols:
    if col in df.columns:
        df[col] = pd.to_datetime(
            df[col],
            errors="coerce"
        ).dt.strftime("%Y-%m-%d")

df.to_csv(OUTPUT_FILE, index=False)

print(f"Saved fixed file: {OUTPUT_FILE}")
print(df[date_cols].head())