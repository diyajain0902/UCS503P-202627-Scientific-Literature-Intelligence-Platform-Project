import type { Job, Paper, SearchResponse } from '../api/client'

// Synthetic fixtures for UI tests only.
export const job = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1',
  kind: 'arxiv_import',
  state: 'queued',
  source_ref: '2101.00001',
  display_name: null,
  paper_id: null,
  error: null,
  attempts: 0,
  created_at: '2026-10-08T00:00:00Z',
  updated_at: '2026-10-08T00:00:00Z',
  finished_at: null,
  ...overrides,
})

export const paper = (overrides: Partial<Paper> = {}): Paper => ({
  id: 'paper-1',
  source: 'arxiv',
  arxiv_id: '2101.00001',
  arxiv_version: 2,
  title: 'Synthetic Paper Title',
  authors: ['A. One', 'B. Two', 'C. Three', 'D. Four'],
  abstract: null,
  categories: ['cs.CL'],
  published_at: null,
  page_count: 12,
  chunk_count: 40,
  created_at: '2026-10-08T00:00:00Z',
  ...overrides,
})

export const searchResponse = (overrides: Partial<SearchResponse> = {}): SearchResponse => ({
  query: 'attention',
  top_k: 10,
  embedding_model: 'sentence-transformers/all-MiniLM-L6-v2',
  took_ms: 12.5,
  results: [
    {
      rank: 1,
      chunk_id: 'chunk-1',
      score: 0.81234,
      rank_score: null,
      text: 'Passage about attention spanning two pages.',
      page_start: 3,
      page_end: 4,
      char_start: 100,
      char_end: 150,
      paper: { id: 'paper-1', title: 'Synthetic Paper Title', arxiv_id: '2101.00001', arxiv_version: 2 },
    },
  ],
  ...overrides,
})
