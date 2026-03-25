"""Cloud Function entry point for the H-Orchestrator pipeline."""

import json
import logging
from datetime import datetime, timedelta, timezone

import functions_framework

from pipeline.bq_client import fetch_daily_calls
from pipeline.mapper import map_to_sessions, compute_daily_metrics
from pipeline.gemini_client import generate_daily_report
from pipeline.gcs_client import get_previous_day_report, store_daily_report
from pipeline.embedding_client import build_file_index
from pipeline.search_index import add_to_index, rebuild_index

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


def _resolve_target_date(request) -> str:
    """Extract target_date from request, defaulting to yesterday (UTC)."""
    # Try JSON body first.
    try:
        body = request.get_json(silent=True) or {}
        if "target_date" in body:
            return body["target_date"]
    except Exception:
        pass

    # Try query parameter.
    target_date = request.args.get("target_date")
    if target_date:
        return target_date

    # Default to yesterday UTC.
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")


def _validate_date(date_str: str) -> bool:
    """Validate that date_str is in YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


@functions_framework.http
def generate_daily_log(request):
    """HTTP Cloud Function: generate and store a daily H-Voice log.

    Accepts GET or POST with optional `target_date` parameter (YYYY-MM-DD).
    Defaults to yesterday if not specified.

    Steps:
        1. Resolve target date
        2. Fetch call records from BigQuery
        3. Map to sessions and compute metrics
        4. Retrieve previous day's report for comparison
        5. Generate report via Gemini
        6. Store report in GCS

    Returns:
        JSON response with status, date, path, and summary metrics.
    """
    try:
        target_date = _resolve_target_date(request)

        if not _validate_date(target_date):
            return (
                json.dumps({"error": f"Invalid date format: {target_date}. Use YYYY-MM-DD."}),
                400,
                {"Content-Type": "application/json"},
            )

        logger.info("=== Starting daily log generation for %s ===", target_date)

        # Step 1: Fetch raw call data from BigQuery.
        logger.info("Step 1: Fetching call data from BigQuery...")
        raw_rows = fetch_daily_calls(target_date)

        if not raw_rows:
            logger.warning("No call records found for %s", target_date)
            return (
                json.dumps({
                    "status": "no_data",
                    "date": target_date,
                    "message": f"No H-Voice call records found for {target_date}.",
                }),
                200,
                {"Content-Type": "application/json"},
            )

        # Step 2: Map to sessions and compute metrics.
        logger.info("Step 2: Mapping %d rows to sessions...", len(raw_rows))
        sessions = map_to_sessions(raw_rows)
        metrics = compute_daily_metrics(sessions)

        logger.info(
            "Metrics: total=%d, connected=%d, conn_rate=%.1f%%, bant=%.1f%%, transfer=%.1f%%",
            metrics.total_calls,
            metrics.connected_calls,
            metrics.connection_rate,
            metrics.bant_completion_rate,
            metrics.transfer_rate,
        )

        # Step 3: Get previous day report for delta comparison.
        logger.info("Step 3: Fetching previous day report...")
        previous_report = get_previous_day_report(target_date)

        # Step 4: Generate report via Gemini.
        logger.info("Step 4: Generating report via Gemini...")
        report_content = generate_daily_report(metrics, sessions, target_date, previous_report)

        # Step 5: Store in GCS.
        logger.info("Step 5: Storing report in GCS...")
        gcs_uri = store_daily_report(report_content, target_date)

        # Step 6: Update semantic search index.
        logger.info("Step 6: Updating embedding index...")
        try:
            from pipeline.config import GCS_DAILY_PREFIX

            report_path = f"{GCS_DAILY_PREFIX}/{target_date}.md"
            file_entry = build_file_index(report_path, report_content)
            add_to_index(file_entry)
            logger.info("Embedding index updated for %s", report_path)
        except Exception:
            logger.exception("Failed to update embedding index (non-fatal)")

        logger.info("=== Daily log generation complete: %s ===", gcs_uri)

        return (
            json.dumps({
                "status": "success",
                "date": target_date,
                "gcs_path": gcs_uri,
                "metrics": {
                    "total_calls": metrics.total_calls,
                    "connected_calls": metrics.connected_calls,
                    "connection_rate": metrics.connection_rate,
                    "bant_completion_rate": metrics.bant_completion_rate,
                    "avg_duration_seconds": metrics.avg_duration_seconds,
                    "transfer_rate": metrics.transfer_rate,
                    "success_sessions": len(metrics.success_sessions),
                    "failure_sessions": len(metrics.failure_sessions),
                    "anomalies": metrics.anomalies,
                },
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        logger.exception("Failed to generate daily log")
        return (
            json.dumps({
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }),
            500,
            {"Content-Type": "application/json"},
        )


@functions_framework.http
def generate_ondemand_report(request):
    """HTTP Cloud Function: generate an on-demand report for a date range.

    Accepts POST with JSON body:
        - start_date: str (YYYY-MM-DD, required)
        - end_date: str (YYYY-MM-DD, required)
        - requested_by: str (optional, default "system")

    Returns:
        JSON response with status and GCS path.
    """
    try:
        body = request.get_json(silent=True)
        if not body:
            return (
                json.dumps({"error": "Request body required with start_date and end_date."}),
                400,
                {"Content-Type": "application/json"},
            )

        start_date = body.get("start_date")
        end_date = body.get("end_date")
        requested_by = body.get("requested_by", "system")

        if not start_date or not end_date:
            return (
                json.dumps({"error": "Both start_date and end_date are required."}),
                400,
                {"Content-Type": "application/json"},
            )

        for d in (start_date, end_date):
            if not _validate_date(d):
                return (
                    json.dumps({"error": f"Invalid date format: {d}. Use YYYY-MM-DD."}),
                    400,
                    {"Content-Type": "application/json"},
                )

        logger.info(
            "=== On-demand report: %s to %s (by %s) ===",
            start_date,
            end_date,
            requested_by,
        )

        # Collect daily reports for the range.
        from pipeline.gcs_client import read_markdown, upload_markdown
        from pipeline.config import GCS_DAILY_PREFIX, GCS_REPORTS_PREFIX

        current = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")

        daily_reports: list[str] = []
        missing_dates: list[str] = []

        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            path = f"{GCS_DAILY_PREFIX}/{date_str}.md"
            content = read_markdown(path)
            if content:
                daily_reports.append(content)
            else:
                missing_dates.append(date_str)
            current += timedelta(days=1)

        if not daily_reports:
            return (
                json.dumps({
                    "status": "no_data",
                    "message": f"No daily reports found for {start_date} to {end_date}.",
                    "missing_dates": missing_dates,
                }),
                200,
                {"Content-Type": "application/json"},
            )

        # Use Gemini to synthesize a period report.
        from pipeline.gemini_client import _ensure_init

        import vertexai
        from vertexai.generative_models import GenerativeModel, GenerationConfig
        from pipeline.config import GEMINI_MODEL, GEMINI_TEMPERATURE

        _ensure_init()

        model = GenerativeModel(
            GEMINI_MODEL,
            system_instruction=[
                "You are an AI operations analyst for the H-Voice call agent system (HMCA). "
                "Generate a period summary report in markdown following the report template structure. "
                "Analyze trends, key findings, and provide actionable recommendations. "
                "Output ONLY the markdown content."
            ],
        )

        combined_reports = "\n\n---\n\n".join(daily_reports)
        # Truncate if needed to fit context.
        if len(combined_reports) > 30000:
            combined_reports = combined_reports[:30000] + "\n... [truncated]"

        prompt = (
            f"Generate a period summary report for H-Voice agent from {start_date} to {end_date}.\n"
            f"Requested by: {requested_by}\n\n"
            f"Use this template structure:\n"
            f"---\ndate: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
            f"agent: h-voice-call\ntype: report\n"
            f"period: {start_date} ~ {end_date}\n"
            f"requested_by: {requested_by}\n"
            f"generated_at: {datetime.now(timezone.utc).isoformat()}\n---\n\n"
            f"# H-Voice Report: {start_date} ~ {end_date}\n\n"
            f"## Daily Reports Data:\n\n{combined_reports}"
        )

        response = model.generate_content(
            prompt,
            generation_config=GenerationConfig(
                temperature=GEMINI_TEMPERATURE,
                max_output_tokens=8192,
            ),
        )

        report_content = response.text

        # Store the report.
        report_path = (
            f"{GCS_REPORTS_PREFIX}/{start_date}_{end_date}.md"
        )
        gcs_uri = upload_markdown(report_content, report_path)

        # Update embedding index for the new report.
        try:
            file_entry = build_file_index(report_path, report_content)
            add_to_index(file_entry)
            logger.info("Embedding index updated for %s", report_path)
        except Exception:
            logger.exception("Failed to update embedding index (non-fatal)")

        logger.info("On-demand report stored: %s", gcs_uri)

        return (
            json.dumps({
                "status": "success",
                "gcs_path": gcs_uri,
                "period": f"{start_date} ~ {end_date}",
                "daily_reports_found": len(daily_reports),
                "missing_dates": missing_dates,
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        logger.exception("Failed to generate on-demand report")
        return (
            json.dumps({
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }),
            500,
            {"Content-Type": "application/json"},
        )


@functions_framework.http
def rebuild_search_index(request):
    """HTTP Cloud Function: rebuild the full semantic search embedding index.

    Scans all markdown files in GCS, generates embeddings for each, and
    overwrites the stored index.  Useful for initial setup or recovery.

    Returns:
        JSON response with status and entry count.
    """
    try:
        logger.info("=== Starting full search index rebuild ===")
        index = rebuild_index()
        logger.info("=== Search index rebuild complete: %d entries ===", len(index))

        return (
            json.dumps({
                "status": "success",
                "entries": len(index),
                "message": f"Search index rebuilt with {len(index)} file entries.",
            }),
            200,
            {"Content-Type": "application/json"},
        )

    except Exception as e:
        logger.exception("Failed to rebuild search index")
        return (
            json.dumps({
                "status": "error",
                "error": str(e),
                "error_type": type(e).__name__,
            }),
            500,
            {"Content-Type": "application/json"},
        )
