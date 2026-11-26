import { useState, type DragEvent, type FormEvent } from 'react'
import { api, errorMessage, type Job } from '../../api/client'
import { JobStatus } from './JobStatus'

interface Props {
  onImported: () => void
  maxMegabytes?: number
  pollIntervalMs?: number
}

/** Upload PDF tab of "Add papers" (FR-03): drop zone or browse, optional title, size check before sending. */
export function UploadForm({ onImported, maxMegabytes = 50, pollIntervalMs = 1000 }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState('')
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [dragging, setDragging] = useState(false)

  function drop(event: DragEvent) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files[0]
    if (dropped) setFile(dropped)
  }

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
    <form onSubmit={submit} className="stack">
      <label
        htmlFor="upload-file"
        className={dragging ? 'dropzone is-dragging' : 'dropzone'}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <span className="dropzone-title">{file ? file.name : 'Drop a PDF here'}</span>
        <span className="faint small" id="upload-help">
          or <span className="link-ish">browse</span> · up to {maxMegabytes} MB · text-based PDFs only (scans are rejected, no
          OCR)
        </span>
        <input
          id="upload-file"
          type="file"
          className="sr-only"
          accept="application/pdf,.pdf"
          aria-label="PDF file"
          aria-describedby="upload-help"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
      </label>
      <label htmlFor="upload-title" className="field-label">
        Title (optional)
      </label>
      <input
        id="upload-title"
        className="text-input"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        maxLength={300}
        placeholder="Defaults to the PDF's embedded title or file name"
      />
      <button type="submit" className="btn btn-dark" disabled={submitting || !file}>
        {submitting ? 'Uploading…' : 'Upload'}
      </button>
      {error && (
        <p role="alert" className="alert">
          {error}
        </p>
      )}
      {job && (
        <JobStatus key={job.id} job={job} pollIntervalMs={pollIntervalMs} onFinished={(done) => done.state === 'ready' && onImported()} />
      )}
    </form>
  )
}
