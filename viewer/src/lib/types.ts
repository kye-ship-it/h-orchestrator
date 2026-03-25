export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  children?: FileNode[];
}

export interface SearchResult {
  path: string;
  title: string;
  snippet: string;
  frontmatter: Record<string, string>;
  score: number;
}

export interface ReportParams {
  startDate: string;
  endDate: string;
  title: string;
  metrics: string[];
  reportType: string;
}

export interface DailyLogFrontmatter {
  date: string;
  agent: string;
  type: string;
  generated_at: string;
  [key: string]: string;
}

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

export type SearchMode = 'semantic' | 'keyword';

export interface SearchResponse {
  results: SearchResult[];
  mode: SearchMode;
}
