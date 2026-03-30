import { BigQuery } from '@google-cloud/bigquery';
import { generateReport } from '@/lib/gemini';
import { writeFile, readFile } from '@/lib/gcs';
import type { ReportParams } from '@/lib/types';

const GCP_PROJECT = process.env.GCP_PROJECT ?? 'hyundai-bi-agent-dev';
const BQ_META = process.env.BQ_META_TABLE ?? 'dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_meta';
const BQ_ANALYSIS = process.env.BQ_ANALYSIS_TABLE ?? 'dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_analysis';
const BQ_LEAD = process.env.BQ_LEAD_TABLE ?? 'dl-cx-sync.HQ_DW_PRD.ods_hmb_hvoice_lead';

export async function POST(request: Request) {
  let params: ReportParams;
  try {
    params = await request.json();
  } catch {
    return Response.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { startDate, endDate, title, reportType } = params;
  if (!startDate || !endDate || !title || !reportType) {
    return Response.json(
      { error: 'Missing required fields: startDate, endDate, title, reportType' },
      { status: 400 }
    );
  }

  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
    return Response.json({ error: 'Dates must be in YYYY-MM-DD format' }, { status: 400 });
  }

  try {
    // Strategy: use existing daily logs if available, fall back to BQ
    // For long periods (>14 days), extract only metrics sections to stay efficient
    const dailyLogs = await collectDailyLogs(startDate, endDate);
    let data: string;

    if (dailyLogs.length > 0) {
      const dayCount = dailyLogs.length;
      if (dayCount > 14) {
        data = dailyLogs.map((log) => extractMetrics(log)).join('\n\n---\n\n');
      } else {
        data = dailyLogs.join('\n\n---\n\n');
      }
    } else {
      data = await queryBigQuery(startDate, endDate);
    }

    const content = await generateReport(params, data);

    const titleSlug = title
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, '-')
      .replace(/(^-|-$)/g, '');
    const path = `reports/h-voice/${startDate}_${endDate}_${titleSlug}.md`;

    await writeFile(path, content);

    return Response.json({ content, path }, { status: 201 });
  } catch (error) {
    console.error('POST /api/report error:', error);
    const message = error instanceof Error ? error.message : 'Report generation failed';
    return Response.json({ error: message }, { status: 500 });
  }
}

function extractMetrics(log: string): string {
  // Extract frontmatter + sections 1-4 (funnel, qualification, performance, insights)
  // Drop sections 5-6 (anomalies detail, orchestrator notes) and individual call summaries
  const sections = log.split(/^## /m);
  const kept: string[] = [];

  for (const section of sections) {
    // Keep frontmatter + title + executive summary
    if (!section.startsWith('5.') && !section.startsWith('6.')) {
      kept.push(section);
    }
  }

  return kept.join('## ').trim();
}

async function collectDailyLogs(startDate: string, endDate: string): Promise<string[]> {
  const logs: string[] = [];
  const current = new Date(startDate);
  const end = new Date(endDate);

  while (current <= end) {
    const dateStr = current.toISOString().split('T')[0];
    const path = `daily/h-voice/hmb/${dateStr}.md`;
    const content = await readFile(path);
    if (content) {
      logs.push(content);
    }
    current.setDate(current.getDate() + 1);
  }

  return logs;
}

async function queryBigQuery(startDate: string, endDate: string): Promise<string> {
  let bigquery: BigQuery;
  try {
    bigquery = new BigQuery({ projectId: GCP_PROJECT, location: 'asia-northeast3' });
  } catch {
    return `[BigQuery not configured]\nDate range: ${startDate} to ${endDate}`;
  }

  const query = `
    SELECT
      DATE(m.call_created_at, 'America/Sao_Paulo') AS call_date,
      COUNT(*) AS total_calls,
      COUNTIF(a.voicemail = true) AS voicemail_count,
      COUNTIF(a.hung_up = true) AS hungup_count,
      COUNTIF(a.voicemail = false AND a.hung_up = false) AS connected_count,
      COUNTIF(a.type = 'accepted') AS accepted_count,
      COUNTIF(a.dealer_consent = 'yes') AS consent_count,
      COUNTIF(a.test_drive_slot IS NOT NULL AND a.test_drive_slot != '' AND LOWER(a.test_drive_slot) NOT IN ('not informed', 'não informado')) AS testdrive_count,
      ROUND(AVG(m.call_duration), 1) AS avg_duration,
      m.model_of_interest,
      m.channel
    FROM \`${BQ_META}\` m
    LEFT JOIN \`${BQ_ANALYSIS}\` a ON m.call_id = a.call_id
    WHERE DATE(m.call_created_at, 'America/Sao_Paulo') BETWEEN @startDate AND @endDate
    GROUP BY call_date, m.model_of_interest, m.channel
    ORDER BY call_date, total_calls DESC
  `;

  try {
    const [rows] = await bigquery.query({
      query,
      params: { startDate, endDate },
    });

    if (!rows || rows.length === 0) {
      return `No data found for ${startDate} to ${endDate}.`;
    }

    const headers = Object.keys(rows[0]);
    const lines: string[] = [headers.join('\t')];
    for (const row of rows) {
      lines.push(headers.map((h) => String((row as Record<string, unknown>)[h] ?? '')).join('\t'));
    }
    return lines.join('\n');
  } catch (error) {
    console.error('BigQuery query error:', error);
    return `[BigQuery query failed]\nDate range: ${startDate} to ${endDate}\nError: ${error instanceof Error ? error.message : 'Unknown error'}`;
  }
}
