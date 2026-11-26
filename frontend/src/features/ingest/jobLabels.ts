import type { Job } from '../../api/client'

export const STATE_LABELS: Record<string, string> = {
  queued: 'Queued',
  fetching: 'Fetching',
  extracting: 'Extracting text',
  chunking: 'Chunking',
  embedding: 'Computing embeddings',
  ready: 'Ready',
  failed: 'Failed',
}

/**
 * How far along the pipeline a job's current stage is, for the progress bar. This reflects the stage only;
 * the backend does not report progress within a stage.
 */
export const STAGE_PROGRESS: Record<string, number> = {
  queued: 8,
  fetching: 25,
  extracting: 45,
  chunking: 65,
  embedding: 85,
  ready: 100,
  failed: 100,
}

export function jobName(job: Job): string {
  return job.display_name ?? job.source_ref
}

/** The newest job per source that still needs attention: running, or failed and not since retried. */
export function jobsNeedingAttention(jobs: Job[]): Job[] {
  const latest = new Map<string, Job>()
  for (const job of jobs) {
    const seen = latest.get(job.source_ref)
    if (!seen || job.created_at > seen.created_at) latest.set(job.source_ref, job)
  }
  return [...latest.values()]
    .filter((job) => job.state !== 'ready')
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
}
