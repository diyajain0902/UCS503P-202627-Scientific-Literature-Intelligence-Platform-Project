// New-style (1706.03762, optional v7) and old-style (hep-th/9901001) arXiv identifiers.
const ARXIV_ID = /^(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+(?:\.[a-z]{2})?\/\d{7}(?:v\d+)?)$/i

/** The arXiv ID in the input, or null if it is not an ID (and should be treated as keywords). */
export function parseArxivId(input: string): string | null {
  const match = ARXIV_ID.exec(input.trim())
  return match ? match[1] : null
}
