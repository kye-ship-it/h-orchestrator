import { type NextRequest } from 'next/server';
import { searchFiles, resolveSearchMode } from '@/lib/gcs';

const MAX_RESULTS = 50;

export async function GET(request: NextRequest) {
  const q = request.nextUrl.searchParams.get('q');

  if (!q) {
    return Response.json(
      { error: 'Missing required query parameter: q' },
      { status: 400 }
    );
  }

  const prefix = request.nextUrl.searchParams.get('prefix') ?? undefined;
  const modeParam = request.nextUrl.searchParams.get('mode');
  const requestedMode: 'semantic' | 'keyword' =
    modeParam === 'keyword' ? 'keyword' : 'semantic';

  try {
    const [results, actualMode] = await Promise.all([
      searchFiles(q, prefix, requestedMode),
      resolveSearchMode(requestedMode),
    ]);

    return Response.json({
      results: results.slice(0, MAX_RESULTS),
      mode: actualMode,
    });
  } catch (error) {
    console.error('GET /api/search error:', error);
    return Response.json(
      { error: 'Search failed' },
      { status: 500 }
    );
  }
}
