# Test and Evaluation Methodology

Covers FR-19, FR-20, FR-21 and NFR-01–NFR-04, NFR-07. Results live in run records under `eval/runs/`; reports
quote numbers only from a named run record.

## 1. Test layers

| Layer | Marker / command | What it uses | In CI |
|-------|------------------|--------------|-------|
| Unit | `pytest -m "not integration and not model and not network and not ollama and not e2e"` | Pure code, fakes, mocked HTTP | Yes |
| DB integration | `pytest -m integration` | Real PostgreSQL + pgvector; deterministic fake embedder and scripted fake LLM | Yes (service container) |
| Real embedding model | `pytest -m model` | all-MiniLM-L6-v2 | Yes |
| Real local LLM | `pytest -m ollama` | qwen2.5:3b via Ollama | No (manual; GitHub runners have no Ollama) |
| Live arXiv | `pytest -m network` | arXiv API | No (manual) |
| Frontend | `npm test` | Vitest + Testing Library, mocked fetch | Yes |
| Retrieval regression gate | `python -m app.evaluation retrieval --search-mode M --min-recall-at-5 X` | Real corpus, real MiniLM, real cross-encoder, real pgvector | Yes |
| Stack end-to-end | `SLIP_E2E_BASE_URL=http://localhost:8080/api/v1 pytest -m e2e` | Running Docker stack via nginx, real models, real Ollama | No (manual; needs Ollama) |
| Availability probe | `python scripts/uptime_probe.py` | Running stack | No (pilot window) |

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
| Search latency p50 / p95 | Server-side search time per query (embedding, database, fusion, and reranking when enabled) | NFR-04 |
| Answer rate | Answerable items with status `answered` | FR-20 |
| Cited-relevant rate | Answerable items where at least one *valid* citation points to a relevant passage (deterministic proxy for citation correctness; not semantic support) | FR-20, NFR-06 |
| Citation validity rate | Valid citations / all citations in returned answers (withheld answers' claims are not stored and not counted) | NFR-06 |
| Abstention recall | Unanswerable items answered with `insufficient_evidence` | NFR-07 |
| Abstention precision | Of all `insufficient_evidence` outcomes, the fraction on unanswerable items | NFR-07 |
| False-answer rate | Unanswerable items that received an `answered` status | NFR-07 |
| Q&A latency p50 / p95 (warm) | Server-side end-to-end Q&A time with the model loaded; percentiles by nearest rank | NFR-03 (target p95 ≤ 3 s) |
| Cold-start latency | First question after the model is unloaded from Ollama (reported separately) | NFR-03 |

Groundedness (M5, `--judge`, local self-judge, not human-validated) and availability (M7 pilot window, §8) were
added later.

## 4. Run records

`eval/runs/<UTC timestamp>_<kind>_<commit>.json` contains: dataset name/version/sha256/item counts/labelers/
human-reviewed count, manifest sha256, git commit, `dirty` (tracked files changed) and `untracked_files` (from
M7), hardware and power source, configuration (embedding model, chunker versions, top-k, retrieval mode with RRF and
reranker settings (from M7), Q&A thresholds, generation model and options, prompt version), aggregate metrics, and
per-item results. Run records are committed when they back a reported number.

## 5. CI regression gate (FR-21)

The `retrieval-eval` CI job builds the corpus from arXiv, runs `check-labels`, then two gates (since M7):

| Mode | Gate | Baseline (Windows) | Rationale |
|------|------|--------------------|-----------|
| `hybrid_rerank` (default) | Recall@5 ≥ **0.85** | 0.875 (35/40), `20261008T204032Z_retrieval_192ac2b.json` | One item below baseline |
| `dense` (fallback) | Recall@5 ≥ **0.675** | 0.700 (28/40), M3 official record | One item below baseline (unchanged) |

**Threshold rationale.** Each gate is one item below its baseline. This tolerates one rank change caused by
floating-point differences between the Windows baseline and Linux CI runners; a regression of two or more items
fails the build. From M6 until M7 the gate ran the default mode (`hybrid_rerank`) against the dense threshold
0.675, which would have allowed a 0.200 drop. M7 tightened it (justified in the progress log). Changing a threshold
requires a progress-log entry explaining why.

## 6. Baseline results (2026-10-08)

Corpus `nlp-core` v1 (20 papers, 399 pages, 1,654 chunks, chunker `tokwin-v1|…|w256|o38`; counts corrected in
M7 from the database, which has not been rebuilt since M3; the M3 log said 1,207 pages / 1,634 chunks); dataset `nlp-core-qa` v1
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

## 7. Hybrid retrieval and reranking results (M6, re-measured in M7, 2026-10-09)

Same corpus and dataset as §6, top_k 10, AC power, after migration 0006. ADR-0008 has the decision.

| Mode | Recall@1 | Recall@5 | Recall@10 | MRR | Search p50 / p95 | Run record |
|------|---------:|---------:|----------:|----:|-----------------:|------------|
| dense | 0.200 | 0.700 | 0.775 | 0.416 | 46 / 53 ms | `20261008T203718Z_retrieval_192ac2b.json` |
| bm25 | 0.300 | 0.525 | 0.650 | 0.393 | 56 / 91 ms | `20261008T203750Z_retrieval_192ac2b.json` |
| hybrid (RRF) | 0.375 | 0.725 | 0.825 | 0.527 | 102 / 137 ms | `20261008T203825Z_retrieval_192ac2b.json` |
| **hybrid_rerank** | **0.575** | **0.875** | **0.925** | **0.701** | 1,853 / 2,021 ms | `20261008T204032Z_retrieval_192ac2b.json` |

- NFR-01 (Recall@5 ≥ 0.80) is **met by `hybrid_rerank` on this set**. Caveats: the mode was selected on these same
  50 questions, and the labels are assistant-written and unreviewed. Treat 0.875 as optimistic until a held-out,
  human-reviewed set confirms it.
- The M6 run records (`…_0006bbd.json`) agree except for `hybrid` R@1 and MRR (0.400 / 0.539 then). The difference
  comes from the M7 RRF tie-break (equal scores now ordered by chunk ID). M6's BM25 and hybrid records were
  measured before migration 0005 had been applied to the eval database (it was still at revision 0004), hence the
  653 ms BM25 p50 then. The run `20261008T195921Z_retrieval_0006bbd.json` (bm25, Recall@5 0.075) is an M6 run that
  the M6 log does not explain. It is kept and is not a valid result.

### Grounded Q&A with `hybrid_rerank` (qwen2.5:3b, top_k 6, qa_min_score 0.30 on cosine similarity)

| Run | Answer rate | Cited-relevant | Abstention recall / precision | False answers | Citation validity | Warm p50 / p95 | Cold start |
|-----|------------:|---------------:|------------------------------:|--------------:|------------------:|---------------:|-----------:|
| `20261008T204611Z_qa_b173e72.json` (`--judge`) | 0.875 | 0.725 | 0.90 / 0.64 | **1/10** | 1.00 | 3.10 / 4.50 s | 8.4–12.0 s |
| `20261008T205117Z_qa_b173e72.json` | 0.950 | 0.750 | 0.90 / 0.82 | **1/10** | 1.00 | 3.06 / 4.43 s | 8.1–10.2 s |

- Compared with M5 (dense, `20261008T182021Z_qa_6080738.json`), the answer rate rose from 0.80 to 0.875–0.95 and
  cited-relevant from 0.55 to 0.725–0.75.
- **New false answer:** q050 ("How many kilowatt-hours of energy did training DistilBERT consume?") was answered
  in both runs with "LLaMA-65B: 449 MWh". The cited LLaMA passage is real, but it is about the wrong model. This
  is an adversarial item and the M5 configuration abstained on it. The groundedness judge rated this claim
  "supported", which shows the judge checks support, not relevance to the question.
- Groundedness (`--judge` run, self-judged, not human-validated): 37 claims; 83.8% supported, 8.1% partial, 8.1% not
  supported (M5: 69.7 / 18.2 / 12.1).
- **NFR-03 (p95 ≤ 3 s) is not met:** warm p95 is 4.4–4.5 s. Profile from the 52 persisted answers of the second
  run (this includes its 3 cold-start questions): retrieval p50 1,157 ms / p95 1,363 ms (cross-encoder over 24
  candidates on CPU), generation p50 1,945 ms / p95 3,255 ms. `SLIP_SEARCH_MODE=hybrid` would remove most of the
  retrieval time at the cost of recall (see table above).
- The first run overlapped with dependency scans and lint runs on the same machine. The second run had no other
  workload. Latencies agree within 2%.
- The second run's record shows `dirty: true`. The tracked changes at the time were `ci.yml`, `nginx.conf`, the
  pytest marker list in `pyproject.toml`, and ADR-0008; none is on the evaluation code path.

## 8. Availability (NFR-05)

The probe is described in `docs/operations.md` §5. Each pilot window's log is committed under `eval/uptime/`, and
the progress log states its results.

## 9. Step 4 RAG evaluation audit (2026-10-09)

Full audit in `docs/evaluation/`: `rag-evaluation-report.md` (findings RA-01–RA-09),
`dataset-and-annotation-methodology.md`, `experiment-log.md`, `known-failure-modes.md`. New commands:
`python -m app.evaluation check-provenance` (chunks against their original PDFs; set `SLIP_STORAGE_DIR` to the
eval storage) and `python -m app.evaluation profile-retrieval` (latency per stage, context redundancy).
