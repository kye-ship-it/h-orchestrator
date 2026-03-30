#!/bin/bash
set -euo pipefail

PROJECT="hyundai-bi-agent-dev"
BUCKET="h-agent-log"
REGION="asia-northeast3"

echo "Creating GCS bucket: gs://${BUCKET}"
gcloud storage buckets create "gs://${BUCKET}" \
  --project="${PROJECT}" \
  --location="${REGION}" \
  --uniform-bucket-level-access \
  2>/dev/null || echo "Bucket already exists"

echo "Uploading templates..."
gsutil cp pipeline/templates/daily-log.md "gs://${BUCKET}/templates/daily-log.md"
gsutil cp pipeline/templates/report.md "gs://${BUCKET}/templates/report.md"

echo "Done."
