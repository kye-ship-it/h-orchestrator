import { type NextRequest } from 'next/server';
import { readFile, writeFile } from '@/lib/gcs';

export async function GET(request: NextRequest) {
  const path = request.nextUrl.searchParams.get('path');

  if (!path) {
    return Response.json(
      { error: 'Missing required query parameter: path' },
      { status: 400 }
    );
  }

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

export async function PUT(request: NextRequest) {
  try {
    const body = await request.json();
    const { path, content } = body;

    if (!path || typeof content !== 'string') {
      return Response.json(
        { error: 'Missing required fields: path, content' },
        { status: 400 }
      );
    }

    if (path.includes('..') || path.startsWith('/')) {
      return Response.json(
        { error: 'Invalid path: traversal not allowed' },
        { status: 400 }
      );
    }

    if (!path.endsWith('.md')) {
      return Response.json(
        { error: 'Only .md files can be saved' },
        { status: 400 }
      );
    }

    const savedPath = await writeFile(path, content);

    return Response.json({ path: savedPath, status: 'saved' });
  } catch (error) {
    console.error('PUT /api/file error:', error);
    return Response.json(
      { error: 'Failed to save file' },
      { status: 500 }
    );
  }
}
