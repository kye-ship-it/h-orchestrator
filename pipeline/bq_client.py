"""BigQuery client for querying H-Voice call data from 3 ODS tables."""

import logging
from typing import Any

from google.cloud import bigquery

from config import (
    BQ_ANALYSIS_TABLE,
    BQ_LEAD_TABLE,
    BQ_META_TABLE,
    GCP_PROJECT,
)

logger = logging.getLogger(__name__)


def _get_client() -> bigquery.Client:
    """Create a BigQuery client scoped to the project."""
    return bigquery.Client(project=GCP_PROJECT)


def _build_daily_query() -> str:
    """Build the JOIN query across ODS meta, analysis, and lead tables.

    ODS views already handle dedup, type casting, and timestamp parsing,
    so this query is a straightforward 3-table JOIN.
    """
    return f"""
SELECT
  m.call_id,
  m.recording_url,
  m.call_created_at,
  m.call_status,
  m.call_duration,
  m.call_ended_by,
  m.scenario_version,
  m.variant,
  m.`from` AS from_number,
  m.submitted_at,
  m.lead_id,
  m.first_name,
  m.last_name,
  m.phone,
  m.email,
  m.zip_code,
  m.first_dealer_id,
  m.first_dealer_name,
  m.second_dealer_id,
  m.second_dealer_name,
  m.third_dealer_id,
  m.third_dealer_name,
  m.channel,
  m.model_of_interest,
  m.script_en,
  m.summary,
  -- Analysis fields
  a.voicemail,
  a.hung_up,
  a.type AS call_type,
  a.trim,
  a.dealer_consent,
  a.timeframe,
  a.payment_method,
  a.trade_in,
  a.test_drive_interest,
  a.test_drive_slot,
  a.preferred_contact_channel,
  a.dealer_selected,
  a.dealer_selected_id,
  a.recommendation,
  a.validity,
  -- Lead fields
  l.version AS lead_version,
  l.model_of_interest AS lead_model,
  l.`1st_dealer_name` AS lead_dealer_name,
  l.failed_message
FROM `{BQ_META_TABLE}` m
LEFT JOIN `{BQ_ANALYSIS_TABLE}` a ON m.call_id = a.call_id
LEFT JOIN `{BQ_LEAD_TABLE}` l ON SAFE_CAST(m.lead_id AS STRING) = l.lead_id
WHERE DATE(m.call_created_at, 'America/Sao_Paulo') = @target_date
ORDER BY m.call_created_at ASC
"""


def fetch_daily_calls(target_date: str) -> list[dict[str, Any]]:
    """Fetch all H-Voice call records for a given date.

    Joins ODS meta, analysis, and lead tables.

    Args:
        target_date: Date string in YYYY-MM-DD format.

    Returns:
        List of merged row dicts from BigQuery.
    """
    client = _get_client()
    query = _build_daily_query()

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
        ]
    )

    logger.info("Fetching daily calls for %s (3-table ODS JOIN)", target_date)
    rows = client.query(query, job_config=job_config).result()

    results = [dict(row) for row in rows]
    logger.info("Fetched %d call records for %s", len(results), target_date)
    return results


def fetch_date_range_calls(
    start_date: str, end_date: str
) -> list[dict[str, Any]]:
    """Fetch call records for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format (inclusive).
        end_date: End date in YYYY-MM-DD format (inclusive).

    Returns:
        List of merged row dicts.
    """
    client = _get_client()
    base_query = _build_daily_query()
    query = base_query.replace(
        "WHERE DATE(m.call_created_at, 'America/Sao_Paulo') = @target_date",
        "WHERE DATE(m.call_created_at, 'America/Sao_Paulo') BETWEEN @start_date AND @end_date",
    )

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date),
        ]
    )

    logger.info("Fetching calls for %s ~ %s", start_date, end_date)
    rows = client.query(query, job_config=job_config).result()

    results = [dict(row) for row in rows]
    logger.info("Fetched %d call records for %s ~ %s", len(results), start_date, end_date)
    return results
