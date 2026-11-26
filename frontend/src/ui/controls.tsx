import type { ReactNode } from 'react'

interface SegmentedProps<T extends string> {
  label: string
  options: readonly (readonly [T, string])[]
  value: T
  onChange: (value: T) => void
}

/** A two-or-more option toggle; the active option is the white raised segment. */
export function Segmented<T extends string>({ label, options, value, onChange }: SegmentedProps<T>) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map(([id, text]) => (
        <button key={id} type="button" aria-pressed={value === id} onClick={() => onChange(id)}>
          {text}
        </button>
      ))}
    </div>
  )
}

export function Wordmark({ large = false, onClick }: { large?: boolean; onClick?: () => void }) {
  const content = (
    <>
      <span className="wordmark-grid" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>
      <span className="wordmark-text">slip</span>
    </>
  )
  const className = large ? 'wordmark wordmark-lg' : 'wordmark'
  return onClick ? (
    <button type="button" className={className} onClick={onClick} aria-label="slip home page">
      {content}
    </button>
  ) : (
    <span className={className}>{content}</span>
  )
}

/** Inline error message (role=alert) used by every view. */
export function ErrorText({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="alert">
      {children}
    </p>
  )
}
