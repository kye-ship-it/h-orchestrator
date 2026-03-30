#!/bin/bash
set -euo pipefail

# =============================================================
# H-Voice Daily Log Backfill Script
#
# Usage:
#   bash infra/backfill.sh 2026-03-01 2026-03-29
#   bash infra/backfill.sh 2026-03-25              # single day
# =============================================================

PROJECT="hyundai-bi-agent-dev"
REGION="asia-northeast3"
FUNCTION_NAME="generate-daily-report"

START_DATE="${1:?Usage: backfill.sh START_DATE [END_DATE]}"
END_DATE="${2:-$START_DATE}"

# Get the Cloud Function URL
FUNCTION_URL=$(gcloud functions describe "${FUNCTION_NAME}" \
  --gen2 --region "${REGION}" --project "${PROJECT}" \
  --format="value(serviceConfig.uri)")

if [ -z "${FUNCTION_URL}" ]; then
  echo "Error: Cloud Function '${FUNCTION_NAME}' not found. Deploy it first."
  exit 1
fi

# Get identity token for authenticated call
TOKEN=$(gcloud auth print-identity-token)

echo "=== Backfill: ${START_DATE} ~ ${END_DATE} ==="
echo "Function URL: ${FUNCTION_URL}"
echo ""

CURRENT="${START_DATE}"
SUCCESS=0
FAIL=0
NO_DATA=0

while [[ "${CURRENT}" < "${END_DATE}" || "${CURRENT}" == "${END_DATE}" ]]; do
  echo -n "${CURRENT} ... "

  RESPONSE=$(curl -s -w "\n%{http_code}" \
    -H "Authorization: Bearer ${TOKEN}" \
    "${FUNCTION_URL}?target_date=${CURRENT}")

  HTTP_CODE=$(echo "${RESPONSE}" | tail -1)
  BODY=$(echo "${RESPONSE}" | sed '$d')

  STATUS=$(echo "${BODY}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null || echo "unknown")

  if [ "${HTTP_CODE}" = "200" ] && [ "${STATUS}" = "success" ]; then
    echo "✅ success"
    SUCCESS=$((SUCCESS + 1))
  elif [ "${HTTP_CODE}" = "200" ] && [ "${STATUS}" = "no_data" ]; then
    echo "⏭️  no data"
    NO_DATA=$((NO_DATA + 1))
  else
    echo "❌ failed (HTTP ${HTTP_CODE})"
    echo "  ${BODY}" | head -1
    FAIL=$((FAIL + 1))
  fi

  # Next day
  CURRENT=$(date -j -v+1d -f "%Y-%m-%d" "${CURRENT}" "+%Y-%m-%d" 2>/dev/null || \
            date -d "${CURRENT} + 1 day" "+%Y-%m-%d")

  # Brief pause to avoid rate limiting
  sleep 2
done

echo ""
echo "=== Backfill Complete ==="
echo "Success: ${SUCCESS} | No Data: ${NO_DATA} | Failed: ${FAIL}"
