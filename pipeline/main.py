"""Cloud Function entry point for the H-Orchestrator pipeline."""

import json
import logging
from datetime import datetime, timedelta, timezone

import functions_framework

from bq_client import fetch_daily_calls
from mapper import map_to_call_records, compute_daily_metrics
from gemini_client import generate_daily_report
from gcs_client import get_previous_day_report, store_daily_report
from embedding_client import build_file_index
from search_index import add_to_index, rebuild_index

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _resolve_target_date(request) -> str:
    """Extract target_date from request, defaulting to yesterday (UTC)."""
    try:
        body = request.get_json(silent=True) or {}
        if "target_date" in body:
            return body["target_date"]
    except Exception:
        pass

    target_date = request.args.get("target_date")
    if target_date:
        return target_date

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _validate_date(date_str: str) -> bool:
    """Validate that date_str is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _json_response(data: dict, status: int = 200):
    return (
        json.dumps(data, ensure_ascii=False),
        status,
        {"Content-Type": "application/json"},
    )


@functions_framework.http
def generate_daily_log(request):
    """HTTP Cloud Function: generate and store a daily H-Voice log.

    Accepts GET or POST with optional `target_date` parameter (YYYY-MM-DD).
    Defaults to yesterday if not specified.
    """
    try:
        target_date = _resolve_target_date(request)

        if not _validate_date(target_date):
            return _json_response(
                {"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."},
                400,
            )

        logger.info("=== Starting daily log generation for %s ===", target_date)

        # Step 1: Fetch raw call data from BigQuery (3-table JOIN).
        logger.info("Step 1: Fetching call data from BigQuery...")
        raw_rows = fetch_daily_calls(target_date)

        if not raw_rows:
            logger.warning("No call records found for %s", target_date)
            return _json_response({
                "status": "no_data",
                "date": target_date,
                "message": f"No H-Voice call records found for {target_date}.",
            })

        # Step 2: Map to CallRecords and compute metrics.
        logger.info("Step 2: Mapping %d rows to CallRecords...", len(raw_rows))
        records = map_to_call_records(raw_rows)
        metrics = compute_daily_metrics(records)

        logger.info(
            "Metrics: total=%d, connected=%d, accepted=%d, qualified=%d, consent=%d",
            metrics.total_calls,
            metrics.connected_count,
            metrics.accepted_count,
            metrics.qualified_count,
            metrics.consent_count,
        )

        # Step 3: Get previous day report for delta comparison.
        logger.info("Step 3: Fetching previous day report...")
        previous_report = get_previous_day_report(target_date)

        # Step 4: Generate report via Gemini.
        logger.info("Step 4: Generating report via Gemini...")
        report_content = generate_daily_report(metrics, records, target_date, previous_report)

        # Step 5: Store in GCS.
        logger.info("Step 5: Storing report in GCS...")
        gcs_uri = store_daily_report(report_content, target_date)

        # Step 6: Update semantic search index.
        logger.info("Step 6: Updating embedding index...")
        try:
            from config import GCS_DAILY_PREFIX

            report_path = f"{GCS_DAILY_PREFIX}/{target_date}.md"
            file_entry = build_file_index(report_path, report_content)
            add_to_index(file_entry)
            logger.info("Embedding index updated for %s", report_path)
        except Exception:
            logger.exception("Failed to update embedding index (non-fatal)")

        logger.info("=== Daily log generation complete: %s ===", gcs_uri)

        return _json_response({
            "status": "success",
            "date": target_date,
            "gcs_path": gcs_uri,
            "metrics": {
                "total_calls": metrics.total_calls,
                "connected_count": metrics.connected_count,
                "connected_rate": metrics.connected_rate,
                "accepted_count": metrics.accepted_count,
                "accepted_rate": metrics.accepted_rate,
                "qualified_count": metrics.qualified_count,
                "qualified_rate": metrics.qualified_rate,
                "consent_count": metrics.consent_count,
                "consent_rate": metrics.consent_rate,
                "testdrive_count": metrics.testdrive_count,
                "anomalies": metrics.anomalies,
            },
        })

    except Exception as e:
        logger.exception("Failed to generate daily log")
        return _json_response(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            500,
        )


@functions_framework.http
def rebuild_search_index(request):
    """HTTP Cloud Function: rebuild the full semantic search embedding index."""
    try:
        logger.info("=== Starting full search index rebuild ===")
        index = rebuild_index()
        logger.info("=== Search index rebuild complete: %d entries ===", len(index))

        return _json_response({
            "status": "success",
            "entries": len(index),
            "message": f"Search index rebuilt with {len(index)} file entries.",
        })

    except Exception as e:
        logger.exception("Failed to rebuild search index")
        return _json_response(
            {"status": "error", "error": str(e), "error_type": type(e).__name__},
            500,
        )
