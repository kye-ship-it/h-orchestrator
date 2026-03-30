#!/bin/bash
set -euo pipefail

PROJECT="hyundai-bi-agent-dev"
REGION="asia-northeast3"
SERVICE_NAME="h-agent-orchestrator"
SA_EMAIL="h-agent-orchestrator@${PROJECT}.iam.gserviceaccount.com"

echo "=== Deploying Cloud Run: ${SERVICE_NAME} ==="

# Deploy from source (Cloud Build will use Dockerfile)
gcloud run deploy "${SERVICE_NAME}" \
  --source ./viewer \
  --region "${REGION}" \
  --project "${PROJECT}" \
  --allow-unauthenticated \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "\
GCS_BUCKET=h-agent-log,\
GCP_PROJECT=${PROJECT},\
GEMINI_MODEL=gemini-2.5-flash,\
GEMINI_LOCATION=asia-northeast3,\
BQ_META_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_meta,\
BQ_LEAD_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_lead,\
BQ_ANALYSIS_TABLE=dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_analysis" \
  --memory 512Mi \
  --min-instances 0

echo "=== Deployed successfully ==="
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT}" --format="value(status.url)")
echo "Service URL: ${SERVICE_URL}"
