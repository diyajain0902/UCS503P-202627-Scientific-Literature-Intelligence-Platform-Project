# Evaluation Dataset and Annotation Methodology

Covers FR-19 and NFR-01/02/07. Companion to `docs/evaluation.md` (method) and `rag-evaluation-report.md`.

## 1. Corpus

| Property | Value |
|----------|-------|
| Manifest | `eval/corpus.json`, `nlp-core` v1, sha256 `6f5c0efa…` (recorded in every run record) |
| Papers | 20 NLP arXiv papers, each pinned to an exact version (e.g. `1706.03762v7`) |
| Size in the eval database | 399 pages, 1,654 chunks (433 of them span two or more pages) |
| Chunker | `tokwin-v1`, MiniLM tokenizer, 256-token windows, 38-token overlap (ADR-0003) |
| Build | `python -m app.evaluation build-corpus` fetches the PDFs from arXiv; `verify_corpus` refuses any other content |
| Provenance check | `check-provenance` re-extracts every stored PDF: **0 problems in 1,654 chunks** (audit, 2026-10-09) |

## 2. Question set

| Property | Value |
|----------|-------|
| File | `eval/qa_v1.json`, `nlp-core-qa` v1, sha256 `b0fc0f6d…` |
| Items | 50: 40 answerable, 10 unanswerable |
| Evidence quotes | 110 (1–5 per answerable item: 8 items have 1, 11 have 2, 8 have 3, 9 have 4, 4 have 5) |
| Labeler | `ai-assistant` for all 50 items (ADR-0007, a team decision) |
| Review status | `unreviewed` for all 50. **0 items human-reviewed** |
| Labelled on | 2026-10-08 |

Item fields: `id`, `kind`, `question`, `answer` (reference answer), `evidence[]` (`arxiv_id`, verbatim `quote`),
`labeler`, `labeled_on`, `review_status`, and for unanswerable items `notes` (how absence was checked).

### Derived categories

These categories come from the existing labels, with no new labelling:

| Category | Rule | Items |
|----------|------|------:|
| Single-paper, numeric answer | one evidence paper; the reference answer contains a digit | 16 |
| Single-paper, textual answer | one evidence paper; no digit | 23 |
| Multi-paper | evidence from two or more papers | 1 |
| Unanswerable | `kind = unanswerable` | 10 |
| Ambiguous, conflicting-findings, or partially supported questions | — | **0 (not covered)** |
| Prompt injection inside retrieved text | — | 0 in this set; covered separately by `test_qa_ollama.py::test_instructions_inside_passages_are_not_followed` (real model) |

## 3. Annotation rules (as applied in M3)

1. Questions were paraphrased, not copied from the paper text.
2. Evidence was located by keyword search over each paper's extracted text, **not** with the retriever, to avoid
   biasing labels towards what the system already finds.
3. Each quote is verbatim; `check-labels` verifies every quote occurs in the stated paper before any run.
4. A label-completeness review added quotes for every passage in the gold paper that states the answer (52 → 110
   quotes). It also corrected two wrong labels (q019, q026); the pre-review run record is kept.
5. Unanswerable items were checked for absence by keyword search across the whole corpus (`notes`). Several are
   adversarial: they name a corpus paper and ask for a fact that only a neighbouring paper has (e.g. q050).

## 4. Relevance unit

**Passage (chunk) level.** A retrieved chunk is relevant to an item if it belongs to the labelled paper **and**
contains at least one evidence quote (case- and whitespace-normalised). Paper-level matches do not count.
Recall@k and MRR in every experiment use this one unit.

- Labels survive re-chunking because they are quotes, not chunk IDs.
- A quote that crosses a chunk boundary is in no chunk, so it counts as a miss. This makes recall conservative.

## 5. Metric definitions (verified in code: `backend/app/evaluation/metrics.py`)

- **Recall@k** = (answerable items with ≥ 1 relevant chunk in the top k) / (answerable items). This is a hit rate,
  as the proposal defines it, not the fraction of all relevant chunks retrieved.
- **MRR** = mean over answerable items of 1 / rank of the first relevant chunk, or 0 if none is in the top k.
- **Percentiles:** nearest rank, no interpolation.

Unit tests on hand-computed cases: `tests/test_eval_metrics.py` (12 tests, passing).

## 6. Limitations

- **Labels are not human-validated.** The same assistant wrote the labels, much of the code, and this audit.
- **Small:** 40 answerable items means one item is 2.5 points of Recall@5. The 95% Wilson interval for 35/40 is
  roughly 0.74–0.95.
- **No held-out split:** the retrieval mode was selected on this set.
- Single domain (NLP), English only. Almost no multi-paper questions, and none with conflicting findings or
  ambiguity.
- **Recommended next data work (team):** human review of at least 15 items (set `review_status` and reviewer), and
  a held-out set of about 20 new questions covering multi-paper, conflicting, ambiguous, and partially supported
  cases.
