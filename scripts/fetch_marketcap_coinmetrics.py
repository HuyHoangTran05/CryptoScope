import os
import time
import shutil
import pandas as pd

# =========================================================
# CONFIG
# =========================================================

START_DATE = "2024-03-01"
END_DATE = "2024-12-31"

OUT_DIR = "data/external/marketcap_coinmetrics"

COINMETRICS_MAP = {
    # coin_id trong project của bạn -> symbol trên CoinMetrics
    "binancecoin": "bnb",
    "bitcoin": "btc",
    "cardano": "ada",
    "dogecoin": "doge",
    "ethereum": "eth",
    "litecoin": "ltc",
    "ripple": "xrp",
    "solana": "sol",
    "tether": "usdt",
    "tron": "trx",
    "usd-coin": "usdc",
    "zcash": "zec",

    # Các coin có thể thiếu hoặc không chắc có trên CoinMetrics
    "figure-heloc": "figure-heloc",
    "hyperliquid": "hype",
    "usds": "usds",
    "whitebit": "wbt",
}


# =========================================================
# CLEAN OLD OUTPUT
# =========================================================

def reset_output_dir():
    """
    Xóa sạch thư mục output cũ rồi tạo lại.

    Chỉ xóa:
        data/external/marketcap_coinmetrics/

    Không xóa dữ liệu giá close, silver, gold hoặc các file khác.
    """

    if os.path.exists(OUT_DIR):
        print(f"[CLEAN] Removing old output directory: {OUT_DIR}")
        shutil.rmtree(OUT_DIR)

    os.makedirs(OUT_DIR, exist_ok=True)
    print(f"[CLEAN] Created fresh output directory: {OUT_DIR}")


# =========================================================
# HELPERS
# =========================================================

def count_non_null(df: pd.DataFrame, col: str) -> int:
    """
    Đếm số dòng non-null của một cột.
    Nếu cột không tồn tại thì trả về 0.
    """

    if col not in df.columns:
        return 0

    return int(df[col].notna().sum())


def build_empty_summary(
    coin_id,
    cm_symbol,
    status,
    rows=0,
    selected_column=None,
    has_market_cap_current=False,
    has_market_cap_estimated=False,
    has_supply=False,
    market_cap_type=None,
    market_cap_source=None,
    available_columns=None,
    output_file=None,
    cap_cur_non_null=0,
    cap_est_non_null=0,
    supply_non_null=0,
):
    return {
        "coin_id": coin_id,
        "coinmetrics_symbol": cm_symbol,
        "status": status,
        "rows": rows,
        "selected_column": selected_column,
        "has_market_cap_current": has_market_cap_current,
        "has_market_cap_estimated": has_market_cap_estimated,
        "has_supply": has_supply,
        "market_cap_type": market_cap_type,
        "market_cap_source": market_cap_source,
        "cap_cur_non_null": cap_cur_non_null,
        "cap_est_non_null": cap_est_non_null,
        "supply_non_null": supply_non_null,
        "available_columns": available_columns,
        "output_file": output_file,
    }


# =========================================================
# FETCH ONE COIN
# =========================================================

def fetch_coinmetrics_data(coin_id: str, cm_symbol: str):
    """
    Lấy dữ liệu CoinMetrics cho 1 coin.

    Thứ tự ưu tiên, nhưng chỉ chọn nếu có dữ liệu non-null
    trong giai đoạn START_DATE -> END_DATE:

    1. CapMrktCurUSD
       -> market_cap_current_usd
       -> current market cap theo CoinMetrics.

    2. CapMrktEstUSD
       -> market_cap_estimated_usd
       -> estimated market cap theo CoinMetrics.

    3. SplyCur
       -> circulating_supply
       -> cần merge với close để tính:
          close * circulating_supply.

    4. Nếu không có cả ba hoặc đều null:
       -> missing.
    """

    url = f"https://raw.githubusercontent.com/coinmetrics/data/master/csv/{cm_symbol}.csv"

    print("\n" + "=" * 100)
    print(f"Fetching coin_id: {coin_id}")
    print(f"CoinMetrics symbol: {cm_symbol}")
    print(f"URL: {url}")

    try:
        df = pd.read_csv(url)
    except Exception as e:
        print(f"[ERROR] {coin_id}: cannot read CoinMetrics file")
        print(f"Reason: {e}")

        return None, build_empty_summary(
            coin_id=coin_id,
            cm_symbol=cm_symbol,
            status="MISSING_FILE",
        )

    available_columns = df.columns.tolist()

    if "time" not in df.columns:
        print(f"[ERROR] {coin_id}: missing time column")

        return None, build_empty_summary(
            coin_id=coin_id,
            cm_symbol=cm_symbol,
            status="MISSING_TIME_COLUMN",
            available_columns=", ".join(available_columns),
        )

    # Chuẩn hóa date
    df["date"] = pd.to_datetime(df["time"], errors="coerce").dt.date
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])

    # Lọc giai đoạn 03/2024 -> 12/2024
    df = df[
        (df["date"] >= START_DATE) &
        (df["date"] <= END_DATE)
    ].copy()

    available_columns = df.columns.tolist()

    if df.empty:
        print(f"[WARNING] {coin_id}: no rows in date range {START_DATE} -> {END_DATE}")

        return None, build_empty_summary(
            coin_id=coin_id,
            cm_symbol=cm_symbol,
            status="NO_DATA_IN_DATE_RANGE",
            available_columns=", ".join(available_columns),
        )

    # =====================================================
    # Đếm dữ liệu non-null trong đúng giai đoạn cần lấy
    # =====================================================

    cap_cur_count = count_non_null(df, "CapMrktCurUSD")
    cap_est_count = count_non_null(df, "CapMrktEstUSD")
    supply_count = count_non_null(df, "SplyCur")

    print(f"Rows in date range: {len(df)}")
    print(f"CapMrktCurUSD non-null: {cap_cur_count}")
    print(f"CapMrktEstUSD non-null: {cap_est_count}")
    print(f"SplyCur non-null: {supply_count}")

    # =====================================================
    # Chọn cột theo ưu tiên + phải có dữ liệu thật
    # =====================================================

    if cap_cur_count > 0:
        selected_col = "CapMrktCurUSD"
        output_col = "market_cap_current_usd"
        market_cap_type = "current"
        market_cap_source = "coinmetrics_CapMrktCurUSD"
        status = "HAS_MARKET_CAP_CURRENT"

    elif cap_est_count > 0:
        selected_col = "CapMrktEstUSD"
        output_col = "market_cap_estimated_usd"
        market_cap_type = "estimated"
        market_cap_source = "coinmetrics_CapMrktEstUSD"
        status = "HAS_MARKET_CAP_ESTIMATED"

    elif supply_count > 0:
        selected_col = "SplyCur"
        output_col = "circulating_supply"
        market_cap_type = "need_calculation_from_close_and_supply"
        market_cap_source = "need_close_times_SplyCur"
        status = "HAS_SUPPLY_ONLY"

    else:
        selected_col = None
        output_col = None
        market_cap_type = None
        market_cap_source = None
        status = "MISSING_MARKET_CAP_AND_SUPPLY"

    if selected_col is None:
        print(f"[MISSING] {coin_id}: no usable CapMrktCurUSD, CapMrktEstUSD, or SplyCur")
        print(f"Available columns: {available_columns[:50]}")

        return None, build_empty_summary(
            coin_id=coin_id,
            cm_symbol=cm_symbol,
            status=status,
            selected_column=None,
            has_market_cap_current=False,
            has_market_cap_estimated=False,
            has_supply=False,
            market_cap_type=None,
            market_cap_source=None,
            available_columns=", ".join(available_columns),
            cap_cur_non_null=cap_cur_count,
            cap_est_non_null=cap_est_count,
            supply_non_null=supply_count,
        )

    # =====================================================
    # Build result với schema thống nhất
    # =====================================================

    result = df[["date", selected_col]].copy()

    if selected_col == "CapMrktCurUSD":
        result = result.rename(columns={
            selected_col: "market_cap_current_usd"
        })
        result["market_cap_estimated_usd"] = pd.NA
        result["circulating_supply"] = pd.NA

    elif selected_col == "CapMrktEstUSD":
        result = result.rename(columns={
            selected_col: "market_cap_estimated_usd"
        })
        result["market_cap_current_usd"] = pd.NA
        result["circulating_supply"] = pd.NA

    elif selected_col == "SplyCur":
        result = result.rename(columns={
            selected_col: "circulating_supply"
        })
        result["market_cap_current_usd"] = pd.NA
        result["market_cap_estimated_usd"] = pd.NA

    result["coin_id"] = coin_id
    result["coinmetrics_symbol"] = cm_symbol
    result["market_cap_type"] = market_cap_type
    result["market_cap_source"] = market_cap_source
    result["selected_column"] = selected_col

    result = result[[
        "date",
        "coin_id",
        "coinmetrics_symbol",
        "market_cap_current_usd",
        "market_cap_estimated_usd",
        "circulating_supply",
        "market_cap_type",
        "market_cap_source",
        "selected_column",
    ]]

    # Drop null theo cột được chọn
    result = result.dropna(subset=[output_col])

    if result.empty:
        print(f"[WARNING] {coin_id}: selected {selected_col} but all selected values became null")

        return None, build_empty_summary(
            coin_id=coin_id,
            cm_symbol=cm_symbol,
            status=f"{selected_col}_ALL_NULL_AFTER_FILTER",
            selected_column=selected_col,
            has_market_cap_current=False,
            has_market_cap_estimated=False,
            has_supply=False,
            market_cap_type=market_cap_type,
            market_cap_source=market_cap_source,
            available_columns=", ".join(available_columns),
            cap_cur_non_null=cap_cur_count,
            cap_est_non_null=cap_est_count,
            supply_non_null=supply_count,
        )

    # =====================================================
    # Save per-coin file
    # =====================================================

    if status in ["HAS_MARKET_CAP_CURRENT", "HAS_MARKET_CAP_ESTIMATED"]:
        output_file = os.path.join(OUT_DIR, f"{coin_id}_marketcap.csv")
    else:
        output_file = os.path.join(OUT_DIR, f"{coin_id}_supply.csv")

    result.to_csv(output_file, index=False)

    print(f"[OK] {coin_id}: {status}")
    print(f"Selected column: {selected_col}")
    print(f"Market cap type: {market_cap_type}")
    print(f"Rows saved: {len(result)}")
    print(f"Saved: {output_file}")

    return result, build_empty_summary(
        coin_id=coin_id,
        cm_symbol=cm_symbol,
        status=status,
        rows=len(result),
        selected_column=selected_col,
        has_market_cap_current=selected_col == "CapMrktCurUSD",
        has_market_cap_estimated=selected_col == "CapMrktEstUSD",
        has_supply=selected_col == "SplyCur",
        market_cap_type=market_cap_type,
        market_cap_source=market_cap_source,
        available_columns=", ".join(available_columns),
        output_file=output_file,
        cap_cur_non_null=cap_cur_count,
        cap_est_non_null=cap_est_count,
        supply_non_null=supply_count,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    reset_output_dir()

    all_dataframes = []
    summary_rows = []

    for coin_id, cm_symbol in COINMETRICS_MAP.items():
        coin_df, summary = fetch_coinmetrics_data(coin_id, cm_symbol)

        summary_rows.append(summary)

        if coin_df is not None and not coin_df.empty:
            all_dataframes.append(coin_df)

        # Tránh spam GitHub raw
        time.sleep(1)

    # =====================================================
    # SAVE SUMMARY
    # =====================================================

    summary_df = pd.DataFrame(summary_rows)

    summary_path = os.path.join(
        OUT_DIR,
        "marketcap_supply_summary.csv"
    )

    summary_df.to_csv(summary_path, index=False)

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    display_cols = [
        "coin_id",
        "coinmetrics_symbol",
        "status",
        "rows",
        "selected_column",
        "cap_cur_non_null",
        "cap_est_non_null",
        "supply_non_null",
        "has_market_cap_current",
        "has_market_cap_estimated",
        "has_supply",
        "market_cap_type",
        "market_cap_source",
    ]

    print(summary_df[display_cols])

    print(f"\n[DONE] Saved summary: {summary_path}")

    # =====================================================
    # SAVE COMBINED DATA
    # =====================================================

    if all_dataframes:
        final_df = pd.concat(all_dataframes, ignore_index=True)

        final_path = os.path.join(
            OUT_DIR,
            "all_marketcap_or_supply_2024_03_12.csv"
        )

        final_df.to_csv(final_path, index=False)

        print(f"[DONE] Saved combined data: {final_path}")
        print(f"[DONE] Total rows: {len(final_df)}")

        # =================================================
        # QUICK REPORT
        # =================================================

        print("\n" + "=" * 100)
        print("GROUPED STATUS")
        print("=" * 100)
        print(summary_df["status"].value_counts())

        print("\n" + "=" * 100)
        print("COINS WITH CURRENT MARKET CAP: CapMrktCurUSD")
        print("=" * 100)
        print(
            summary_df.loc[
                summary_df["status"] == "HAS_MARKET_CAP_CURRENT",
                "coin_id"
            ].tolist()
        )

        print("\n" + "=" * 100)
        print("COINS WITH ESTIMATED MARKET CAP: CapMrktEstUSD")
        print("=" * 100)
        print(
            summary_df.loc[
                summary_df["status"] == "HAS_MARKET_CAP_ESTIMATED",
                "coin_id"
            ].tolist()
        )

        print("\n" + "=" * 100)
        print("COINS WITH SUPPLY ONLY: SplyCur")
        print("=" * 100)
        print(
            summary_df.loc[
                summary_df["status"] == "HAS_SUPPLY_ONLY",
                "coin_id"
            ].tolist()
        )

        print("\n" + "=" * 100)
        print("MISSING COINS")
        print("=" * 100)
        print(
            summary_df.loc[
                ~summary_df["status"].isin([
                    "HAS_MARKET_CAP_CURRENT",
                    "HAS_MARKET_CAP_ESTIMATED",
                    "HAS_SUPPLY_ONLY",
                ]),
                "coin_id"
            ].tolist()
        )

    else:
        print("\nKhông lấy được dữ liệu nào từ CoinMetrics.")


if __name__ == "__main__":
    main()