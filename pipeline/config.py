"""Configuration for the H-Orchestrator pipeline."""

import os

GCP_PROJECT = os.getenv("GCP_PROJECT", "dl-cx-sync")
GCS_BUCKET = os.getenv("GCS_BUCKET", "hmca-agent-logs")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")
GEMINI_LOCATION = os.getenv("GEMINI_LOCATION", "us-central1")
GEMINI_TEMPERATURE = 0.3

# BigQuery
BQ_DATASET = os.getenv("BQ_DATASET", "")  # To be configured after schema check
BQ_TABLE_PREFIX = "hvoice"

# GCS paths
GCS_DAILY_PREFIX = "daily/h-voice"
GCS_REPORTS_PREFIX = "reports/h-voice"
GCS_TEMPLATES_PREFIX = "templates"

# Embedding / Semantic Search (QMD)
EMBEDDING_MODEL = "text-embedding-005"
EMBEDDING_DIMENSIONS = 768
GCS_INDEX_PATH = "index/embeddings.json"
