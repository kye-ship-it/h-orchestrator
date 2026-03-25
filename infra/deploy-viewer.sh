#!/bin/bash
set -euo pipefail

PROJECT="dl-cx-sync"
REGION="us-central1"
SERVICE_NAME="hmca-viewer"
SA_EMAIL="${SERVICE_NAME}@${PROJECT}.iam.gserviceaccount.com"

echo "=== Deploying Cloud Run: ${SERVICE_NAME} ==="

# Create service account if not exists
gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT}" 2>/dev/null || \
  gcloud iam service-accounts create "${SERVICE_NAME}" \
    --project="${PROJECT}" \
    --display-name="HMCA Viewer"

# Grant permissions
for ROLE in roles/storage.objectViewer roles/storage.objectCreator roles/bigquery.dataViewer roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "${PROJECT}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="${ROLE}" \
    --quiet
done

# Deploy from source
gcloud run deploy "${SERVICE_NAME}" \
  --source ./viewer \
  --region "${REGION}" \
  --project "${PROJECT}" \
  --allow-unauthenticated \
  --service-account "${SA_EMAIL}" \
  --set-env-vars "GCS_BUCKET=hmca-agent-logs,GCP_PROJECT=${PROJECT},GEMINI_MODEL=gemini-3.1-flash-lite-preview" \
  --memory 512Mi \
  --min-instances 0

echo "=== Deployed successfully ==="
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT}" --format="value(status.url)")
echo "Service URL: ${SERVICE_URL}"
