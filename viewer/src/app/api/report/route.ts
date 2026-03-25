import { BigQuery } from '@google-cloud/bigquery';
import { generateReport } from '@/lib/gemini';
import { writeFile } from '@/lib/gcs';
import type { ReportParams } from '@/lib/types';

const GCP_PROJECT = process.env.GCP_PROJECT ?? 'dl-cx-sync';

export async function POST(request: Request) {
  let params: ReportParams;
  try {
    params = await request.json();
  } catch {
    return Response.json(
      { error: 'Invalid JSON body' },
      { status: 400 }
    );
  }

  // Validate required fields
  const { startDate, endDate, title, metrics, reportType } = params;
  if (!startDate || !endDate || !title || !reportType) {
    return Response.json(
      {
        error:
          'Missing required fields: startDate, endDate, title, reportType',
      },
      { status: 400 }
    );
  }

  if (!Array.isArray(metrics) || metrics.length === 0) {
    return Response.json(
      { error: 'metrics must be a non-empty array of strings' },
      { status: 400 }
    );
  }

  // Validate date format (YYYY-MM-DD)
  const dateRegex = /^\d{4}-\d{2}-\d{2}$/;
  if (!dateRegex.test(startDate) || !dateRegex.test(endDate)) {
    return Response.json(
      { error: 'Dates must be in YYYY-MM-DD format' },
      { status: 400 }
    );
  }

  try {
    // Query BigQuery for data in the date range
    const data = await queryBigQuery(params);

    // Generate report with Gemini
    const content = await generateReport(params, data);

    // Build the GCS path
    const titleSlug = title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '');
    const path = `reports/h-voice/${startDate}_${titleSlug}.md`;

    // Save to GCS
    await writeFile(path, content);

    return Response.json({ content, path }, { status: 201 });
  } catch (error) {
    console.error('POST /api/report error:', error);
    const message =
      error instanceof Error ? error.message : 'Report generation failed';
    return Response.json({ error: message }, { status: 500 });
  }
}

/**
 * Query BigQuery for metrics data within the specified date range.
 * Returns the results as a formatted text string for Gemini consumption.
 */
async function queryBigQuery(params: ReportParams): Promise<string> {
  let bigquery: BigQuery;
  try {
    bigquery = new BigQuery({ projectId: GCP_PROJECT });
  } catch {
    console.warn(
      'BigQuery not configured. Returning placeholder data.'
    );
    return `[No BigQuery data available - service not configured]\nDate range: ${params.startDate} to ${params.endDate}\nRequested metrics: ${params.metrics.join(', ')}`;
  }

  const metricsFilter = params.metrics
    .map((m) => `'${m.replace(/'/g, "\\'")}'`)
    .join(', ');

  const query = `
    SELECT *
    FROM \`${GCP_PROJECT}.h_voice.daily_metrics\`
    WHERE date BETWEEN @startDate AND @endDate
      AND metric_name IN (${metricsFilter})
    ORDER BY date DESC, metric_name
    LIMIT 10000
  `;

  try {
    const [rows] = await bigquery.query({
      query,
      params: {
        startDate: params.startDate,
        endDate: params.endDate,
      },
    });

    if (!rows || rows.length === 0) {
      return `No data found for the specified date range (${params.startDate} to ${params.endDate}) and metrics (${params.metrics.join(', ')}).`;
    }

    // Format rows as a readable text table for Gemini
    const headers = Object.keys(rows[0]);
    const lines: string[] = [headers.join('\t')];
    for (const row of rows) {
      lines.push(headers.map((h) => String(row[h] ?? '')).join('\t'));
    }

    return lines.join('\n');
  } catch (error) {
    console.error('BigQuery query error:', error);
    return `[BigQuery query failed]\nDate range: ${params.startDate} to ${params.endDate}\nRequested metrics: ${params.metrics.join(', ')}\nError: ${error instanceof Error ? error.message : 'Unknown error'}`;
  }
}
