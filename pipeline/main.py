"""Cloud Function entry point for the H-Orchestrator pipeline."""

import json
import logging
from datetime import datetime, timedelta, timezone

import functions_framework
from zoneinfo import ZoneInfo

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


def _json_response(data: dict, status: int = 200):
    return (
        json.dumps(data, ensure_ascii=False),
        status,
        {"Content-Type": "application/json"},
    )


def _validate_date(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _generate_single_day(date_str: str) -> dict:
    """Generate a daily log for a single date. Returns result dict."""
    raw_rows = fetch_daily_calls(date_str)

    if not raw_rows:
        logger.info("No data for %s", date_str)
        return {"date": date_str, "status": "no_data"}

    records = map_to_call_records(raw_rows)
    metrics = compute_daily_metrics(records)
    previous_report = get_previous_day_report(date_str)
    report_content = generate_daily_report(metrics, records, date_str, previous_report)
    gcs_uri = store_daily_report(report_content, date_str)

    try:
        from config import GCS_DAILY_PREFIX
        report_path = f"{GCS_DAILY_PREFIX}/{date_str}.md"
        file_entry = build_file_index(report_path, report_content)
        add_to_index(file_entry)
    except Exception:
        logger.exception("Embedding index update failed for %s (non-fatal)", date_str)

    return {
        "date": date_str,
        "status": "success",
        "gcs_path": gcs_uri,
        "total_calls": metrics.total_calls,
    }


@functions_framework.http
def generate_daily_log(request):
    """HTTP Cloud Function: generate daily H-Voice log(s).

    Single day:
        GET  ?target_date=2026-03-28
        POST {"target_date": "2026-03-28"}

    Backfill (date range):
        POST {"start_date": "2026-01-01", "end_date": "2026-03-29"}

    Defaults to yesterday if no parameters given.
    """
    try:
        body = request.get_json(silent=True) or {}
        start_date = body.get("start_date")
        end_date = body.get("end_date")

        # --- Backfill mode: start_date + end_date ---
        if start_date and end_date:
            for d in (start_date, end_date):
                if not _validate_date(d):
                    return _json_response({"error": f"Invalid date: {d}"}, 400)

            logger.info("=== Backfill: %s ~ %s ===", start_date, end_date)

            current = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            results = {"success": [], "no_data": [], "failed": []}

            while current <= end:
                ds = current.strftime("%Y-%m-%d")
                try:
                    result = _generate_single_day(ds)
                    if result["status"] == "success":
                        results["success"].append(ds)
                    else:
                        results["no_data"].append(ds)
                except Exception as e:
                    logger.exception("Failed for %s", ds)
                    results["failed"].append({"date": ds, "error": str(e)})
                current += timedelta(days=1)

            logger.info(
                "=== Backfill complete: %d success, %d no_data, %d failed ===",
                len(results["success"]), len(results["no_data"]), len(results["failed"]),
            )
            return _json_response({
                "status": "complete",
                "success": len(results["success"]),
                "no_data": len(results["no_data"]),
                "failed": len(results["failed"]),
                "details": results,
            })

        # --- Single day mode ---
        # Default: yesterday in BRT (America/Sao_Paulo)
        BRT = ZoneInfo("America/Sao_Paulo")
        target_date = (
            body.get("target_date")
            or request.args.get("target_date")
            or (datetime.now(BRT) - timedelta(days=1)).strftime("%Y-%m-%d")
        )

        if not _validate_date(target_date):
            return _json_response({"error": f"Invalid date: {target_date}"}, 400)

        logger.info("=== Single day: %s ===", target_date)
        result = _generate_single_day(target_date)

        return _json_response(result)

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
