import os
import pandas as pd

# =========================================================
# CONFIG
# =========================================================

FULL_COIN_DIR = "data/external/full_coin"
FULL_COIN_OUTPUT_DIR = "data/external/full_coin_fixed"

QUALITY_REPORT_PATH = "data/quality_reports/full_coin/full_coin_quality_summary.csv"
QUALITY_REPORT_OUTPUT_PATH = "data/quality_reports/full_coin/full_coin_quality_summary_fixed.csv"

os.makedirs(FULL_COIN_OUTPUT_DIR, exist_ok=True)

# Các tên cột có khả năng là date trong các bảng
DATE_COLUMNS_CANDIDATES = [
    "date",
    "Date",
    "DATE",
    "time",
    "Time",
    "min_date",
    "max_date",
    "missing_date",
]


# =========================================================
# HELPERS
# =========================================================

def fix_date_column(series: pd.Series) -> pd.Series:
    """
    Chuyển cột date về chuẩn yyyy-mm-dd.

    Dữ liệu coin của bạn đang có dạng dd/mm/yyyy:
        9/11/2017  -> 2017-11-09
        1/12/2017  -> 2017-12-01

    Nên dùng dayfirst=True.
    """

    parsed = pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True
    )

    return parsed.dt.strftime("%Y-%m-%d")


def fix_one_csv(input_path: str, output_path: str):
    print("\n" + "=" * 80)
    print(f"Fixing file: {input_path}")

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        print(f"[ERROR] Cannot read file: {e}")
        return

    fixed_cols = []

    for col in df.columns:
        if col in DATE_COLUMNS_CANDIDATES:
            before_sample = df[col].head(5).tolist()

            df[col] = fix_date_column(df[col])

            after_sample = df[col].head(5).tolist()

            fixed_cols.append(col)

            print(f"[OK] Fixed date column: {col}")
            print(f"     Before: {before_sample}")
            print(f"     After : {after_sample}")

    if not fixed_cols:
        print("[INFO] No date columns found.")

    df.to_csv(output_path, index=False)

    print(f"[DONE] Saved: {output_path}")


# =========================================================
# FIX FULL COIN FILES
# =========================================================

def fix_full_coin_files():
    if not os.path.isdir(FULL_COIN_DIR):
        print(f"[ERROR] Folder not found: {FULL_COIN_DIR}")
        return

    csv_files = [
        f for f in os.listdir(FULL_COIN_DIR)
        if f.lower().endswith(".csv")
    ]

    if not csv_files:
        print(f"[ERROR] No CSV files found in: {FULL_COIN_DIR}")
        return

    print(f"[INFO] Found {len(csv_files)} coin CSV files")

    for file_name in sorted(csv_files):
        input_path = os.path.join(FULL_COIN_DIR, file_name)
        output_path = os.path.join(FULL_COIN_OUTPUT_DIR, file_name)

        fix_one_csv(input_path, output_path)


# =========================================================
# FIX QUALITY SUMMARY
# =========================================================

def fix_quality_report():
    if not os.path.exists(QUALITY_REPORT_PATH):
        print(f"\n[INFO] Quality report not found, skip: {QUALITY_REPORT_PATH}")
        return

    fix_one_csv(
        QUALITY_REPORT_PATH,
        QUALITY_REPORT_OUTPUT_PATH
    )


# =========================================================
# MAIN
# =========================================================

def main():
    print("[START] Fixing all date formats to yyyy-mm-dd")

    fix_full_coin_files()
    fix_quality_report()

    print("\n[DONE] All fixed files created.")
    print(f"Coin files output folder: {FULL_COIN_OUTPUT_DIR}")
    print(f"Quality report output file: {QUALITY_REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()