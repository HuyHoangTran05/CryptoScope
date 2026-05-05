import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from google.cloud import secretmanager, storage


def load_config(config_path: str = "configs/config.yaml") -> Dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_str() -> str:
    return utc_now().strftime("%Y-%m-%dT%H-%M-%SZ")


def today_utc_date() -> str:
    return utc_now().strftime("%Y-%m-%d")


def make_run_id(prefix: str) -> str:
    return f"{prefix}_{utc_now_str()}_{uuid.uuid4().hex[:8]}"


def get_secret(project_id: str, secret_name: str, version: str = "latest") -> str:
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_name}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8").strip()


def upload_text_to_gcs(
    bucket_name: str,
    destination_blob_name: str,
    text: str,
    content_type: str = "application/json",
) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_string(text, content_type=content_type)
    return f"gs://{bucket_name}/{destination_blob_name}"


def upload_file_to_gcs(
    bucket_name: str,
    source_file_path: str,
    destination_blob_name: str,
    content_type: Optional[str] = None,
) -> str:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_path, content_type=content_type)
    return f"gs://{bucket_name}/{destination_blob_name}"


def write_manifest(
    bucket_name: str,
    run_id: str,
    source: str,
    status: str,
    files: list,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    manifest = {
        "run_id": run_id,
        "source": source,
        "status": status,
        "created_at_utc": utc_now().isoformat(),
        "files": files,
        "extra": extra or {},
    }

    blob_name = f"manifest/ingestion_date={today_utc_date()}/{run_id}.json"

    return upload_text_to_gcs(
        bucket_name=bucket_name,
        destination_blob_name=blob_name,
        text=json.dumps(manifest, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def write_dead_letter(
    bucket_name: str,
    run_id: str,
    source: str,
    error_message: str,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    record = {
        "run_id": run_id,
        "source": source,
        "error_message": error_message,
        "payload": payload or {},
        "created_at_utc": utc_now().isoformat(),
    }

    blob_name = f"dead_letter/ingestion_date={today_utc_date()}/{run_id}.json"

    return upload_text_to_gcs(
        bucket_name=bucket_name,
        destination_blob_name=blob_name,
        text=json.dumps(record, ensure_ascii=False, indent=2),
        content_type="application/json",
    )


def sleep_with_backoff(attempt: int) -> None:
    delays = [5, 30, 120]
    delay = delays[min(attempt, len(delays) - 1)]
    print(f"Sleeping {delay}s before retry...")
    time.sleep(delay)


def ensure_file_exists(path: str) -> None:
    if not Path(path).exists():
        raise FileNotFoundError(f"File not found: {path}")