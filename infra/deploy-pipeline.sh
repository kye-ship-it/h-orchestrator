#!/bin/bash
set -euo pipefail

PROJECT="dl-cx-sync"
REGION="us-central1"
FUNCTION_NAME="generate-daily-report"
SA_EMAIL="${FUNCTION_NAME}@${PROJECT}.iam.gserviceaccount.com"

echo "=== Deploying Cloud Function: ${FUNCTION_NAME} ==="

# Create service account if not exists
gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT}" 2>/dev/null || \
  gcloud iam service-accounts create "${FUNCTION_NAME}" \
    --project="${PROJECT}" \
    --display-name="H-Orchestrator Pipeline"

# Grant permissions
for ROLE in roles/bigquery.dataViewer roles/storage.objectAdmin roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

# Deploy
gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --runtime python311 \
  --region "${REGION}" \
  --source ./pipeline \
  --entry-point generate_daily_report \
  --trigger-http \
  --project "${PROJECT}" \
  --memory 512MB \
  --timeout 300s \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "GCP_PROJECT=${PROJECT},GCS_BUCKET=hmca-agent-logs,GEMINI_MODEL=gemini-3.1-flash-lite-preview"

echo "=== Deployed successfully ==="
FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" --gen2 --region "${REGION}" --project "${PROJECT}" --format="value(serviceConfig.uri)")
echo "Function URL: ${FUNCTION_URL}"
