# Handover

Scientific Literature Intelligence Platform: UCS503P (2026–27), Thapar Institute of Engineering and Technology.
Authors: Paarth Ganesh, Diya Jain. State as of 2026-10-09 (end of M7, before final acceptance).

## 1. What the system does

A local research assistant for scientific papers:

- **Import** from arXiv (by ID or keyword search) or upload PDFs.
- **Ingest:** page-aware text extraction, 256-token chunks, and MiniLM embeddings in PostgreSQL + pgvector.
- **Search** with hybrid dense + BM25 retrieval and cross-encoder reranking.
- **Ask** questions and get answers from a local Ollama model, with citations checked on the server and an
  explicit "insufficient evidence" when the papers don't support an answer.
- **Analyse:** summarise a paper, synthesise and compare several papers, and extract structured fields.

Nothing is sent to a hosted LLM.

## 2. Where things are

| Need | Look at |
|------|---------|
| Rules every change must follow | `CLAUDE.md` |
| Requirements and status per requirement | `docs/requirements/` (RTM is the index) |
| Architecture and decisions | `docs/architecture/`, `docs/adr/0001`–`0008` |
| History of what was done and measured | `docs/implementation/progress.md` |
| Run, configure, back up, troubleshoot | `README.md`, `docs/operations.md` |
| Evaluation method and numbers | `docs/evaluation.md`, `eval/runs/` |
| Security controls and open risks | `docs/security.md` |
| Audits (RAG evaluation, security, CI/CD) | `docs/audits/` |

## 3. Status against the proposal's goals

| Goal | Status | Evidence |
|------|--------|----------|
| Retrieval quality (NFR-01 Recall@5 ≥ 0.80) | Met on the pilot set: 0.875 | `docs/evaluation.md` §7. **Optimistic:** labels are assistant-written and unreviewed, and the mode was chosen on the same set |
| Q&A latency (NFR-03 p95 ≤ 3 s) | **Not met:** 4.4–4.5 s warm | Retrieval takes ~1.2 s with the reranker; generation ~1.9 s (p50) |
| Citation integrity (NFR-06) | 1.00 valid in every run | Server-side resolution; tests |
| Abstention (NFR-07) | 9/10 unanswerable abstained; 1 false answer (q050) | `docs/evaluation.md` §7 |
| Availability (NFR-05 ≥ 99%) | One 25.5-minute window: 52/52 probes up | Progress log (M7); not a semester-scale pilot |
| Generation | Local Ollama `qwen2.5:3b` instead of the proposal's Gemini | ADR-0001. Whether to amend the proposal is still open |
| Deployment | Local Docker Compose only | Public deployment needs authorization and the open security items fixed |

## 4. Decisions still open for the team

1. **Human review of the evaluation labels.** This is the largest missing piece of evidence. Review a sample (for
   example 15 of 50 items) and set `review_status`/reviewer in `eval/qa_v1.json`. Ideally, also write a small
   held-out question set.
2. **Least-privilege database role (security S1).** Needs separate migration and runtime roles. This changes the
   deployment and needs a manual step on the existing volume.
3. **Speed vs. recall.** Keep `hybrid_rerank` (Recall@5 0.875, p95 ~4.5 s), or switch the default to `hybrid`
   (0.725, about 1.1 s faster per question). Either way, NFR-03 should be re-stated or re-measured.
4. **q050 false answer:** an abstention change evaluated on held-out questions (RAG audit R4).
5. **Proposal amendment** for ADR-0001 (Gemini → Ollama).
6. **Move the repository out of OneDrive.** Docker builds fail inside it. The workaround is in
   `docs/operations.md` §2.
7. **Small-to-big chunking experiment.** It was in the M6 plan and has not been done. It is optional now that
   NFR-01 is met on this set.

## 5. Known limitations

- Extraction can cite a valid passage and still read the wrong number, because tables are flattened by text
  extraction (M5 example: perplexity read as BLEU).
- Summaries sometimes produce one long claim instead of 3–5 short ones.
- No authentication: the tool is single-user and local.
- Scanned PDFs are rejected (no OCR).
- Uploaded papers have no authors or abstract metadata.
- The groundedness judge is the answering model itself (not independent).
- CI's `retrieval-eval` job depends on live arXiv and has failed from throttling before.

## 6. First steps for a new maintainer

1. Read `CLAUDE.md`.
2. Follow `README.md` to start the stack.
3. Run the end-to-end test (`docs/operations.md` §5).
4. Read the latest progress-log entry and the three audits.
5. Pick up an open decision from §4.

Every behaviour change references requirement IDs, adds tests, and updates the RTM and the progress log.
