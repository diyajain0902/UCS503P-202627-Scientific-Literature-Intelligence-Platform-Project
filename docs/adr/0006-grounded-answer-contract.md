# ADR-0006: Grounded answer contract — labelled evidence, constrained JSON, server-side citation checks

- Status: Accepted (2026-10-08, M2)

## Context

FR-09–FR-11 require answers generated only from retrieved passages, citations that resolve to real passages,
and explicit abstention. The local model is `qwen2.5:3b` (ADR-0001; team constraint for M2: keep this model).
Small models garble long identifiers, follow instructions embedded in documents, and can loop or truncate.

## Decision

1. **Labels, not IDs.** Passages above the relevance threshold are labelled `P1..Pn` in rank order. The model
   cites labels; the server maps labels to the evidence it actually supplied. Any other label is stored and shown
   as `valid: false` and never linked to a source (`answer_citations.valid = (evidence_id IS NOT NULL)`).
2. **Untrusted evidence.** Passages are wrapped in `<passage>` delimiters; delimiter-like text inside a passage is
   neutralised; the system prompt states that passage text is source material, not instructions.
3. **Constrained JSON.** Ollama receives a JSON Schema (`format`), with field order `claims` → `status` and, per
   claim, `citations` → `text`; citations must match `^P[0-9]{1,2}$`; claim text ≤ 300 chars; ≤ 5 claims. The
   server validates with a more tolerant Pydantic model so bad labels are flagged rather than failing the request.
4. **Abstention at three points.** (a) no passage ≥ `qa_min_score` → `insufficient_evidence` without calling the
   model; (b) model returns `insufficient_evidence`; (c) no claim has a valid citation → answer withheld as
   `insufficient_evidence`. Claims whose text is only labels are dropped.
5. **Claim labels are honest.** `cited` means at least one valid citation; semantic support is **not** verified
   (groundedness is FR-20, evaluated in M3/M5). The UI says so.
6. **Everything is recorded.** Every outcome except invalid input is persisted (`queries`, `answers`,
   `answer_evidence` snapshot, `answer_citations`), including errors, with model tag, prompt version, embedding
   model, retrieval/generation options, token counts, and timings (NFR-09).
7. **No fallback.** Ollama unreachable / model missing → HTTP 503; timeout → 504; malformed output → 502.
   Search is unaffected (NFR-16).

## Evidence for the prompt/schema choices (smoke tests, not an evaluation)

Measured 2026-10-08 with qwen2.5:3b, temperature 0, seed 0, num_ctx 4096:

| Variant | Synthetic set (4 answerable / 3 unanswerable) | Real-paper set, 1706.03762 (6 / 2) |
|---|---|---|
| First prompt (rules + trailing "Respond with JSON" hint, status first) | 0–1/4 answered, 3/3 abstained | 1/6 with real text; 1 truncated (looping `N\n`); claims like `"P1"` |
| Hint removed, answer-first rules, claims before status | 4/4, 3/3 | — |
| + citations before text | — | 4/6, 2/2, 0 truncated, 1 terse claim (`dmodel 512`) |
| + one worked example in the prompt | — | 5/6 but **1/2 abstained**: invented a cited answer to an unanswerable question — rejected |
| **Chosen:** citations first + label pattern + 300-char cap, no example | 4/4, 3/3 | 4/6, 2/2, 0 truncated |

The chosen variant trades some recall for not fabricating answers. Retrieval misses (e.g. the Adam optimizer
passage not in the top 6) are a separate problem for M3.

## Consequences

- Answers are short and conservative; some answerable questions abstain.
- `qa_min_score = 0.30` is provisional and must be calibrated on the M3 evaluation set.
- Changing the prompt or schema requires bumping `PROMPT_VERSION` and re-running the M3 evaluation.
