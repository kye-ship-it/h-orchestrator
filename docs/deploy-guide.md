# H-Orchestrator 배포 가이드

> GCP Cloud Run + Cloud Functions + Cloud Scheduler 배포 절차

---

## 사전 요구사항

| 항목 | 상태 |
|------|------|
| GCP 프로젝트 `dl-cx-sync` 접근 권한 | 필요 |
| `gcloud` CLI 설치 및 로그인 | `gcloud auth login` |
| Service Account 생성 완료 | SA 이미 생성됨 |
| IAP | Phase 1에서는 미적용 (`--allow-unauthenticated`) |

### 환경 정보

| 항목 | 값 |
|------|---|
| GCP Project | `dl-cx-sync` |
| Region | `asia-northeast3` (Seoul) |
| GCS Bucket | `h-gdcx-orchestrator` |
| Gemini Model | `gemini-2.5-flash-lite-preview-06-17` |
| BQ Tables (ODS) | `ods_hmb_hvoice_meta`, `ods_hmb_hvoice_lead`, `ods_hmb_hvoice_analysis` |

---

## 배포 순서

### Step 0. 프로젝트 설정 확인

```bash
gcloud config set project dl-cx-sync
gcloud config set compute/region asia-northeast3
```

### Step 1. GCS 버킷 생성 + 템플릿 업로드

```bash
bash infra/setup.sh
```

실행 결과:
- `gs://h-gdcx-orchestrator` 버킷 생성 (asia-northeast3)
- `templates/daily-log.md`, `templates/report.md` 업로드

### Step 2. Cloud Function 배포 (Daily Log 파이프라인)

```bash
bash infra/deploy-pipeline.sh
```

실행 결과:
- Service Account `generate-daily-report@dl-cx-sync.iam.gserviceaccount.com` 생성 (이미 있으면 스킵)
- IAM 권한 부여: BigQuery DataViewer, Storage ObjectAdmin, Vertex AI User
- Cloud Function `generate-daily-report` (gen2, Python 3.11) 배포
- 환경변수: GCS 버킷, Gemini 모델, BQ 테이블 경로 설정
- 배포 완료 시 Function URL 출력

### Step 3. Cloud Scheduler 설정

```bash
bash infra/scheduler.sh
```

실행 결과:
- Cloud Scheduler Job `daily-hvoice-report` 생성
- 매일 07:00 (America/Santiago) Cloud Function 자동 호출
- OIDC 인증으로 Cloud Function 호출

### Step 4. Cloud Run 배포 (Viewer)

```bash
bash infra/deploy-viewer.sh
```

실행 결과:
- Service Account `hmca-viewer@dl-cx-sync.iam.gserviceaccount.com` 생성 (이미 있으면 스킵)
- IAM 권한 부여: Storage ObjectViewer/Creator, BigQuery DataViewer, Vertex AI User
- `viewer/` 디렉토리 기반 Cloud Build → Cloud Run 배포
- `--allow-unauthenticated` (Phase 1 MVP)
- 배포 완료 시 **Service URL 출력** ← 이 URL로 접속

---

## 배포 후 검증

### Cloud Function 수동 테스트

```bash
# 어제 날짜로 Daily Log 생성 테스트
gcloud scheduler jobs run daily-hvoice-report \
  --project dl-cx-sync \
  --location asia-northeast3
```

또는 특정 날짜 지정:

```bash
FUNCTION_URL=$(gcloud functions describe generate-daily-report \
  --gen2 --region asia-northeast3 --project dl-cx-sync \
  --format="value(serviceConfig.uri)")

curl -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "${FUNCTION_URL}?target_date=2026-03-28"
```

### Viewer 접속 확인

```bash
# URL 확인
gcloud run services describe hmca-viewer \
  --region asia-northeast3 --project dl-cx-sync \
  --format="value(status.url)"
```

출력된 URL로 브라우저 접속 → 폴더 트리, 마크다운 렌더링, 검색 기능 확인

### GCS 파일 확인

```bash
# 생성된 Daily Log 확인
gsutil ls gs://h-gdcx-orchestrator/daily/h-voice/

# 임베딩 인덱스 확인
gsutil ls gs://h-gdcx-orchestrator/index/
```

---

## Backfill (과거 데이터 일괄 생성)

배포 완료 후, 과거 날짜의 Daily Log를 일괄 생성하려면:

```bash
# 기간 지정 (시작일 ~ 종료일)
bash infra/backfill.sh 2026-03-01 2026-03-29

# 특정 날짜 하나만
bash infra/backfill.sh 2026-03-25
```

- 각 날짜별로 Cloud Function을 순차 호출 (2초 간격)
- 데이터 없는 날은 자동 스킵
- 완료 후 성공/스킵/실패 건수 출력

---

## 아키텍처 요약

```
[팀원] → Cloud Run (Viewer)
              │ reads
         ┌────┴────────────┐
         ▼                 ▼
    GCS (*.md)    Cloud Function (Pipeline)
    index/           │
                     ├─ BigQuery (ODS 3 tables)
                     ├─ Gemini (리포트 생성)
                     ├─ GCS (저장)
                     └─ Vertex AI Embeddings (인덱싱)
                          ▲
                   Cloud Scheduler
                   (매일 07:00)
```

### 서비스 목록

| 서비스 | 이름 | 역할 |
|--------|------|------|
| Cloud Run | `hmca-viewer` | 프론트엔드 뷰어 + On-demand 리포트 |
| Cloud Function | `generate-daily-report` | Daily Log 자동 생성 파이프라인 |
| Cloud Scheduler | `daily-hvoice-report` | 매일 07:00 자동 트리거 |
| GCS | `h-gdcx-orchestrator` | 마크다운 + 임베딩 인덱스 저장 |

### 배포 스크립트 목록

| 스크립트 | 역할 |
|----------|------|
| `infra/setup.sh` | GCS 버킷 생성 + 템플릿 업로드 |
| `infra/deploy-pipeline.sh` | Cloud Function 배포 |
| `infra/scheduler.sh` | Cloud Scheduler 설정 |
| `infra/deploy-viewer.sh` | Cloud Run 배포 |
| `infra/backfill.sh` | 과거 데이터 일괄 생성 |

---

## 트러블슈팅

### Cloud Function 배포 실패

```bash
# 로그 확인
gcloud functions logs read generate-daily-report \
  --gen2 --region asia-northeast3 --project dl-cx-sync --limit 50
```

### Cloud Run 배포 실패

```bash
# 빌드 로그 확인
gcloud builds list --project dl-cx-sync --limit 5
gcloud builds log <BUILD_ID> --project dl-cx-sync
```

### Daily Log 생성 실패

```bash
# Cloud Function 실행 로그
gcloud logging read "resource.type=cloud_function AND resource.labels.function_name=generate-daily-report" \
  --project dl-cx-sync --limit 20 --format="table(timestamp,severity,textPayload)"
```

### 일반적인 문제

| 증상 | 원인 | 해결 |
|------|------|------|
| `No call records found` | 해당 날짜 BQ 데이터 없음 | 데이터 있는 날짜로 테스트 |
| `Permission denied` on BQ | SA에 BigQuery 권한 없음 | `deploy-pipeline.sh` 재실행 |
| `Bucket not found` | GCS 버킷 미생성 | `setup.sh` 실행 |
| Viewer 접속 불가 | Cloud Run 배포 미완료 | `deploy-viewer.sh` 실행 후 URL 확인 |
| Gemini API 오류 | 모델 미지원 리전 | `GEMINI_LOCATION` 확인 |
