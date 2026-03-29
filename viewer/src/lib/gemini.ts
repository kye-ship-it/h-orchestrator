import { VertexAI } from '@google-cloud/vertexai';
import type { ReportParams } from './types';

const PROJECT = process.env.GCP_PROJECT ?? 'dl-cx-sync';
const LOCATION = process.env.GEMINI_LOCATION ?? 'us-central1';
const MODEL = process.env.GEMINI_MODEL ?? 'gemini-2.5-flash-lite';

const SYSTEM_PROMPT = `당신은 H-Voice 콜 에이전트 시스템의 AI 운영 분석가입니다.
제공된 Daily Log 데이터 또는 BigQuery 집계 데이터를 기반으로 분석 리포트를 생성합니다.

작성 규칙:
- 기본 언어는 한글이며, 주요 지표명(Acceptance Rate, Qualification Rate 등)은 영문으로 유지합니다.
- Executive Summary를 반드시 포함하세요.
- 테이블, 추이 분석, 세그먼트 비교를 활용하세요.
- 개선 권장사항(Recommendations)을 구체적으로 작성하세요.
- 절대 코드 펜스(\`\`\`)로 감싸지 마세요. 순수 마크다운만 출력하세요.
- 반드시 ---로 시작하는 YAML frontmatter를 포함하세요.`;

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

function buildPrompt(params: ReportParams, data: string): string {
  const now = new Date().toISOString();

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

아래는 해당 기간의 데이터입니다:

${data}

위 데이터를 기반으로 다음 섹션을 포함하는 리포트를 작성하세요:
1. Executive Summary
2. 기간 요약 (Period Overview)
3. 일별 추이 (Daily Trend)
4. 퍼널 분석 (Funnel Analysis)
5. 세그먼트 분석 (차종별, 채널별, 딜러별)
6. 주요 발견 (Key Findings)
7. 개선 권장사항 (Recommendations)`;
}
