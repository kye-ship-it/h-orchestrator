# H-Orchestrator GCP 변경사항 로그

> 팀원 공유용 — 이 프로젝트 배포 과정에서 GCP 프로젝트 `dl-cx-sync`에 가한 변경사항

---

## 변경 일시: 2026-03-29

### 1. API 활���화

| API | 이유 | 기존 서비스 영향 |
|-----|------|----------------|
| Cloud Functions API (`cloudfunctions.googleapis.com`) | Cloud Function 배포에 필요 | 없음 — 활성화만으로 기존 서비스에 영향 없음 |

### 2. Service Account 생성

| SA | 용도 |
|----|------|
| `generate-daily-report@dl-cx-sync.iam.gserviceaccount.com` | H-Orchestrator Daily Log 파이프���인 전용 |

### 3. IAM 바인딩 추가

위 SA에 아래 역할을 부여함 (기존 바인딩에는 영향 없음 — 추가만):

| 역할 | 용도 |
|------|------|
| `roles/bigquery.dataViewer` | ODS 테이블 읽기 |
| `roles/storage.objectAdmin` | GCS 버킷 읽기/쓰기 (Daily Log, 임베딩 인덱스) |
| `roles/aiplatform.user` | Vertex AI Gemini / Embeddings 호출 |

### 4. 리소스 생성

| 리소스 | 이름 | 리전 | 비고 |
|--------|------|------|------|
| Cloud Function (gen2) | `generate-daily-report` | asia-northeast3 | Python 3.11, HTTP 트리거 |
| GCS 버킷 | `h-gdcx-orchestrator` | asia-northeast3 | Daily Log + 임베딩 인덱스 저장 |

### 5. 주의사항

- **SA 교체 필요 (2곳)**:
  1. **Cloud Function** (`generate-daily-report`): 현재 `generate-daily-report@dl-cx-sync.iam.gserviceaccount.com` 사용 중. Cloud Run 콘솔 → Edit & Deploy → Security 탭에서 변경. 새 SA에 동일 IAM 역할(bigquery.dataViewer, bigquery.jobUser, storage.objectAdmin, aiplatform.user) 부여 필요.
  2. **Cloud Scheduler** (`daily-hvoice-log`): OIDC 인증에 같은 SA 사용 중. Scheduler 콘솔 → 작업 수정 → OIDC 서비스 계정 변경.
- **Gemini 모델 리전**: `gemini-2.5-flash-lite` 모델은 `asia-northeast3`(Seoul)에서 미지원. `GEMINI_LOCATION=us-central1`로 설정하여 Gemini API 호출만 us-central1로 전송. Cloud Function 자체는 Seoul에서 실행됨.
- **IAM 추가 바인딩**: `roles/bigquery.jobUser` 역할도 SA에 부여함 (BQ 쿼리 실행에 필요).

### 6. 변경하지 않은 것 (확인)

- 기존 Service Account 수정/삭제: **없음**
- 기존 IAM 바인딩 수정/삭제: **없음**
- 기존 Cloud Run 서비스 수정: **없음**
- 기존 BigQuery 테이블/뷰 수정: **없음**
- 기존 GCS 버킷 수정: **없음**

---

## 향후 추가 예정

| 리소스 | 이름 | 용도 |
|--------|------|------|
| Cloud Scheduler | `daily-hvoice-log` | 매일 07:00 Cloud Function 자동 호출 |
| Cloud Run | `h-agent-view` | Next.js 뷰어 (프론트엔드) |
| Service Account | `h-agent-view@dl-cx-sync.iam.gserviceaccount.com` | ��어 전용 SA |
