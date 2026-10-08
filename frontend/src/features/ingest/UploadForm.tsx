import { useState, type FormEvent } from 'react'
import { api, errorMessage, type Job } from '../../api/client'
import { JobStatus } from './JobStatus'

interface Props {
  onImported: () => void
  maxMegabytes?: number
  pollIntervalMs?: number
}

export function UploadForm({ onImported, maxMegabytes = 50, pollIntervalMs = 1000 }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!file) return
    setError(null)
    if (file.size > maxMegabytes * 1024 * 1024) {
      setError(`File is larger than the ${maxMegabytes} MB limit`)
      return
    }
    setSubmitting(true)
    try {
      setJob(await api.upload(file, title))
    } catch (err) {
      setJob(null)
      setError(errorMessage(err))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section aria-labelledby="upload-heading" className="card">
      <h2 id="upload-heading">Upload a PDF</h2>
      <p className="muted small" id="upload-help">
        Text-based PDFs up to {maxMegabytes} MB. Scanned PDFs are rejected (no OCR).
      </p>
      <form onSubmit={submit} className="stack-form">
        <label htmlFor="upload-file">PDF file</label>
        <input
          id="upload-file"
          type="file"
          accept="application/pdf,.pdf"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          aria-describedby="upload-help"
        />
        <label htmlFor="upload-title">Title (optional)</label>
        <input
          id="upload-title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          maxLength={300}
          placeholder="Defaults to the PDF's embedded title or file name"
        />
        <button type="submit" disabled={submitting || !file}>
          {submitting ? 'Uploading…' : 'Upload'}
        </button>
      </form>
      {error && (
        <p role="alert" className="status-error">
          {error}
        </p>
      )}
      {job && (
        <JobStatus
          key={job.id}
          job={job}
          pollIntervalMs={pollIntervalMs}
          onFinished={(done) => done.state === 'ready' && onImported()}
        />
      )}
    </section>
  )
}
