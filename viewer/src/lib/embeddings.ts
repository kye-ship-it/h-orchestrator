import { GoogleAuth } from 'google-auth-library';
import type { SearchResult } from './types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EmbeddingChunk {
  section: string;
  text: string;
  embedding: number[];
}

export interface IndexEntry {
  path: string;
  frontmatter: Record<string, string>;
  chunks: EmbeddingChunk[];
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

const GCP_PROJECT = process.env.GCP_PROJECT ?? 'dl-cx-sync';
const GCP_LOCATION = process.env.GCP_LOCATION ?? 'us-central1';
const EMBEDDING_MODEL = 'text-embedding-005';
const INDEX_PATH = 'index/embeddings.json';
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

const USE_MOCK = process.env.USE_MOCK_DATA === 'true' || !process.env.GCS_BUCKET;

// ---------------------------------------------------------------------------
// Index cache
// ---------------------------------------------------------------------------

let cachedIndex: IndexEntry[] | null = null;
let cacheTimestamp = 0;

// ---------------------------------------------------------------------------
// Google Auth for REST API calls
// ---------------------------------------------------------------------------

let authClient: GoogleAuth | null = null;

function getAuth(): GoogleAuth {
  if (!authClient) {
    authClient = new GoogleAuth({
      scopes: ['https://www.googleapis.com/auth/cloud-platform'],
    });
  }
  return authClient;
}

// ---------------------------------------------------------------------------
// Embedding via Vertex AI REST API
// ---------------------------------------------------------------------------

/**
 * Embed a search query using Vertex AI text-embedding-005 with task type
 * RETRIEVAL_QUERY.
 */
export async function embedQuery(query: string): Promise<number[]> {
  if (USE_MOCK) {
    return mockEmbedding();
  }

  const auth = getAuth();
  const client = await auth.getClient();
  const token = await client.getAccessToken();

  const url = `https://${GCP_LOCATION}-aiplatform.googleapis.com/v1/projects/${GCP_PROJECT}/locations/${GCP_LOCATION}/publishers/google/models/${EMBEDDING_MODEL}:predict`;

  const body = {
    instances: [
      {
        content: query,
        task_type: 'RETRIEVAL_QUERY',
      },
    ],
  };

  const response = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(
      `Vertex AI embedding request failed (${response.status}): ${errorText}`
    );
  }

  const data = await response.json();
  const embedding: number[] = data.predictions?.[0]?.embeddings?.values;

  if (!embedding || !Array.isArray(embedding)) {
    throw new Error('Unexpected embedding response structure');
  }

  return embedding;
}

// ---------------------------------------------------------------------------
// Cosine similarity
// ---------------------------------------------------------------------------

/**
 * Compute cosine similarity between two vectors. Returns a value in [-1, 1].
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length) return 0;

  let dot = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  if (denom === 0) return 0;

  return dot / denom;
}

// ---------------------------------------------------------------------------
// Index loading
// ---------------------------------------------------------------------------

/**
 * Load the embedding index from GCS (`index/embeddings.json`). Results are
 * cached in memory for 5 minutes.
 */
export async function loadIndex(): Promise<IndexEntry[] | null> {
  if (USE_MOCK) return null;

  const now = Date.now();
  if (cachedIndex && now - cacheTimestamp < CACHE_TTL_MS) {
    return cachedIndex;
  }

  try {
    const { Storage } = await import('@google-cloud/storage');
    const bucketName = process.env.GCS_BUCKET ?? 'h-gdcx-orchestrator';
    const storage = new Storage();
    const bucket = storage.bucket(bucketName);
    const file = bucket.file(INDEX_PATH);

    const [exists] = await file.exists();
    if (!exists) {
      console.warn(`Embedding index not found at gs://${bucketName}/${INDEX_PATH}`);
      return null;
    }

    const [buffer] = await file.download();
    const entries: IndexEntry[] = JSON.parse(buffer.toString('utf-8'));

    cachedIndex = entries;
    cacheTimestamp = now;

    return entries;
  } catch (error) {
    console.error('Failed to load embedding index:', error);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Semantic search
// ---------------------------------------------------------------------------

/**
 * Perform semantic search against the embedding index.
 *
 * 1. Load the index from GCS
 * 2. Embed the query via Vertex AI
 * 3. Compute cosine similarity against all chunks
 * 4. Group results by file (best chunk score per file)
 * 5. Return top K results (default 20)
 *
 * Returns `null` when the index is unavailable (caller should fall back to
 * keyword search).
 */
export async function semanticSearch(
  query: string,
  topK: number = 20
): Promise<SearchResult[] | null> {
  const index = await loadIndex();
  if (!index || index.length === 0) return null;

  let queryEmbedding: number[];
  try {
    queryEmbedding = await embedQuery(query);
  } catch (error) {
    console.error('Failed to embed query, falling back to keyword search:', error);
    return null;
  }

  // Score every chunk and group by file
  const fileScores = new Map<
    string,
    { entry: IndexEntry; bestScore: number; bestChunk: EmbeddingChunk }
  >();

  for (const entry of index) {
    for (const chunk of entry.chunks) {
      if (!chunk.embedding || chunk.embedding.length === 0) continue;

      const score = cosineSimilarity(queryEmbedding, chunk.embedding);

      const existing = fileScores.get(entry.path);
      if (!existing || score > existing.bestScore) {
        fileScores.set(entry.path, {
          entry,
          bestScore: score,
          bestChunk: chunk,
        });
      }
    }
  }

  // Sort by score descending and take top K
  const sorted = Array.from(fileScores.values())
    .sort((a, b) => b.bestScore - a.bestScore)
    .slice(0, topK);

  return sorted.map(({ entry, bestScore, bestChunk }) => {
    // Extract a readable snippet from the best matching chunk
    const snippet = bestChunk.text.slice(0, 200).replace(/\n+/g, ' ').trim();
    const title =
      entry.frontmatter?.title ??
      entry.path.split('/').pop()?.replace('.md', '') ??
      entry.path;

    return {
      path: entry.path,
      title,
      snippet: snippet + (bestChunk.text.length > 200 ? '...' : ''),
      frontmatter: entry.frontmatter ?? {},
      score: bestScore,
    };
  });
}

// ---------------------------------------------------------------------------
// Check whether the embedding index is available
// ---------------------------------------------------------------------------

/**
 * Returns true if the semantic search index exists and is loadable.
 * Useful for deciding between semantic and keyword search modes.
 */
export async function isIndexAvailable(): Promise<boolean> {
  if (USE_MOCK) return false;
  const index = await loadIndex();
  return index !== null && index.length > 0;
}

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

function mockEmbedding(): number[] {
  const dim = 768;
  const vec = new Array<number>(dim);
  for (let i = 0; i < dim; i++) {
    vec[i] = Math.random() * 2 - 1;
  }
  // Normalize
  const norm = Math.sqrt(vec.reduce((sum, v) => sum + v * v, 0));
  return vec.map((v) => v / norm);
}
