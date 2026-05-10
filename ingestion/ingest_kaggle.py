import argparse
import os
from pathlib import Path

import pandas as pd

from ingestion.utils import (
    ensure_file_exists,
    load_config,
    make_run_id,
    today_utc_date,
    upload_file_to_gcs,
    write_dead_letter,
    write_manifest,
)


def basic_csv_check(file_path: str) -> dict:
    df_head = pd.read_csv(file_path, nrows=5)

    file_size_bytes = os.path.getsize(file_path)

    return {
        "file_name": Path(file_path).name,
        "file_size_bytes": file_size_bytes,
        "columns": list(df_head.columns),
        "sample_rows_checked": len(df_head),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        required=True,
        help="Local path to Kaggle CSV file",
    )
    parser.add_argument(
        "--dataset-name",
        default="kaggle_crypto_historical",
        help="Logical dataset name",
    )
    parser.add_argument("--config", default="configs/config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    bronze_bucket = config["gcs"]["bronze_bucket"]

    run_id = make_run_id("kaggle")
    print(f"Run ID: {run_id}")

    try:
        ensure_file_exists(args.file)

        check_result = basic_csv_check(args.file)
        print("Basic CSV check:")
        print(check_result)

        ingestion_date = today_utc_date()
        source_file_name = Path(args.file).name

        blob_name = (
            f"raw_kaggle/dataset={args.dataset_name}/"
            f"ingestion_date={ingestion_date}/"
            f"{run_id}_{source_file_name}"
        )

        gcs_uri = upload_file_to_gcs(
            bucket_name=bronze_bucket,
            source_file_path=args.file,
            destination_blob_name=blob_name,
            content_type="text/csv",
        )

        manifest_uri = write_manifest(
            bucket_name=bronze_bucket,
            run_id=run_id,
            source="kaggle",
            status="SUCCESS",
            files=[gcs_uri],
            extra={
                "dataset_name": args.dataset_name,
                "csv_check": check_result,
            },
        )

        print("Kaggle ingestion SUCCESS")
        print(f"Raw file: {gcs_uri}")
        print(f"Manifest: {manifest_uri}")

    except Exception as e:
        print(f"Kaggle ingestion FAILED: {e}")

        dead_letter_uri = write_dead_letter(
            bucket_name=bronze_bucket,
            run_id=run_id,
            source="kaggle",
            error_message=str(e),
            payload={
                "file": args.file,
                "dataset_name": args.dataset_name,
            },  
        )

        print(f"Dead-letter written to: {dead_letter_uri}")
        raise


if __name__ == "__main__":
    main()