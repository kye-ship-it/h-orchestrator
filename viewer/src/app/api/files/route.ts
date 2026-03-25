import { type NextRequest } from 'next/server';
import { listFileTree } from '@/lib/gcs';

export const revalidate = 60;

export async function GET(request: NextRequest) {
  try {
    const prefix = request.nextUrl.searchParams.get('prefix') ?? undefined;
    const tree = await listFileTree(prefix);

    return Response.json(tree, {
      headers: {
        'Cache-Control': 'public, s-maxage=60, stale-while-revalidate=30',
      },
    });
  } catch (error) {
    console.error('GET /api/files error:', error);
    return Response.json(
      { error: 'Failed to list files' },
      { status: 500 }
    );
  }
}
