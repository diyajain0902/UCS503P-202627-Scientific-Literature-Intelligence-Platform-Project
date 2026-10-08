# Test and Evaluation Methodology

Covers FR-19, FR-20, FR-21 and NFR-01–NFR-04, NFR-07. Results live in run records under `eval/runs/`; reports
quote numbers only from a named run record.

## 1. Test layers

| Layer | Marker / command | What it uses | In CI |
|-------|------------------|--------------|-------|
| Unit | `pytest -m "not integration and not model and not network and not ollama"` | Pure code, fakes, mocked HTTP | Yes |
| DB integration | `pytest -m integration` | Real PostgreSQL + pgvector; deterministic fake embedder and scripted fake LLM | Yes (service container) |
| Real embedding model | `pytest -m model` | all-MiniLM-L6-v2 | Yes |
| Real local LLM | `pytest -m ollama` | qwen2.5:3b via Ollama | No (manual; GitHub runners have no Ollama) |
| Live arXiv | `pytest -m network` | arXiv API | No (manual) |
| Frontend | `npm test` | Vitest + Testing Library, mocked fetch | Yes |
| Retrieval regression gate | `python -m app.evaluation retrieval --min-recall-at-5 X` | Real corpus, real MiniLM, real pgvector | Yes |

Tests that use fakes say so in their module docstrings; real-model results are reported separately.

## 2. Evaluation data

- **Corpus:** `eval/corpus.json`, 20 NLP arXiv papers pinned to exact versions. Built into a separate database with
  `python -m app.evaluation build-corpus`; `verify_corpus` refuses to evaluate against anything else. PDFs are not
  committed (fetched from arXiv at build time).
- **Questions:** `eval/qa_v1.json`. Each item has an id, question, kind (`answerable` / `unanswerable`), reference
  answer, evidence quotes (paper + verbatim text), `labeler`, `labeled_on`, `review_status`.
- **Provenance (ADR-0007):** items were written by the AI assistant and are **not human-validated** unless marked
  `human_reviewed` with a reviewer. Every run record reports the labelers and the number of human-reviewed items.
- **Relevance rule:** a retrieved passage is relevant to an item if it belongs to the labelled paper and contains an
  evidence quote (case- and whitespace-normalised). Labels therefore survive re-chunking. `check-labels` verifies
  every quote occurs in the corpus before any run.

## 3. Metrics

| Metric | Definition | Requirement |
|--------|------------|-------------|
| Recall@k (k = 1, 5, 10) | Fraction of answerable items with ≥ 1 relevant passage in the top k (hit rate, as in the proposal) | NFR-01 (target Recall@5 ≥ 0.80) |
| MRR | Mean over answerable items of 1 / rank of the first relevant passage (0 if none in top 10) | NFR-02 |
| Search latency p50 / p95 | Server-side embedding + vector search time per query | NFR-04 |
| Answer rate | Answerable items with status `answered` | FR-20 |
| Cited-relevant rate | Answerable items where at least one *valid* citation points to a relevant passage (deterministic proxy for citation correctness; not semantic support) | FR-20, NFR-06 |
| Citation validity rate | Valid citations / all citations in returned answers (withheld answers' claims are not stored and not counted) | NFR-06 |
| Abstention recall | Unanswerable items answered with `insufficient_evidence` | NFR-07 |
| Abstention precision | Of all `insufficient_evidence` outcomes, the fraction on unanswerable items | NFR-07 |
| False-answer rate | Unanswerable items that received an `answered` status | NFR-07 |
| Q&A latency p50 / p95 (warm) | Server-side end-to-end Q&A time with the model loaded; percentiles by nearest rank | NFR-03 (target p95 ≤ 3 s) |
| Cold-start latency | First question after the model is unloaded from Ollama (reported separately) | NFR-03 |

Not measured in M3: semantic groundedness of each claim (planned with a local judge plus human spot checks, M5),
availability (pilot window, M7).

## 4. Run records

`eval/runs/<UTC timestamp>_<kind>_<commit>.json` contains: dataset name/version/sha256/item counts/labelers/
human-reviewed count, manifest sha256, git commit and dirty flag, hardware, configuration (embedding model,
chunker versions, top-k, Q&A thresholds, generation model and options, prompt version), aggregate metrics, and
per-item results. Run records are committed when they back a reported number.

## 5. CI regression gate (FR-21)

The `retrieval-eval` CI job builds the corpus from arXiv, runs `check-labels`, then
`retrieval --min-recall-at-5 0.675`.

**Threshold rationale.** The baseline is Recall@5 = 0.700 (28/40) on Windows. The gate is one item lower
(0.675 = 27/40) to tolerate a single rank change from floating-point differences between the Windows baseline
and Linux CI runners; a regression of two or more items fails the build. The gate guards against regressions
only: the NFR-01 target (0.80) is **not met**. Changing the threshold requires a progress-log entry explaining why.

## 6. Baseline results (2026-10-08)

Corpus `nlp-core` v1 (20 papers, 1,634 chunks, chunker `tokwin-v1|…|w256|o38`); dataset `nlp-core-qa` v1
(40 answerable, 10 unanswerable, 110 evidence quotes). **Labels: written by the AI assistant, 0 items
human-reviewed (ADR-0007).** Hardware: Ryzen 7 7435HS, RTX 3050 Laptop 4 GB, Windows 11; embeddings on CPU.

### Retrieval (official record `eval/runs/20261008T170309Z_retrieval_3eab94d.json`)

| Recall@1 | Recall@5 | Recall@10 | MRR | Search p50 / p95 |
|---------:|---------:|----------:|----:|-----------------:|
| 0.200 | **0.700** | 0.775 | 0.416 | 43 / 53 ms |

NFR-01 target Recall@5 ≥ 0.80: **not met** (0.70). All misses at k = 5 still retrieve the correct paper; the
relevant passage ranks lower or outside the top 10. Before the label-completeness review (52 quotes) the same
system scored Recall@5 = 0.50; that run record is kept for transparency.

### Grounded Q&A (qwen2.5:3b, temperature 0, seed 0, num_ctx 4096, top_k 6, qa_min_score 0.30)

| Run | Power | Answer rate | Cited-relevant (answerable) | Abstention recall | False answers (unanswerable) | Citation validity | Warm p50 / p95 | Cold start |
|-----|-------|------------:|----------------------------:|------------------:|-----------------------------:|------------------:|---------------:|-----------:|
| 135804Z | not recorded (AC likely) | 0.825 | 0.550 | 1.00 | 0.00 | 1.00 | 1.29 / 2.74 s | 5.9–10.5 s |
| 164846Z | battery | 0.750 | 0.525 | 1.00 | 0.00 | 1.00 | 3.30 / 7.24 s | 5.9–8.9 s |

- Run-to-run variance is material: the answer rate moved between 0.75 and 0.825 at identical settings
  (temperature 0 and a fixed seed do not make GPU generation fully deterministic). Report ranges, not single runs.
- NFR-03 (p95 ≤ 3 s): met in one plugged-in run (2.74 s), **not met on battery** (7.24 s); cold start is
  5.9–10.5 s. Not a validated claim: two runs, one machine, power state recorded only from the second run.
- `qa_min_score` calibration: raising it to 0.40 would block 4/10 unanswerable questions before the model call
  while keeping 27/28 answerable items whose relevant passage is in the top 6. Two runs at 0.40 showed no quality
  difference beyond run-to-run variance and the value would be tuned on the test set itself, so the default stays
  0.30.
- Groundedness (M5, run `20261008T182021Z_qa_6080738.json`, AC power, `--judge`): 33 cited claims judged by
  the local model — 69.7% supported, 18.2% partially supported, 12.1% not supported, 0 unusable verdicts.
  **Self-judged by the same qwen2.5:3b that wrote the answers; not human-validated.** Same run: answer rate 0.80,
  cited-relevant 0.55, abstention recall 1.00, false answers 0/10, citation validity 1.00, warm p50/p95
  2.09/3.27 s, cold 5.5-9.2 s.
- "Cited-relevant" is a deterministic proxy (a valid citation points to a labelled passage); semantic support of
  each claim is not measured here.
