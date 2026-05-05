import argparse
import json
from typing import Dict, List

import requests

from ingestion.utils import (
    get_secret,
    load_config,
    make_run_id,
    sleep_with_backoff,
    today_utc_date,
    upload_text_to_gcs,
    write_dead_letter,
    write_manifest,
)


COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"


def fetch_top_coins(
    api_key: str,
    vs_currency: str = "usd",
    top_n: int = 10,
    max_retries: int = 3,
) -> List[Dict]:
    headers = {
        "x-cg-demo-api-key": api_key,
    }

    params = {
        "vs_currency": vs_currency,
        "order": "market_cap_desc",
        "per_page": top_n,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h",
    }

    consecutive_429 = 0

    for attempt in range(max_retries + 1):
        response = requests.get(
            COINGECKO_MARKETS_URL,
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            consecutive_429 += 1
            print(f"CoinGecko rate limit 429. consecutive_429={consecutive_429}")

            if consecutive_429 >= 3:
                raise RuntimeError("Circuit breaker triggered: >3 consecutive 429 errors")

            sleep_with_backoff(attempt)
            continue

        if response.status_code in [500, 502, 503, 504]:
            print(f"Temporary server error {response.status_code}: {response.text[:200]}")
            sleep_with_backoff(attempt)
            continue

        raise RuntimeError(
            f"CoinGecko request failed. status={response.status_code}, body={response.text[:500]}"
        )

    raise RuntimeError("CoinGecko request failed after max retries")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)

    project_id = config["project_id"]
    bronze_bucket = config["gcs"]["bronze_bucket"]
    secret_name = config["coingecko"]["secret_name"]
    top_n = int(config["coingecko"].get("top_n_coins", 10))
    vs_currency = config["coingecko"].get("vs_currency", "usd")

    run_id = make_run_id("coingecko")
    print(f"Run ID: {run_id}")

    try:
        api_key = get_secret(project_id, secret_name)
        data = fetch_top_coins(
            api_key=api_key,
            vs_currency=vs_currency,
            top_n=top_n,
        )

        ingestion_date = today_utc_date()
        blob_name = (
            f"raw_api/source=coingecko/"
            f"ingestion_date={ingestion_date}/"
            f"{run_id}.json"
        )

        payload = {
            "run_id": run_id,
            "source": "coingecko",
            "ingestion_date": ingestion_date,
            "top_n": top_n,
            "vs_currency": vs_currency,
            "records": data,
        }

        gcs_uri = upload_text_to_gcs(
            bucket_name=bronze_bucket,
            destination_blob_name=blob_name,
            text=json.dumps(payload, ensure_ascii=False, indent=2),
            content_type="application/json",
        )

        manifest_uri = write_manifest(
            bucket_name=bronze_bucket,
            run_id=run_id,
            source="coingecko",
            status="SUCCESS",
            files=[gcs_uri],
            extra={
                "top_n": top_n,
                "vs_currency": vs_currency,
                "record_count": len(data),
            },
        )

        print("CoinGecko ingestion SUCCESS")
        print(f"Raw file: {gcs_uri}")
        print(f"Manifest: {manifest_uri}")

    except Exception as e:
        print(f"CoinGecko ingestion FAILED: {e}")

        dead_letter_uri = write_dead_letter(
            bucket_name=bronze_bucket,
            run_id=run_id,
            source="coingecko",
            error_message=str(e),
            payload={"top_n": top_n, "vs_currency": vs_currency},
        )

        print(f"Dead-letter written to: {dead_letter_uri}")
        raise


if __name__ == "__main__":
    main()