import { type NextRequest } from 'next/server';
import { readFile } from '@/lib/gcs';

export async function GET(request: NextRequest) {
  const path = request.nextUrl.searchParams.get('path');

  if (!path) {
    return Response.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

  // Prevent path traversal
  if (path.includes('..') || path.startsWith('/')) {
    return Response.json(
      { error: 'Invalid path: traversal not allowed' },
      { status: 400 }
    );
  }

  try {
    const content = await readFile(path);

    if (content === null) {
      return Response.json(
        { error: 'File not found' },
        { status: 404 }
      );
    }

    return Response.json({ content, path });
  } catch (error) {
    console.error(`GET /api/file error for "${path}":`, error);
    return Response.json(
      { error: 'Failed to read file' },
      { status: 500 }
    );
  }
}
