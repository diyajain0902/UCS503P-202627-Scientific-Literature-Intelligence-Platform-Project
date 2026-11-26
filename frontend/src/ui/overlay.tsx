import { useEffect, useRef, type ReactNode } from 'react'
import { useEscape } from './hooks'

interface OverlayProps {
  kind: 'drawer' | 'modal'
  label: string
  onClose: () => void
  children: ReactNode
}

/** A drawer (right) or modal (centre) dialog over a scrim. Esc and a scrim click close it; focus returns afterwards. */
export function Overlay({ kind, label, onClose, children }: OverlayProps) {
  const panel = useRef<HTMLDivElement>(null)
  useEscape(true, onClose)
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    // Keep focus on an autofocused field inside the panel; otherwise focus the panel itself.
    if (!panel.current?.contains(document.activeElement)) panel.current?.focus()
    return () => previous?.focus()
  }, [])
  return (
    <div className={`overlay overlay-${kind}`}>
      <div className="scrim" data-testid="scrim" onClick={onClose} aria-hidden="true" />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        className={`overlay-panel ${kind}-panel ${kind === 'drawer' ? 'glass-strong' : ''}`}
      >
        {children}
      </div>
    </div>
  )
}

export function CloseButton({ onClick, label = 'Close' }: { onClick: () => void; label?: string }) {
  return (
    <button type="button" className="btn-icon" aria-label={label} onClick={onClick}>
      ✕
    </button>
  )
}
