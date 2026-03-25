import { VertexAI } from '@google-cloud/vertexai';
import type { ReportParams } from './types';

const PROJECT = process.env.GCP_PROJECT ?? 'dl-cx-sync';
const LOCATION = process.env.GCP_LOCATION ?? 'us-central1';
const MODEL = process.env.GEMINI_MODEL ?? 'gemini-3.1-flash-lite-preview';

const SYSTEM_PROMPT = `You are a professional report generator for the H-Orchestrator system.
Generate well-structured markdown reports based on the provided data and parameters.

Follow these guidelines:
- Use clear section headings (##, ###) for organization
- Include a summary section at the top
- Present metrics in tables where appropriate
- Use bullet points for key findings
- Add a "Recommendations" section when applicable
- Keep language professional and concise
- Format dates consistently (YYYY-MM-DD)
- Include the report metadata (date range, type, title) in YAML frontmatter`;

let vertexInstance: VertexAI | null = null;

function getVertex(): VertexAI {
  if (vertexInstance) return vertexInstance;
  vertexInstance = new VertexAI({ project: PROJECT, location: LOCATION });
  return vertexInstance;
}

/**
 * Generate an on-demand report using Gemini on Vertex AI.
 *
 * @param params - Report parameters (date range, title, metrics, type)
 * @param data - Raw data to base the report on (e.g., BigQuery results as text)
 * @returns Generated markdown report content
 */
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
  const text =
    response.candidates?.[0]?.content?.parts?.[0]?.text;

  if (!text) {
    throw new Error('Gemini returned an empty response');
  }

  return text;
}

function buildPrompt(params: ReportParams, data: string): string {
  return `Generate a "${params.reportType}" report with the following parameters:

**Title**: ${params.title}
**Date Range**: ${params.startDate} to ${params.endDate}
**Requested Metrics**: ${params.metrics.join(', ')}

**Raw Data**:
\`\`\`
${data}
\`\`\`

Please generate a comprehensive markdown report based on this data. Include YAML frontmatter with the report metadata.`;
}
