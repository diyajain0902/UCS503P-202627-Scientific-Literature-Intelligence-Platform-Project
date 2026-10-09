# MVP Known Limitations and Future Work

As of the MVP acceptance (2026-10-09). Each item names its evidence. None blocks the core user journeys; all must be
disclosed with the submission.

## Answer quality and evaluation

| Limitation | Evidence | Future work |
|------------|----------|-------------|
| **Q&A latency above target:** warm p95 4.4–4.5 s vs. 3 s (NFR-03). The cross-encoder takes ~0.9 s and generation ~1.9 s at p50, on CPU and a 4 GB GPU | `docs/evaluation.md` §7; step 4 profile | Smaller rerank pool or `SLIP_SEARCH_MODE=hybrid` (−1.1 s, Recall@5 0.725), tuned on a held-out set; GPU reranking |
| **Wrong-paper answers:** the model can answer with a fact from a related paper (q050 unanswerable; q002 answerable) | RA-01, FM-01 | Check that the cited paper matches the entity named in the question |
| **A valid citation does not guarantee support:** 2 of 14 spot-checked claims were not stated by the passage they cite. The UI says semantic support is not verified | RA-02, FM-02 | Claim-level entailment check; mark such claims "unverified" |
| **Abstains on some answerable questions** (2–5 of 40 in eval runs; 2 of 3 in the reproducibility run and 2 of 3 in the acceptance run) | FM-08; acceptance and reproducibility runs | Prompt and threshold work on held-out data |
| Summary claims cite every supplied passage rather than claim-specific ones | Acceptance run (FR-12) | Prompt refinement; per-claim citation limits |
| Extracted values can be wrong even when cited (PDF tables are flattened) | M5 (perplexity read as BLEU) | Table-aware extraction |
| No "uncertain" answer status; no clarification questions | RA-05, FM-09 | Add a status for partial support |
| **Evaluation labels are assistant-written; 0 of 50 human-reviewed;** the search mode was selected on the same set | ADR-0007; RA-03 | Human review of ≥ 15 items; a new held-out set |
| Evaluation set lacks multi-paper, conflicting and ambiguous questions | RA-07 | Extend the held-out set |
| Groundedness judge is the answering model itself (3B) and disagreed with inspection on 4 of 14 claims | RA-09 | Human spot checks; a stronger local judge |
| Context contains overlapping neighbouring chunks (47 pairs in 300 top-6 slots) | FM-06 | De-duplicate or merge neighbours |

## Retrieval and ingestion

| Limitation | Evidence | Future work |
|------------|----------|-------------|
| arXiv search ranks by arXiv's relevance; an exact title may not be in the top results | Acceptance run | Search the title field first, or quoted phrase search; import by ID works |
| arXiv rate-limits bursts (HTTP 429). Shown to the user as a 502 with the reason; CI retries with backoff | Acceptance and CI logs | — |
| HNSW index unused at the current corpus size (exact scan, 12 ms) | RA-06 | Revisit when the corpus grows |
| Scanned PDFs rejected (no OCR) | FR-26 deferred | OCR pipeline |
| Uploaded papers have no author or abstract metadata | M4 | Metadata entry or lookup |
| Settings view does not show the search mode or reranker model | FR-23 partial | Add them to `/settings` |

## Operations, security and reproducibility

| Limitation | Evidence | Future work |
|------------|----------|-------------|
| **Ollama on this machine listens on all interfaces with Public-profile firewall Allow rules** (host setting) | SEC-01 | Owner applies `docs/security/mvp-security-audit.md` §6, step 4 |
| No authentication; single user, localhost only | SEC-09 | Authentication before any shared deployment |
| App database role is a superuser | SEC-02 | Separate migration and runtime roles |
| No wall-clock timeout on PDF parsing | SEC-05 | Parse in a killable subprocess |
| Model revisions not pinned; first start downloads ~180 MB (about 15 min on the reference network) | SEC-08; reproducibility report | Pin revisions; pre-bake the models into the image |
| Availability measured over only 25.5 minutes (52/52 probes) | NFR-05 | A multi-day pilot with `scripts/uptime_probe.py` |
| Builds fail inside OneDrive | Reproducibility report | Keep the repository outside OneDrive |
| No manual accessibility audit | NFR-15 | Keyboard and screen-reader pass |
