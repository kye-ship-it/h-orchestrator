"""GCS client for storing and retrieving markdown reports."""

import logging
from datetime import datetime, timedelta

from google.cloud import storage
from google.cloud.exceptions import NotFound

from config import GCP_PROJECT, GCS_BUCKET, GCS_DAILY_PREFIX

logger = logging.getLogger(__name__)


def _get_client() -> storage.Client:
    """Create a GCS client scoped to the project."""
    return storage.Client(project=GCP_PROJECT)


def _get_bucket(client: storage.Client | None = None) -> storage.Bucket:
    """Get the configured GCS bucket."""
    client = client or _get_client()
    return client.bucket(GCS_BUCKET)


def upload_markdown(content: str, path: str) -> str:
    """Upload markdown content to the GCS bucket.

    Returns:
        Full GCS URI (gs://bucket/path).
    """
    bucket = _get_bucket()
    blob = bucket.blob(path)
    blob.upload_from_string(content, content_type="text/markdown; charset=utf-8")

    full_uri = f"gs://{GCS_BUCKET}/{path}"
    logger.info("Uploaded report to %s (%d bytes)", full_uri, len(content.encode("utf-8")))
    return full_uri


def read_markdown(path: str) -> str | None:
    """Read markdown content from the GCS bucket.

    Returns:
        File content as string, or None if the object does not exist.
    """
    bucket = _get_bucket()
    blob = bucket.blob(path)

    try:
        content = blob.download_as_text(encoding="utf-8")
        logger.info("Read %d chars from gs://%s/%s", len(content), GCS_BUCKET, path)
        return content
    except NotFound:
        logger.info("Object not found: gs://%s/%s", GCS_BUCKET, path)
        return None


def list_files(prefix: str) -> list[str]:
    """List all object paths under a prefix in the bucket."""
    client = _get_client()
    bucket = _get_bucket(client)

    blobs = bucket.list_blobs(prefix=prefix)
    paths = sorted(blob.name for blob in blobs)
    logger.info("Listed %d files under prefix '%s'", len(paths), prefix)
    return paths


def _daily_report_path(date_str: str) -> str:
    """Construct the GCS path for a daily report by date."""
    return f"{GCS_DAILY_PREFIX}/{date_str}.md"


def get_previous_day_report(target_date: str) -> str | None:
    """Fetch the previous day's daily report markdown."""
    try:
        current = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        logger.error("Invalid date format: %s (expected YYYY-MM-DD)", target_date)
        return None

    previous = current - timedelta(days=1)
    previous_str = previous.strftime("%Y-%m-%d")
    path = _daily_report_path(previous_str)

    logger.info("Fetching previous day report: %s", path)
    return read_markdown(path)


def store_daily_report(content: str, target_date: str) -> str:
    """Store a daily report in the standard location.

    Returns:
        Full GCS URI of the stored report.
    """
    path = _daily_report_path(target_date)
    return upload_markdown(content, path)
