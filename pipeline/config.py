"""Configuration for the H-Orchestrator pipeline."""

import os

GCP_PROJECT = os.getenv("GCP_PROJECT", "hyundai-bi-agent-dev")
GCS_BUCKET = os.getenv("GCS_BUCKET", "h-agent-log")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "asia-northeast3")
GEMINI_TEMPERATURE = 0.3

# BigQuery source tables (STG — ODS transformations applied in query)
BQ_META_TABLE = os.getenv(
    "BQ_META_TABLE", "dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_meta"
)
BQ_LEAD_TABLE = os.getenv(
    "BQ_LEAD_TABLE", "dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_lead"
)
BQ_ANALYSIS_TABLE = os.getenv(
    "BQ_ANALYSIS_TABLE", "dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_analysis"
)

# GCS paths
GCS_DAILY_PREFIX = os.getenv("GCS_DAILY_PREFIX", "daily/h-voice/hmb")
GCS_REPORTS_PREFIX = os.getenv("GCS_REPORTS_PREFIX", "reports/h-voice")
GCS_TEMPLATES_PREFIX = "templates"

# Embedding / Semantic Search (QMD)
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_DIMENSIONS = 768
GCS_INDEX_PATH = "index/embeddings.json"
