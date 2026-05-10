import os
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

DATA_DIR = "data/external/full_coin"
REPORT_DIR = "data/quality_reports/full_coin"

os.makedirs(REPORT_DIR, exist_ok=True)

REQUIRED_COLUMNS = [
    "date",
    "Close",
    "High",
    "Low",
    "Open",
    "Volume",
    "market_cap",
]

COLUMN_ALIASES = {
    "Date": "date",
    "DATE": "date",
    "time": "date",
    "Time": "date",

    "close": "Close",
    "Close": "Close",

    "high": "High",
    "High": "High",

    "low": "Low",
    "Low": "Low",

    "open": "Open",
    "Open": "Open",

    "volume": "Volume",
    "Volume": "Volume",

    "Market Cap": "market_cap",
    "Market_Cap": "market_cap",
    "marketcap": "market_cap",
    "MarketCap": "market_cap",
    "market_cap": "market_cap",
}


# =========================================================
# HELPERS
# =========================================================

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {}
    for col in df.columns:
        if col in COLUMN_ALIASES:
            rename_map[col] = COLUMN_ALIASES[col]

    df = df.rename(columns=rename_map)
    return df


def check_one_coin_file(file_path: str):
    coin_name = os.path.basename(file_path).replace(".csv", "")

    print("\n" + "=" * 100)
    print(f"CHECKING COIN: {coin_name}")
    print(f"FILE: {file_path}")
    print("=" * 100)

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"[ERROR] Không đọc được file {coin_name}: {e}")

        return {
            "coin": coin_name,
            "file_path": file_path,
            "status": "READ_ERROR",
            "rows": 0,
            "min_date": None,
            "max_date": None,
            "missing_columns": None,
            "extra_columns": None,
            "missing_dates_count": None,
            "duplicate_dates_count": None,
            "invalid_dates_count": None,
            "null_columns": None,
            "ohlc_invalid_rows": None,
        }

    df = normalize_columns(df)

    print(f"[INFO] Rows: {len(df)}")
    print(f"[INFO] Columns: {df.columns.tolist()}")

    # =====================================================
    # 1. Check columns
    # =====================================================

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    extra_columns = [col for col in df.columns if col not in REQUIRED_COLUMNS]

    if missing_columns:
        print("\n[FAIL] Thiếu cột bắt buộc:")
        for col in missing_columns:
            print(f"  - {col}")
    else:
        print("\n[OK] Không thiếu cột bắt buộc.")

    if extra_columns:
        print("\n[INFO] Có cột phụ:")
        for col in extra_columns:
            print(f"  - {col}")

    if "date" not in df.columns:
        print("\n[STOP] Không có cột date nên không kiểm tra ngày được.")

        return {
            "coin": coin_name,
            "file_path": file_path,
            "status": "MISSING_DATE_COLUMN",
            "rows": len(df),
            "min_date": None,
            "max_date": None,
            "missing_columns": ", ".join(missing_columns),
            "extra_columns": ", ".join(extra_columns),
            "missing_dates_count": None,
            "duplicate_dates_count": None,
            "invalid_dates_count": None,
            "null_columns": None,
            "ohlc_invalid_rows": None,
        }

    # =====================================================
    # 2. Parse date
    # =====================================================

    # Ảnh bạn gửi có dạng 9/11/2017, thường là dd/mm/yyyy
    df["date_parsed"] = pd.to_datetime(
        df["date"],
        errors="coerce",
        dayfirst=True
    )

    invalid_dates = df[df["date_parsed"].isna()]

    if len(invalid_dates) > 0:
        print(f"\n[FAIL] Có {len(invalid_dates)} dòng date không parse được.")
        print(invalid_dates[["date"]].head(20))
    else:
        print("\n[OK] Tất cả date parse được.")

    df = df.dropna(subset=["date_parsed"]).copy()

    if df.empty:
        print("\n[STOP] Sau khi bỏ date lỗi thì file không còn dữ liệu.")

        return {
            "coin": coin_name,
            "file_path": file_path,
            "status": "ALL_DATES_INVALID",
            "rows": 0,
            "min_date": None,
            "max_date": None,
            "missing_columns": ", ".join(missing_columns),
            "extra_columns": ", ".join(extra_columns),
            "missing_dates_count": None,
            "duplicate_dates_count": None,
            "invalid_dates_count": len(invalid_dates),
            "null_columns": None,
            "ohlc_invalid_rows": None,
        }

    df["date_parsed"] = df["date_parsed"].dt.normalize()

    # =====================================================
    # 3. Duplicate dates
    # =====================================================

    duplicate_dates_df = df[df.duplicated(subset=["date_parsed"], keep=False)]
    duplicate_dates_count = duplicate_dates_df["date_parsed"].nunique()

    if duplicate_dates_count > 0:
        print(f"\n[FAIL] Có {duplicate_dates_count} ngày bị trùng.")
        print(
            duplicate_dates_df[["date", "date_parsed"]]
            .sort_values("date_parsed")
            .head(30)
        )
    else:
        print("\n[OK] Không có ngày bị trùng.")

    # =====================================================
    # 4. Missing dates
    # =====================================================

    min_date = df["date_parsed"].min()
    max_date = df["date_parsed"].max()

    full_dates = pd.date_range(min_date, max_date, freq="D")
    existing_dates = pd.to_datetime(df["date_parsed"].unique())
    missing_dates = full_dates.difference(existing_dates)

    print(f"\n[INFO] Min date: {min_date.date()}")
    print(f"[INFO] Max date: {max_date.date()}")
    print(f"[INFO] Expected daily rows: {len(full_dates)}")
    print(f"[INFO] Actual unique dates: {df['date_parsed'].nunique()}")

    if len(missing_dates) > 0:
        print(f"\n[FAIL] Thiếu {len(missing_dates)} ngày trong chuỗi daily.")
        print("Một số ngày thiếu đầu tiên:")
        for d in missing_dates[:30]:
            print(f"  - {d.date()}")
    else:
        print("\n[OK] Không thiếu ngày nào trong khoảng min_date -> max_date.")

    # Save missing dates per coin
    missing_dates_path = os.path.join(REPORT_DIR, f"{coin_name}_missing_dates.csv")
    pd.DataFrame({"missing_date": missing_dates}).to_csv(missing_dates_path, index=False)

    # =====================================================
    # 5. Null values
    # =====================================================

    check_cols = [col for col in REQUIRED_COLUMNS if col in df.columns]

    null_counts = df[check_cols].isna().sum()
    null_cols = null_counts[null_counts > 0]

    print("\n[CHECK] Null values:")
    print(null_counts)

    if len(null_cols) > 0:
        print("\n[FAIL] Có cột bị null:")
        print(null_cols)
    else:
        print("\n[OK] Không có null trong các cột bắt buộc đang tồn tại.")

    # =====================================================
    # 6. Numeric check
    # =====================================================

    numeric_cols = ["Close", "High", "Low", "Open", "Volume", "market_cap"]
    numeric_cols = [col for col in numeric_cols if col in df.columns]

    invalid_numeric_report = {}

    print("\n[CHECK] Numeric columns:")

    for col in numeric_cols:
        before_null = df[col].isna().sum()
        converted = pd.to_numeric(df[col], errors="coerce")
        after_null = converted.isna().sum()

        invalid_count = after_null - before_null
        invalid_numeric_report[col] = int(invalid_count)

        if invalid_count > 0:
            print(f"[FAIL] {col}: có {invalid_count} giá trị không chuyển được sang số")
        else:
            print(f"[OK] {col}: numeric hợp lệ")

        df[col] = converted

    # =====================================================
    # 7. Negative / zero check
    # =====================================================

    print("\n[CHECK] Negative / zero values:")

    for col in numeric_cols:
        neg_count = int((df[col] < 0).sum())
        zero_count = int((df[col] == 0).sum())

        if neg_count > 0:
            print(f"[FAIL] {col}: có {neg_count} giá trị âm")
        else:
            print(f"[OK] {col}: không có giá trị âm")

        if col in ["Close", "High", "Low", "Open", "market_cap"] and zero_count > 0:
            print(f"[WARNING] {col}: có {zero_count} giá trị bằng 0")

    # =====================================================
    # 8. OHLC logic check
    # =====================================================

    ohlc_invalid_rows = 0

    if all(col in df.columns for col in ["Open", "High", "Low", "Close"]):
        invalid_high = df[
            (df["High"] < df["Open"]) |
            (df["High"] < df["Close"]) |
            (df["High"] < df["Low"])
        ]

        invalid_low = df[
            (df["Low"] > df["Open"]) |
            (df["Low"] > df["Close"]) |
            (df["Low"] > df["High"])
        ]

        ohlc_invalid_rows = len(invalid_high) + len(invalid_low)

        if invalid_high.empty:
            print("\n[OK] High hợp lệ.")
        else:
            print(f"\n[FAIL] Có {len(invalid_high)} dòng High không hợp lệ.")
            print(invalid_high[["date", "Open", "High", "Low", "Close"]].head(20))

        if invalid_low.empty:
            print("[OK] Low hợp lệ.")
        else:
            print(f"[FAIL] Có {len(invalid_low)} dòng Low không hợp lệ.")
            print(invalid_low[["date", "Open", "High", "Low", "Close"]].head(20))

    # =====================================================
    # 9. Save cleaned preview / summary
    # =====================================================

    quality_status = "OK"

    if missing_columns:
        quality_status = "FAIL_MISSING_COLUMNS"
    elif len(invalid_dates) > 0:
        quality_status = "FAIL_INVALID_DATES"
    elif duplicate_dates_count > 0:
        quality_status = "FAIL_DUPLICATE_DATES"
    elif len(missing_dates) > 0:
        quality_status = "FAIL_MISSING_DATES"
    elif len(null_cols) > 0:
        quality_status = "FAIL_NULL_VALUES"
    elif ohlc_invalid_rows > 0:
        quality_status = "FAIL_OHLC_LOGIC"

    return {
        "coin": coin_name,
        "file_path": file_path,
        "status": quality_status,
        "rows": len(df),
        "min_date": min_date.date(),
        "max_date": max_date.date(),
        "expected_daily_rows": len(full_dates),
        "actual_unique_dates": df["date_parsed"].nunique(),
        "missing_columns": ", ".join(missing_columns),
        "extra_columns": ", ".join(extra_columns),
        "missing_dates_count": len(missing_dates),
        "duplicate_dates_count": duplicate_dates_count,
        "invalid_dates_count": len(invalid_dates),
        "null_columns": ", ".join(null_cols.index.tolist()),
        "ohlc_invalid_rows": ohlc_invalid_rows,
        "missing_dates_report": missing_dates_path,
    }


def main():
    print(f"[INFO] Checking folder: {DATA_DIR}")

    if not os.path.isdir(DATA_DIR):
        print(f"[ERROR] Không tìm thấy thư mục: {DATA_DIR}")
        return

    csv_files = []

    for file in os.listdir(DATA_DIR):
        if file.lower().endswith(".csv"):
            csv_files.append(os.path.join(DATA_DIR, file))

    csv_files = sorted(csv_files)

    if not csv_files:
        print(f"[ERROR] Không có file CSV trong thư mục: {DATA_DIR}")
        return

    print(f"[INFO] Found {len(csv_files)} CSV files")

    summary_rows = []

    for file_path in csv_files:
        report = check_one_coin_file(file_path)
        summary_rows.append(report)

    summary_df = pd.DataFrame(summary_rows)

    summary_path = os.path.join(REPORT_DIR, "full_coin_quality_summary.csv")
    summary_df.to_csv(summary_path, index=False)

    print("\n" + "=" * 100)
    print("FINAL SUMMARY")
    print("=" * 100)

    display_cols = [
        "coin",
        "status",
        "rows",
        "min_date",
        "max_date",
        "missing_dates_count",
        "duplicate_dates_count",
        "invalid_dates_count",
        "missing_columns",
        "null_columns",
        "ohlc_invalid_rows",
    ]

    print(summary_df[display_cols])

    print(f"\n[DONE] Saved summary report:")
    print(f"  - {summary_path}")

    print("\n[DONE] Missing dates reports saved in:")
    print(f"  - {REPORT_DIR}")


if __name__ == "__main__":
    main()