# H-Orchestrator Task List

## Context
H-Voice 콜 에이전트 로그를 모니터링하고 리포팅하는 오케스트레이터 시스템 MVP 구축.
BigQuery 적재 데이터 → Gemini 분석 → 마크다운 리포트 생성 → Next.js 뷰어 제공.

## Key Decisions
- **GCP Project**: dl-cx-sync
- **Gemini Model**: gemini-3.1-flash-lite-preview (Vertex AI)
- **UI**: Tailwind + shadcn/ui (미니멀)
- **On-demand 리포트**: Node.js에서 BQ + Gemini 직접 호출
- **검색**: QMD 시맨틱 검색 (Vertex AI text-embedding-005, 768차원, GCS 인덱스)
- **IAP**: Phase 2에서 추가

---

## Phase 1: 프로젝트 초기화 ✅

- [x] `.gitignore` 생성
- [x] `pipeline/` 스캐폴딩 (requirements.txt, config.py)
- [x] `pipeline/templates/daily-log.md` 작성
- [x] `pipeline/templates/report.md` 작성
- [x] `viewer/` Next.js 프로젝트 초기화 (App Router, TypeScript, Tailwind, shadcn/ui)
- [x] `infra/setup.sh` — GCS 버킷 생성 스크립트

## Phase 2: BigQuery 연동 ✅

- [x] `pipeline/bq_client.py` — hvoice 테이블 쿼리 (INFORMATION_SCHEMA 자동 탐색)
- [x] `pipeline/mapper.py` — Session/Event/DailyMetrics 데이터클래스 + 매핑 로직
- [x] `pipeline/tests/test_mapper.py` — 매퍼 유닛 테스트 (36 tests)

## Phase 3: Gemini 리포트 생성 파이프라인 ✅

- [x] `pipeline/gemini_client.py` — Vertex AI Gemini 리포트 생성
- [x] `pipeline/gcs_client.py` — GCS 읽기/쓰기 (경로: `daily/h-voice/YYYY/MM/YYYY-MM-DD.md`)
- [x] `pipeline/main.py` — Cloud Function 엔트리포인트 (BQ → 매핑 → Gemini → GCS)
- [x] `pipeline/tests/test_gemini_client.py`
- [x] `pipeline/tests/test_gcs_client.py` (16 tests)

## Phase 4: Next.js 뷰어 코어 ✅

- [x] `viewer/src/lib/gcs.ts` — GCS SDK 래퍼
- [x] `viewer/src/lib/types.ts` — 공유 타입 정의
- [x] `viewer/src/app/api/files/route.ts` — 폴더 트리 API
- [x] `viewer/src/app/api/file/route.ts` — .md 파일 읽기 API
- [x] `viewer/src/components/Sidebar.tsx` + `FolderTree.tsx` — 폴더 트리 네비게이션
- [x] `viewer/src/components/MarkdownRenderer.tsx` — react-markdown + remark-gfm
- [x] `viewer/src/app/layout.tsx` — 사이드바 레이아웃
- [x] `viewer/src/app/page.tsx` — 대시보드
- [x] `viewer/src/app/logs/[...slug]/page.tsx` — 마크다운 뷰어

## Phase 5: 검색 & On-demand 리포트 ✅

- [x] `viewer/src/app/api/search/route.ts` — QMD 검색 API (semantic/keyword 모드 지원)
- [x] `viewer/src/app/search/page.tsx` — 검색 UI (모드 토글 배지)
- [x] `viewer/src/lib/gemini.ts` — Gemini API 래퍼 (Node.js, Vertex AI)
- [x] `viewer/src/lib/embeddings.ts` — 시맨틱 검색 (text-embedding-005, cosine similarity)
- [x] `viewer/src/app/api/report/route.ts` — On-demand 리포트 생성 API
- [x] `viewer/src/app/reports/generate/page.tsx` — 리포트 생성 UI

## Phase 5.5: Embedding Pipeline ✅

- [x] `pipeline/embedding_client.py` — 마크다운 청킹 + text-embedding-005 임베딩
- [x] `pipeline/search_index.py` — GCS 기반 임베딩 인덱스 관리 (CRUD + rebuild)
- [x] `pipeline/main.py` — 리포트 생성 후 인덱스 자동 업데이트 + rebuild 엔드포인트
- [x] `pipeline/tests/test_embedding_client.py` — 임베딩 클라이언트 테스트 (26 tests)

## Phase 6: 배포

- [x] `viewer/Dockerfile`
- [x] `infra/deploy-pipeline.sh` — Cloud Function 배포
- [x] `infra/deploy-viewer.sh` — Cloud Run 배포
- [x] `infra/scheduler.sh` — Cloud Scheduler (매일 오전 7시)
- [ ] 서비스 계정 권한 설정
- [ ] E2E 테스트
