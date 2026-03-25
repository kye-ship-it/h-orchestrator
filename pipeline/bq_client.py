"""BigQuery client for querying H-Voice call data."""

import logging
from typing import Any

from google.cloud import bigquery

from pipeline.config import GCP_PROJECT, BQ_DATASET, BQ_TABLE_PREFIX

logger = logging.getLogger(__name__)


def _get_client() -> bigquery.Client:
    """Create a BigQuery client scoped to the project."""
    return bigquery.Client(project=GCP_PROJECT)


def discover_hvoice_tables(client: bigquery.Client | None = None) -> list[dict[str, str]]:
    """Discover tables containing 'hvoice' in their name across all datasets.

    Returns a list of dicts with keys: dataset_id, table_id, full_table_id.
    Uses INFORMATION_SCHEMA to avoid needing pre-configured dataset/table names.
    """
    client = client or _get_client()

    if BQ_DATASET:
        # If dataset is configured, search only within it.
        query = """
            SELECT table_catalog, table_schema, table_name
            FROM `{project}.{dataset}.INFORMATION_SCHEMA.TABLES`
            WHERE LOWER(table_name) LIKE @table_pattern
            ORDER BY table_name
        """.format(project=GCP_PROJECT, dataset=BQ_DATASET)
    else:
        # Search across all datasets the service account can access.
        # We query each dataset's INFORMATION_SCHEMA via a region-level view.
        query = """
            SELECT table_catalog, table_schema, table_name
            FROM `region-us`.INFORMATION_SCHEMA.TABLES
            WHERE LOWER(table_name) LIKE @table_pattern
            ORDER BY table_schema, table_name
        """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter(
                "table_pattern", "STRING", f"%{BQ_TABLE_PREFIX}%"
            ),
        ]
    )

    logger.info("Discovering hvoice tables (dataset=%s)", BQ_DATASET or "all")
    results = client.query(query, job_config=job_config).result()

    tables = []
    for row in results:
        tables.append(
            {
                "dataset_id": row.table_schema,
                "table_id": row.table_name,
                "full_table_id": f"{row.table_catalog}.{row.table_schema}.{row.table_name}",
            }
        )

    logger.info("Discovered %d hvoice table(s): %s", len(tables), tables)
    return tables


def _resolve_table(client: bigquery.Client) -> str:
    """Resolve the fully qualified hvoice table name.

    Uses BQ_DATASET + BQ_TABLE_PREFIX if configured, otherwise discovers
    via INFORMATION_SCHEMA. Raises if no table or multiple ambiguous tables found.
    """
    tables = discover_hvoice_tables(client)

    if not tables:
        raise RuntimeError(
            f"No BigQuery tables matching '{BQ_TABLE_PREFIX}' found. "
            "Check BQ_DATASET configuration and service account permissions."
        )

    if len(tables) == 1:
        return tables[0]["full_table_id"]

    # Multiple tables: prefer the one whose name most closely matches the prefix.
    exact = [t for t in tables if t["table_id"].lower() == BQ_TABLE_PREFIX.lower()]
    if exact:
        return exact[0]["full_table_id"]

    # If still ambiguous, log all and pick the first alphabetically.
    logger.warning(
        "Multiple hvoice tables found: %s. Using first match: %s",
        [t["full_table_id"] for t in tables],
        tables[0]["full_table_id"],
    )
    return tables[0]["full_table_id"]


def fetch_daily_calls(target_date: str) -> list[dict[str, Any]]:
    """Fetch all H-Voice call records for a given date.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        List of row dicts from BigQuery.

    Raises:
        RuntimeError: If no hvoice table can be resolved.
        google.api_core.exceptions.GoogleAPIError: On BQ query failures.
    """
    client = _get_client()
    table_id = _resolve_table(client)

    logger.info("Fetching daily calls for %s from %s", target_date, table_id)

    # Use parameterized query to prevent injection.
    # We cast the date column to DATE for safe comparison.
    # The query selects all columns; downstream mapper handles field extraction.
    query = f"""
        SELECT *
        FROM `{table_id}`
        WHERE DATE(timestamp) = @target_date
        ORDER BY timestamp ASC
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
        ]
    )

    rows = client.query(query, job_config=job_config).result()

    results = [dict(row) for row in rows]
    logger.info("Fetched %d call records for %s", len(results), target_date)
    return results
