/** Pastel tone families from the design tokens; each maps to a `tone-*` CSS class. */
export const TONES = ['lav', 'mint', 'peach', 'sky'] as const
export type Tone = (typeof TONES)[number] | 'rose'

export function toneAt(index: number): Tone {
  return TONES[((index % TONES.length) + TONES.length) % TONES.length]
}

/** A stable tone for a citation label such as "P3", so a chip and its source always share a colour. */
export function toneForLabel(label: string): Tone {
  const n = Number.parseInt(label.replace(/\D/g, ''), 10)
  return Number.isNaN(n) ? 'lav' : toneAt(n - 1)
}

/** Q&A outcome → dot tone: answered (mint), declined for lack of evidence (peach), error (rose). */
export function outcomeTone(status: string): Tone {
  if (status === 'answered') return 'mint'
  if (status === 'insufficient_evidence') return 'peach'
  return 'rose'
}

export const OUTCOME_LABELS: Record<string, string> = {
  answered: 'Answered',
  insufficient_evidence: 'Insufficient evidence',
  error: 'Error',
}
