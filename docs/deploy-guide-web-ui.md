# H-Orchestrator 배포 가이드 (GCP 웹 콘솔)

> Cloud Shell 없이 GCP 콘솔 웹 UI만으로 배포하는 절차

---

## Step 1. GCS 버킷 생성 + 템플릿 업로드

### 1-1. 버킷 생성

1. [Cloud Storage 콘솔](https://console.cloud.google.com/storage/browser?project=dl-cx-sync) 접속
2. **"만들기(CREATE)"** 클릭
3. 설정:
   - 버킷 이름: `h-gdcx-orchestrator`
   - 위치 유형: **리전** → `asia-northeast3 (Seoul)`
   - 스토리지 클래스: Standard
   - 액세스 제어: **균일한 버킷 수준 액세스(Uniform)** 선택
4. **"만들기"** 클릭

### 1-2. 폴더 구조 생성

버킷 안에서 아래 순서로 폴더를 만듭니다:

```
h-gdcx-orchestrator/
├── daily/
│   └── h-voice/          ← 에이전트 유형
│       ├── hmb/          ← H-Voice Brazil
│       └── hmca/         ← H-Voice (향후 확장)
├── reports/
│   └── h-voice/          ← 법인별/통합 리포트 모두 여기에 생성
├── index/                ← 임베딩 인덱스 (자동 생성됨)
└── templates/            ← 템플릿 파일 업로드
```

1. **"폴더 만들기"** → `daily` → 만들기
2. `daily/` 진입 → **"폴더 만들기"** → `h-voice` → 만들기
3. `daily/h-voice/` 진입 → **"폴더 만들기"** → `hmb` → 만들기
4. `daily/h-voice/` 진입 → **"폴더 만들기"** → `hmca` → 만들기
5. 버킷 루트로 돌아가기
6. **"폴더 만들기"** → `reports` → 만들기
7. `reports/` 진입 → **"폴더 만들기"** → `h-voice` → 만들기
8. 버킷 루트로 돌아가기
9. **"폴더 만들기"** → `index` → 만들기
10. **"폴더 만들기"** → `templates` → 만들기

### 1-3. 템플릿 업로드

1. `templates/` 폴더 진입
2. **"파일 업로드"** 클릭
3. 로컬에서 아래 2개 파일 업로드:
   - `pipeline/templates/daily-log.md`
   - `pipeline/templates/report.md`

---

## Step 2. Cloud Function 배포

### 2-1. 함수 생성

1. [Cloud Functions 콘솔](https://console.cloud.google.com/functions/list?project=dl-cx-sync) 접속
2. **"Write a function"** 클릭

### 2-2. 기본 설정

| 항목 | 값 |
|------|---|
| Function name | `generate-daily-report` |
| Region | `asia-northeast3 (Seoul)` |
| Trigger type | **HTTPS** |
| Authentication | **Require authentication** |

> Environment 선택이 보이면 **2nd gen** 선택. 안 보이면 기본값(2nd gen)으로 진행.

### 2-3. 런타임, 빌드 설정

**"런타임, 빌드, 연결 및 보안 설정"** 펼치기:

| 항목 | 값 |
|------|---|
| 메모리 | 512 MiB |
| 시간 초과 | 300초 |
| 런타임 서비스 계정 | `generate-daily-report@dl-cx-sync.iam.gserviceaccount.com` (이미 만들어둔 SA) |

**런타임 환경 변수** 추가 (하나씩 "변수 추가" 클릭):

| 이름 | 값 |
|------|---|
| `GCP_PROJECT` | `dl-cx-sync` |
| `GCS_BUCKET` | `h-gdcx-orchestrator` |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite-preview-06-17` |
| `BQ_META_TABLE` | `dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_meta` |
| `BQ_LEAD_TABLE` | `dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_lead` |
| `BQ_ANALYSIS_TABLE` | `dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_analysis` |

**"다음"** 클릭

### 2-4. 코드 입력

| 항목 | 값 |
|------|---|
| 런타임 | **Python 3.11** |
| 진입점 | `generate_daily_log` |
| 소스 코드 | **ZIP 업로드** |

#### ZIP 파일 준비 (로컬에서)

`pipeline/` 폴더의 내용물을 ZIP으로 만들어야 합니다. **폴더 자체가 아니라 안의 파일들이 루트에 오도록** 압축:

```bash
cd pipeline && zip -r ../pipeline.zip . -x "tests/*" "__pycache__/*" "*.pyc" "conftest.py" && cd ..
```

생성된 `pipeline.zip`의 구조 (확인):
```
pipeline.zip
├── main.py          ← 루트에 있어야 함
├── config.py
├── bq_client.py
├── mapper.py
├── gemini_client.py
├── gcs_client.py
├── embedding_client.py
├── search_index.py
├── requirements.txt
├── __init__.py
└── templates/
    ├── daily-log.md
    └── report.md
```

#### 업로드

1. **소스 코드**: "ZIP 업로드" 선택
2. **Cloud Storage 위치**: 스테이징 버킷 선택 (자동 생성됨) 또는 `h-gdcx-orchestrator` 선택
3. **ZIP 파일**: 위에서 만든 `pipeline.zip` 선택
4. **"배포"** 클릭

> 배포에 2~3분 소요. 상태가 "활성(Active)" ✅ 되면 성공.

---

## Step 3. Cloud Scheduler 설정

1. [Cloud Scheduler 콘솔](https://console.cloud.google.com/cloudscheduler?project=dl-cx-sync) 접속
2. **"작업 만들기(CREATE JOB)"** 클릭

### 3-1. 작업 정의

| 항목 | 값 |
|------|---|
| 이름 | `daily-hvoice-report` |
| 리전 | `asia-northeast3 (Seoul)` |
| 빈도 | `0 7 * * *` |
| 시간대 | `America/Santiago` (칠레 시간) |

### 3-2. 실행 구성

| 항목 | 값 |
|------|---|
| 대상 유형 | **HTTP** |
| URL | Cloud Function URL (Step 2 완료 후 함수 상세에서 복사) |
| HTTP 메서드 | **GET** |

### 3-3. 인증 헤더

| 항목 | 값 |
|------|---|
| 인증 헤더 | **OIDC 토큰 추가** |
| 서비스 계정 | `generate-daily-report@dl-cx-sync.iam.gserviceaccount.com` |

**"만들기"** 클릭

### 3-4. 테스트

생성된 작업 옆 **⋮ 메뉴** → **"지금 실행"** → 상태가 "성공"인지 확인

---

## Step 4. Cloud Run 배포 (Viewer)

### 4-1. GitHub 연결 방식 (권장)

1. [Cloud Run 콘솔](https://console.cloud.google.com/run?project=dl-cx-sync) 접속
2. **"서비스 만들기(CREATE SERVICE)"** 클릭
3. **"소스 리포지터리에서 지속적으로 새 버전 배포"** 선택
4. **"CLOUD BUILD 설정"** 클릭
   - 소스 제공업체: **GitHub** 선택
   - 리포지토리: `kye-ship-it/h-orchestrator` 연결
   - 브랜치: `main`
   - 빌드 유형: **Dockerfile**
   - 소스 위치: `/viewer/Dockerfile`

### 4-2. 서비스 설정

| 항목 | 값 |
|------|---|
| 서비스 이름 | `hmca-viewer` |
| 리전 | `asia-northeast3 (Seoul)` |
| 인증 | **인증되지 않은 호출 허용** (Allow unauthenticated invocations) |
| 컨테이너 포트 | `8080` |
| 메모리 | 512 MiB |
| 최소 인스턴스 | 0 |
| 서비스 계정 | `hmca-viewer@dl-cx-sync.iam.gserviceaccount.com` |

### 4-3. 환경 변수

**"컨테이너, 볼륨, 네트워킹, 보안"** 탭 → **"변수 및 보안 비밀"**:

| 이름 | 값 |
|------|---|
| `GCS_BUCKET` | `h-gdcx-orchestrator` |
| `GCP_PROJECT` | `dl-cx-sync` |
| `GEMINI_MODEL` | `gemini-2.5-flash-lite-preview-06-17` |

**"만들기"** 클릭

> 빌드 + 배포에 5~10분 소요. 완료되면 서비스 URL이 표시됩니다.

### 4-4. 대안: 수동 Docker 이미지 빌드

GitHub 연결이 안 되는 경우:

1. [Cloud Build 콘솔](https://console.cloud.google.com/cloud-build/triggers?project=dl-cx-sync) 접속
2. **수동 빌드 실행** → GitHub 소스 지정
3. 빌드 완료 후 Cloud Run에서 해당 이미지로 서비스 생성

---

## Step 5. Backfill (과거 데이터 일괄 생성)

웹 UI에서는 Cloud Scheduler의 **"지금 실행"**이 어제 날짜만 처리합니다.
특정 날짜를 지정하려면 Cloud Function 상세 → **"테스트"** 탭에서:

```json
{
  "target_date": "2026-03-25"
}
```

입력 후 **"함수 테스트"** 클릭. 날짜별로 반복해야 하므로 여러 날짜가 필요하면 날짜만 바꿔가며 실행하세요.

---

## 배포 완료 체크리스트

| # | 항목 | 확인 방법 |
|---|------|----------|
| 1 | GCS 버킷 존재 | Storage 콘솔에서 `h-gdcx-orchestrator` 확인 |
| 2 | 템플릿 업로드 | `templates/` 폴더에 2개 파일 확인 |
| 3 | Cloud Function 활성 | Functions 콘솔에서 `generate-daily-report` 상태 ✅ |
| 4 | Scheduler 동작 | "지금 실행" → 성공 확인 |
| 5 | Daily Log 생성됨 | GCS `daily/h-voice/` 에 .md 파일 확인 |
| 6 | Cloud Run 동작 | 서비스 URL 접속 → 뷰어 화면 확인 |
| 7 | 뷰어에서 로그 확인 | 폴더 트리에 Daily Log 표시 확인 |

---

## 트러블슈팅

| 증상 | 확인 위치 |
|------|----------|
| Cloud Function 배포 실패 | Functions 콘솔 → 함수 클릭 → **"로그"** 탭 |
| Scheduler 실행 실패 | Scheduler 콘솔 → 작업 클릭 → **실행 기록** |
| Cloud Run 빌드 실패 | Cloud Build 콘솔 → 최근 빌드 → **로그** 확인 |
| Viewer에서 데이터 안 보임 | Cloud Run → 서비스 → **"로그"** 탭 확인 |
| `No call records found` | 해당 날짜 BQ에 데이터 있는지 확인 |
| `Permission denied` | IAM 콘솔에서 SA 권한 확인 |
