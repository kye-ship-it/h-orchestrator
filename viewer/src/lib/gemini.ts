import { VertexAI } from '@google-cloud/vertexai';
import type { ReportParams } from './types';

const PROJECT = process.env.GCP_PROJECT ?? 'hyundai-bi-agent-dev';
const LOCATION = process.env.GEMINI_LOCATION ?? 'asia-northeast3';
const MODEL = process.env.GEMINI_MODEL ?? 'gemini-2.5-flash';

const SYSTEM_PROMPT = `당신은 H-Voice 콜 에이전트 시스템의 AI 운영 분석가입니다.
제공된 Daily Log 데이터 또는 BigQuery 집계 데이터를 기반으로 분석 리포트를 생성합니다.

작성 규칙:
- 기본 언어는 한글이며, 주요 지표명(Acceptance Rate, Qualification Rate 등)은 영문으로 유지합니다.
- Executive Summary를 반드시 포함하세요.
- 테이블, 추이 분석, 세그먼트 비교를 활용하세요.
- 개선 권장사항(Recommendations)을 구체적으로 작성하세요.
- 절대 코드 펜스(\`\`\`)로 감싸지 마세요. 순수 마크다운만 출력하세요.
- 절대 이미지 태그(![...](url))를 사용하지 마세요. 차트나 그래프 대신 테이블로 표현하세요.
- 반드시 ---로 시작하는 YAML frontmatter를 포함하세요.
- 딜러별 분석은 상위 10개까지만 표시하세요. "외 N개" 같은 생략 표기를 사용하세요.
- 데이터가 (중략)되거나 잘린 듯한 표현을 사용하지 마세요.`;

let vertexInstance: VertexAI | null = null;

function getVertex(): VertexAI {
  if (vertexInstance) return vertexInstance;
  vertexInstance = new VertexAI({ project: PROJECT, location: LOCATION });
  return vertexInstance;
}

export async function generateReport(
  params: ReportParams,
  data: string
): Promise<string> {
  const vertex = getVertex();

  const model = vertex.getGenerativeModel({
    model: MODEL,
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 8192,
    },
    systemInstruction: {
      role: 'system',
      parts: [{ text: SYSTEM_PROMPT }],
    },
  });

  const userPrompt = buildPrompt(params, data);

  const result = await model.generateContent({
    contents: [
      {
        role: 'user',
        parts: [{ text: userPrompt }],
      },
    ],
  });

  const response = result.response;
  const text = response.candidates?.[0]?.content?.parts?.[0]?.text;

  if (!text) {
    throw new Error('Gemini returned an empty response');
  }

  return text;
}

function detectAggregationUnit(startDate: string, endDate: string): { unit: string; instruction: string } {
  const start = new Date(startDate);
  const end = new Date(endDate);
  const days = Math.round((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1;

  if (days <= 7) {
    return { unit: 'daily', instruction: '일별로 데이터를 표시하세요.' };
  } else if (days <= 31) {
    return { unit: 'weekly', instruction: '주 단위(Week 1, Week 2...)로 집계하여 표시하세요. 일별 테이블은 만들지 마세요.' };
  } else if (days <= 90) {
    return { unit: 'weekly', instruction: '주 단위로 집계하여 표시하세요. 일별 테이블은 만들지 마세요.' };
  } else {
    return { unit: 'monthly', instruction: '월 단위로 집계하여 표시하세요. 주별/일별 테이블은 만들지 마세요.' };
  }
}

function buildPrompt(params: ReportParams, data: string): string {
  const now = new Date().toISOString();
  const { unit, instruction } = detectAggregationUnit(params.startDate, params.endDate);

  return `H-Voice 분석 리포트를 생성하세요.

---
date: ${new Date().toISOString().split('T')[0]}
agent: h-voice-call
type: report
period: ${params.startDate} ~ ${params.endDate}
requested_by: user
generated_at: ${now}
---

**리포트 제목**: ${params.title}
**분석 기간**: ${params.startDate} ~ ${params.endDate}
**리포트 유형**: ${params.reportType}
**요청 지표**: ${params.metrics.join(', ')}
**집계 단위**: ${unit} — ${instruction}

중요 규칙:
- 추이 테이블은 반드시 ${unit} 단위로 집계하세요.
- 딜러별 분석은 상위 10개까지만 표시하고 "외 N개 딜러" 형태로 요약하세요.
- 이미지(![...])를 절대 포함하지 마세요. 차트 대신 테이블을 사용하세요.
- 모든 테이블의 헤더와 구분선(|---|)의 컬럼 수를 반드시 맞추세요.

아래는 해당 기간의 데이터입니다:

${data}

위 데이터를 기반으로 다음 섹션을 포함하는 리포트를 작성하세요:
1. Executive Summary (3~5줄)
2. 기간 요약 (Period Overview) — 핵심 지표 + 이전 동일 기간 대비
3. ${unit === 'daily' ? '일별' : unit === 'weekly' ? '주별' : '월별'} 추이 (Trend)
4. 퍼널 분석 (Funnel Analysis) — 단계별 전환율 + 이탈 사유
5. 세그먼트 분석 — 차종별, 채널별, 딜러별(상위 10) 성과
6. 주요 발견 (Key Findings)
7. 개선 권장사항 (Recommendations)`;
}
