#!/bin/bash
set -euo pipefail

PROJECT="hyundai-bi-agent-dev"
REGION="asia-northeast3"
FUNCTION_NAME="generate-daily-report"
SA_EMAIL="h-agent-orchestrator@${PROJECT}.iam.gserviceaccount.com"

echo "=== Deploying Cloud Function: ${FUNCTION_NAME} ==="

# Deploy — entry-point must match function name in main.py
gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime python311 \
  --region "${REGION}" \
  --source ./pipeline \
  --entry-point generate_daily_log \
  --trigger-http \
  --project "${PROJECT}" \
  --memory 512Mi \
  --timeout 300s \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "\
GCP_PROJECT=${PROJECT},\
GCS_BUCKET=h-agent-log,\
GEMINI_MODEL=gemini-2.5-flash,\
BQ_META_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_meta,\
BQ_LEAD_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_lead,\
BQ_ANALYSIS_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_analysis"

echo "=== Deployed successfully ==="
FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" --gen2 --region "${REGION}" --project "${PROJECT}" --format="value(serviceConfig.uri)")
echo "Function URL: ${FUNCTION_URL}"
