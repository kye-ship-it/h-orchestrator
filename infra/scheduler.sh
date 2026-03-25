#!/bin/bash
set -euo pipefail

PROJECT="dl-cx-sync"
REGION="us-central1"
JOB_NAME="daily-hvoice-report"

# Get the Cloud Function URL
FUNCTION_URL=$(gcloud functions describe generate-daily-report \
  --gen2 --region "${REGION}" --project "${PROJECT}" \
  --format="value(serviceConfig.uri)")

if [ -z "${FUNCTION_URL}" ]; then
  echo "Error: Cloud Function not found. Deploy it first with deploy-pipeline.sh"
  exit 1
fi

# Get the SA email for authentication
SA_EMAIL="generate-daily-report@${PROJECT}.iam.gserviceaccount.com"

echo "=== Creating Cloud Scheduler Job: ${JOB_NAME} ==="
echo "Target: ${FUNCTION_URL}"
echo "Schedule: 07:00 daily (America/Santiago)"

gcloud scheduler jobs create http "${JOB_NAME}" \
  --schedule "0 7 * * *" \
  --time-zone "America/Santiago" \
  --uri "${FUNCTION_URL}" \
  --http-method GET \
  --project "${PROJECT}" \
  --location "${REGION}" \
  --oidc-service-account-email "${SA_EMAIL}" \
  2>/dev/null || \
gcloud scheduler jobs update http "${JOB_NAME}" \
  --schedule "0 7 * * *" \
  --time-zone "America/Santiago" \
  --uri "${FUNCTION_URL}" \
  --http-method GET \
  --project "${PROJECT}" \
  --location "${REGION}" \
  --oidc-service-account-email "${SA_EMAIL}"

echo "=== Scheduler configured ==="
echo "To test manually: gcloud scheduler jobs run ${JOB_NAME} --project ${PROJECT} --location ${REGION}"
