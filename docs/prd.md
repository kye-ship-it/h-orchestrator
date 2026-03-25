
## Agent Logging & Monitoring System PRD

> 에이전트의 로깅 프로토콜을 정의하고, 오케스트레이터가 로그를 기반으로 모니터링·분석·피드백하는 시스템

---

### 1. 개요

#### 1.1 배경
AI 에이전트(H-Voice 콜 에이전트 등)가 실제 고객을 대면하여 동작하고 있으나, 에이전트가 "무엇을 했고, 어떤 결과를 냈는지"를 체계적으로 모니터링하고 피드백하는 구조가 부재한 상태. 이를 해결하기 위해 에이전트 로깅 프로토콜을 정의하고, 오케스트레이터 에이전트가 이를 읽고 리포팅·개선 제안까지 수행하는 시스템을 구축한다.

#### 1.2 핵심 원칙
- **개념 먼저, 테크 스택은 나중에** — 에이전트의 역할과 로깅 프로토콜을 비즈니스 언어로 먼저 정의하고, 구현은 법인/환경에 맞게 선택
- **프로토콜의 범용성** — 하나의 로깅·커뮤니케이션 프로토콜을 정의하면 어떤 에이전트에도 동일하게 응용 가능해야 함
- **작은 것부터 빠르게** — H-Voice 콜 에이전트 하나를 첫 번째 케이스로, 다음 주 초 프로토타입 공유

#### 1.3 스코프

| 구분 | Phase 1 (NOW) | Phase 2 (NEXT) |
|------|-------------|---------------|
| 대상 에이전트 | H-Voice 콜 에이전트 | 자체 빌드 에이전트 확장 |
| 데이터 소스 | GCP 적재 데이터 (콜 종료 후) | 실시간 이벤트 스트림 |
| 오케스트레이터 역할 | 모니터링 + 리포팅 | + 피드백 제안 + 코칭 에이전트 연동 |
| 피드백 반영 | 사람이 확인 후 수동 반영 | 에이전트 간 자동 피드백 루프 |
| 프로토콜 | 로깅 스키마 정의 | A2A 프로토콜 기반 에이전트 간 통신 |

---

### 2. 에이전트 역할 정의

#### 2.1 등장 에이전트

| 에이전트 | 역할 | Phase 1 상태 |
|----------|------|-------------|
| **콜 에이전트 (H-Voice)** | 고객 대면 콜 수행. Vapi 기반. | 이미 운영 중. 로그는 GCP에 적재됨 |
| **오케스트레이터** | 서브 에이전트의 로그를 읽고 모니터링·분석·리포팅 | **이번에 구축** |
| **코칭 에이전트** | 퍼포먼스 분석 기반 개선안 제안. 더 깊은 컨텍스트 보유 | Phase 2에서 검토 |

#### 2.2 오케스트레이터의 두 가지 기능

**기능 1: 모니터링**
- 서브 에이전트의 로그 데이터를 수집·집계
- Daily 마크다운 문서로 구조화하여 사람이 읽기 좋게 정리
- 이상치·트렌드·퍼포먼스 변화를 감지

**기능 2: 피드백 제안** (Phase 2)
- 모니터링 데이터를 기반으로 "이렇게 바꾸면 좋겠다"는 프로포즈를 마크다운으로 생성
- 단독으로 피드백 가능한 경우 오케스트레이터가 직접 수행
- 더 깊은 컨텍스트가 필요한 경우 별도 코칭 에이전트에 위임

---

### 3. 에이전트 로깅 프로토콜

> GA4 모델 참조: 세션 → 이벤트 → 인터랙션의 계층 구조로, 로우 데이터만 제대로 쌓이면 어떤 분석이든 가능하게 한다.

#### 3.1 로그 계층 구조

```
Source (트리거 출처)
  └─ Session (하나의 콜/작업 단위)
       ├─ session_id
       ├─ start_time / end_time
       ├─ source (e.g. Ofertas form, manual trigger)
       └─ Events (세션 내 개별 이벤트)
            ├─ event_id
            ├─ event_type (call_queued, call_dialed, call_accepted,
            │              call_rejected, greeting, question_1_completed,
            │              question_2_completed, ..., call_ended, transfer)
            ├─ timestamp
            ├─ actor (ai / customer / system)
            ├─ payload (이벤트별 상세 데이터)
            └─ 선후관계: 이전 event_id 참조로 시퀀스 파악 가능
```

#### 3.2 H-Voice 콜 에이전트 이벤트 흐름 (예시)

```
[Source: Ofertas 폼 제출]
  └─ Session: call_session_001
       ├─ E1: call_queued        (system → 콜 큐 등록)
       ├─ E2: call_dialed        (system → 고객에게 발신)
       ├─ E3: call_accepted      (customer → 수신)
       ├─ E4: greeting           (ai → 인사말)
       ├─ E5: question_1_asked   (ai → BANT 질문 1)
       ├─ E6: question_1_answer  (customer → 응답)
       ├─ E7: question_2_asked   (ai → BANT 질문 2)
       ├─ ...
       ├─ E12: transfer_intent   (ai → 딜러 연결 의사 확인)
       ├─ E13: dealer_transfer   (system → 딜러 연결)
       └─ E14: call_ended        (system → 통화 종료, 요약 포함)
```

#### 3.3 Phase 1 현실적 제약 (Vapi)

H-Voice는 Vapi(외부 SaaS)를 사용하므로 실시간 이벤트 스트리밍이 제한적이다. 현재 GCP에 적재되는 데이터는 **콜 종료 시점의 집계 데이터**(다이얼로그 전체, 콜 메타데이터)이므로, Phase 1에서는 이 데이터를 기반으로 위 이벤트 구조를 **역산·매핑**하여 로그를 재구성한다.

| 데이터 | 현재 GCP 적재 여부 | Phase 1 활용 |
|--------|------------------|-------------|
| 콜 메타 (시작/종료 시간, 상태) | ✅ 있음 | 세션 레벨 데이터 |
| 다이얼로그 전체 (transcript) | ✅ 있음 | 이벤트 레벨 역산 (AI가 파싱) |
| 실시간 이벤트 스트림 | ❌ Vapi 제약 | Phase 2에서 검토 |
| 소스 정보 (Ofertas 폼 등) | 🟡 별도 테이블 | JOIN으로 연결 |
| BANT 수집 결과 | ✅ 있음 | 퍼포먼스 지표로 활용 |

---

### 4. 에이전트 간 커뮤니케이션 프로토콜

#### 4.1 외부 에이전트 vs 자체 빌드 에이전트

에이전트 간 통신 방식은 **에이전트가 외부 SaaS인지, 자체 빌드인지**에 따라 분기된다.

**외부 에이전트 (Vapi 등):**
- A2A 프로토콜 직접 적용 불가 — Vapi는 자체 API/Webhook만 제공
- GCP에 적재된 데이터를 **간접적으로** 읽는 방식으로 모니터링
- 피드백은 사람이 확인 후 Vapi 프롬프트/설정에 수동 반영
- 구조: `Vapi → GCP (데이터 적재) → 오케스트레이터 (읽기 전용)`

**자체 빌드 에이전트 (향후):**
- 개발 시점부터 A2A 프로토콜을 반영하여 설계
- 에이전트 간 직접 통신 가능 (로그 공유, 피드백 수신, 설정 변경)
- 구조: `에이전트 A ↔ 오케스트레이터 ↔ 코칭 에이전트` (양방향)

#### 4.2 프로토콜 설계 원칙

자체 에이전트 구축 시 다음을 반영한다:

1. **로깅 인터페이스**: 모든 에이전트는 동일한 로그 스키마(3.1 참조)로 이벤트를 기록
2. **컨텍스트 전달**: 에이전트가 다른 에이전트에게 전달하는 정보의 포맷 = 마크다운 + 메타데이터(YAML frontmatter)
3. **역할별 접근 권한**: 오케스트레이터는 모든 서브 에이전트의 로그를 읽을 수 있고, 코칭 에이전트는 오케스트레이터의 로그도 볼 수 있음
4. **A2A 참조**: Google A2A 프로토콜을 기반으로 Agent Card, Task 구조 등을 참조하여 설계

```
[자체 빌드 에이전트의 경우]

┌──────────────────────────────────────────────────┐
│  Agent Communication Protocol (A2A 기반)         │
│                                                  │
│  ┌─────────┐    로그     ┌──────────────────┐    │
│  │ Sub     │───────────▶│ Orchestrator     │    │
│  │ Agent   │◀───────────│                  │    │
│  │         │  피드백/지시 │  - 모니터링      │    │
│  └─────────┘            │  - 분석          │    │
│                         │  - 피드백 제안    │    │
│  ┌─────────┐    로그     │                  │    │
│  │ Sub     │───────────▶│                  │    │
│  │ Agent 2 │◀───────────│                  │    │
│  │         │  피드백/지시 └────────┬─────────┘    │
│  └─────────┘                     │               │
│                            필요 시 위임           │
│                           ┌──────▼─────────┐     │
│                           │ Coaching Agent │     │
│                           │ (깊은 컨텍스트) │     │
│                           └────────────────┘     │
└──────────────────────────────────────────────────┘

[외부 에이전트(Vapi)의 경우]

  ┌─────────┐   GCP 적재    ┌──────────────────┐
  │ Vapi    │─────────────▶│ Orchestrator     │
  │ (외부)  │  (단방향)     │ - 읽기 전용 모니터링│
  └─────────┘              └──────────────────┘
       ▲                          │
       │ 사람이 수동 반영            │ 리포트/개선안
       └──────────── 사람 ◀─────────┘
```

---

### 5. 마크다운 기반 리포팅

#### 5.1 왜 마크다운인가
- **사람이 읽기 좋음**: Obsidian, Notion 등에서 바로 포맷팅되어 보임
- **에이전트가 활용하기 좋음**: LLM의 네이티브 출력 포맷, 파싱·생성 모두 용이
- **경량**: 시스템 로그 대비 저장/전달 비용 미미
- **상호 참조 가능**: 내부 링크([[wikilink]])로 문서 간 그래프 구조 형성 가능

#### 5.2 Daily Log 템플릿

```markdown
---
date: {YYYY-MM-DD}
agent: h-voice-call
type: daily-log
generated_at: {ISO timestamp}
---

# H-Voice Daily Log — {date}

## Summary
> {3줄 이내 핵심 요약: 총 콜 수, 성공률, 주요 이슈}

## Key Metrics
| Metric | Value | vs Prev Day | Status |
|--------|-------|-------------|--------|
| Total Calls | {n} | {+/-}% | {🟢/🟡/🔴} |
| Connection Rate | {n}% | {+/-}pp | |
| BANT Completion Rate | {n}% | {+/-}pp | |
| Avg Call Duration | {n}s | {+/-}s | |
| Dealer Transfer Rate | {n}% | {+/-}pp | |

## Session Breakdown
### 성공 콜 분석
{BANT 수집 완료 + 딜러 연결까지 간 콜들의 패턴 분석}

### 실패/이탈 분석
{고객이 조기 종료하거나 BANT 미완료된 콜의 패턴 분석}

## Anomalies & Alerts
{이상치, 급격한 변화, 주의가 필요한 패턴}

## Orchestrator Notes
{오케스트레이터의 분석 소견 — Phase 2에서 개선 제안으로 확장}

---
*Generated by HMCA Agent Monitoring System*
```

#### 5.3 On-demand Report 템플릿

```markdown
---
date: {YYYY-MM-DD}
agent: h-voice-call
type: report
period: {start_date} ~ {end_date}
requested_by: {user}
generated_at: {ISO timestamp}
---

# {Report Title}
> Period: {start_date} ~ {end_date}

## Executive Summary
{3-5줄 핵심 요약}

## Trend Analysis
{기간 내 주요 지표 추이}

## Key Findings
{데이터에서 발견한 주요 인사이트}

## Comparison
{이전 동일 기간 대비, 또는 기준치 대비 비교}

## Recommendations
{데이터 기반 개선 권장사항}

---
*Generated by HMCA Agent Monitoring System*
```

---

### 6. 시스템 아키텍처 (Phase 1 구현)

> 개념과 프로토콜이 핵심이며, 아래 테크 스택은 현재 HMCA 환경(GCP)에 맞춘 구현 방안이다. 법인/환경이 다르면 Notion, PostgreSQL 등으로 대체 가능.

#### 6.1 아키텍처 다이어그램

```
[팀원]
  │
  ▼
┌─ Cloud Run ──────────────────────────────────────┐
│  Next.js Viewer (Notion/Obsidian 스타일 UI)       │
│  - 마크다운 렌더링 (react-markdown + remark-gfm)   │
│  - 폴더 트리 네비게이션 (GCS 구조 기반)             │
│  - On-demand 리포트 생성 (BQ + Gemini 직접 호출)    │
│  - QMD 시맨틱 검색 (text-embedding-005)            │
└────────┬─────────────────────────────────────────┘
         │ reads
    ┌────┴─────────────┐
    ▼                  ▼
┌─ GCS ──────────┐  ┌─ Cloud Functions (Python) ──────────┐
│ *.md files     │◀─│  - BigQuery 쿼리 (hvoice 테이블)     │
│ index/         │◀─│  - Gemini 마크다운 생성               │
│  embeddings.json│  │  - text-embedding-005 임베딩 생성     │
└────────────────┘  │  - GCS 저장 + 인덱스 업데이트          │
                    └──────────┬──────────────────────────┘
                               ▲
                        ┌──────┴──────┐
                        │ Cloud       │ ← Daily cron (07:00)
                        │ Scheduler   │
                        └─────────────┘
```

#### 6.2 기술 스택

| 구분 | 선택 | 비고 |
|------|------|------|
| 데이터 소스 | BigQuery | 기존 H-Voice 로그 테이블 (hvoice) |
| 오케스트레이션 | Cloud Scheduler + Cloud Functions (Python) | Daily cron + Pipeline |
| AI (리포트 생성) | Vertex AI (Gemini) | `gemini-3.1-flash-lite-preview`, Temperature 0.3 |
| AI (시맨틱 검색) | Vertex AI Embeddings | `text-embedding-005`, 768차원, ~$0.10/1M tokens |
| 마크다운 저장 | Google Cloud Storage (GCS) | 버전 관리 자동, 저비용 |
| 뷰어 | Next.js on Cloud Run | Tailwind + shadcn/ui, Notion/Obsidian 스타일 |
| 접근 제어 | Phase 2에서 IAP + Global LB 추가 예정 | Phase 1은 `--allow-unauthenticated` |

#### 6.3 GCS 폴더 구조

```
hmca-agent-logs/
├── daily/
│   └── h-voice/
│       └── 2026/03/2026-03-25.md
├── reports/
│   └── h-voice/
│       └── 2026-03-25_weekly-bant-analysis.md
├── index/
│   └── embeddings.json          ← 시맨틱 검색 벡터 인덱스
└── templates/
    ├── daily-log.md
    └── report.md
```

#### 6.4 QMD 시맨틱 검색

> 마크다운 파일을 구조화하여 벡터 임베딩 기반의 의미적 검색을 지원한다.

**인덱싱 파이프라인** (Cloud Function 내):
1. Daily Log / Report 생성 시 자동 실행
2. 마크다운을 `##` 헤더 기준으로 섹션 청킹 (frontmatter 별도 청크)
3. 긴 섹션(>500자)은 ~400자 단위로 서브 청킹 (50자 오버랩)
4. 각 청크를 `text-embedding-005` (`RETRIEVAL_DOCUMENT`)로 임베딩
5. `index/embeddings.json`에 누적 저장 (upsert)

**검색 흐름** (Next.js Viewer):
1. 사용자 쿼리를 `text-embedding-005` (`RETRIEVAL_QUERY`)로 임베딩
2. 인덱스의 모든 청크와 cosine similarity 계산
3. 파일별 최고 점수 기준으로 정렬, 상위 K개 반환
4. 인덱스 미존재 시 키워드 검색으로 자동 폴백
5. UI에서 Semantic/Keyword 모드 토글 가능

**비용**: 연간 ~365파일 기준 임베딩 비용 $0.05 미만 (사실상 무료)

---

### 7. 구현 로드맵

#### Phase 1: H-Voice 모니터링 MVP (~ 다음 주 초) ✅ 구현 완료

| # | 태스크 | 산출물 | 상태 |
|---|--------|--------|------|
| 1 | H-Voice BigQuery 연동 + 로그 매핑 | `bq_client.py`, `mapper.py` (Session/Event 프로토콜) | ✅ |
| 2 | Cloud Functions 파이프라인 (BQ → Gemini → GCS) | `main.py` — Daily .md 자동 생성 | ✅ |
| 3 | Next.js 뷰어 (Notion/Obsidian 스타일) | 폴더 트리, 마크다운 렌더링, Cloud Run 배포 | ✅ |
| 4 | On-demand 리포트 생성 | 날짜/지표 선택 → Gemini → GCS 저장 | ✅ |
| 5 | QMD 시맨틱 검색 | text-embedding-005 기반, 키워드 폴백 | ✅ |
| 6 | 배포 스크립트 | Cloud Function, Cloud Run, Cloud Scheduler | ✅ |

#### Phase 1.5: GCP 연결 (잔여 작업)

| # | 태스크 | 비고 |
|---|--------|------|
| 1 | GCS 버킷 생성 | `infra/setup.sh` 실행 |
| 2 | BigQuery hvoice 테이블 스키마 확인 | `mapper.py` 컬럼 상수 조정 |
| 3 | 서비스 계정 권한 설정 | CF/CR SA 생성 + IAM 바인딩 |
| 4 | 배포 + E2E 테스트 | 파이프라인 수동 실행 → 뷰어 확인 |
| 5 | 안재웅 책임 프로토타입 리뷰 | 피드백 수집 |

#### Phase 2: 피드백 루프 + 확장

| # | 태스크 | 비고 |
|---|--------|------|
| 1 | IAP + Global LB 접근 제어 | 팀원만 접근 가능 |
| 2 | 오케스트레이터 피드백 기능 추가 | 개선 제안 마크다운 생성 |
| 3 | 코칭 에이전트 검토 | 추가 컨텍스트 필요 여부에 따라 |
| 4 | 자체 빌드 에이전트 A2A 프로토콜 적용 | 개발 시점부터 반영 |

---

### 8. 접근 제어 (IAP)

- **Global External Application Load Balancer** → Cloud Run 앞단
- **IAP 활성화** → 허용된 Google 계정만 통과
- **설정**: Cloud Run `--no-allow-unauthenticated` + LB 전용 인그레스
- **비용**: IAP 무료, LB ~$18/월, Cloud Run 요청 기반 과금

---

### 9. 비용 추정 (월간)

| 항목 | 예상 비용 | 비고 |
|------|----------|------|
| BigQuery (쿼리) | $1-5 | Daily + On-demand 쿼리 |
| Cloud Functions | $0-1 | 무료 티어 |
| Vertex AI (Gemini) | $3-10 | gemini-3.1-flash-lite-preview |
| Vertex AI (Embeddings) | < $0.01 | text-embedding-005, 사실상 무료 |
| GCS | < $1 | 마크다운 + 인덱스 |
| Cloud Run | $0-5 | 요청 기반 과금 |
| **합계 (Phase 1)** | **~$5-22/월** | IAP/LB 제외 |
| Load Balancer (Phase 2) | ~$18 | Phase 2에서 IAP 추가 시 |

---

### 10. 고려 사항 & 향후 확장

#### 10.1 Vapi 제약과 자체 에이전트 전략
- **현재**: Vapi는 외부 SaaS이므로 A2A 프로토콜 직접 적용 불가. GCP 적재 데이터 기반의 간접 모니터링으로 시작
- **향후**: 자체 빌드 에이전트 구축 시 **개발 시점부터 A2A 프로토콜을 반영**하여 에이전트 간 직접 통신(로그 공유, 피드백 수신, 설정 변경)이 가능하도록 설계
- **전환점**: 자체 에이전트가 A2A를 지원하면, 오케스트레이터의 피드백이 자동으로 서브 에이전트에 반영되는 완전한 피드백 루프 구현 가능

#### 10.2 프로토콜의 범용성
- 본 문서에서 정의한 로깅 프로토콜(세션 → 이벤트 구조)과 커뮤니케이션 프로토콜(마크다운 + 메타데이터)은 H-Voice에 국한되지 않음
- 어떤 에이전트든 동일한 프로토콜을 적용하면 오케스트레이터가 모니터링·분석·피드백 가능
- 에이전트 추가 시 GCS 폴더 구조를 `daily/{agent_name}/`으로 확장하면 됨

#### 10.3 마크다운 효용 & QMD
- **QMD(Query Markdown) 구현 완료**: `text-embedding-005` 기반 시맨틱 검색으로 마크다운 파일을 의미 기반으로 쿼리 가능
- 인덱싱: 마크다운 → 섹션 청킹 → 벡터 임베딩 → GCS JSON 인덱스
- 검색: 쿼리 임베딩 → cosine similarity → 파일별 최적 매칭
- 키워드 검색 폴백 지원, UI에서 모드 토글 가능
- 문서 간 내부 링크를 활용한 그래프 구조는 Graph RAG 등의 고급 정보 검색에도 활용 가능

---

### 다음 단계
1. **GCS 버킷 생성 + BigQuery 스키마 확인** — `infra/setup.sh` 실행, hvoice 테이블 컬럼 매핑
2. **GCP 배포** — Cloud Function, Cloud Run, Cloud Scheduler 배포
3. **E2E 테스트** — 파이프라인 수동 실행 → Daily Log 생성 → 뷰어 확인 → 시맨틱 검색 테스트
4. **안재웅 책임 프로토타입 리뷰** — 프로토타입 기반으로 피드백 수집