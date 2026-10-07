# Non-Functional Requirements

All quantitative values are **targets to be measured**, not achieved claims. A target is "met" only with a
recorded, reproducible measurement (see `docs/implementation/progress.md` and the evaluation reports).

| ID | Category | Requirement / target | Measurement method | Milestone |
|----|----------|----------------------|--------------------|-----------|
| NFR-01 | Retrieval quality | Recall@5 ≥ 0.80 on the pilot eval set | Eval harness (FR-19) on the `eval/` dataset | M3 baseline, M6 |
| NFR-02 | Retrieval quality | MRR reported for every retrieval configuration | Eval harness | M3 |
| NFR-03 | Latency | p95 end-to-end Q&A latency ≤ 3 s, stated with hardware, model, and warm/cold state | Per-query `latency_ms` + benchmark script | M3 (measure), M7 |
| NFR-04 | Latency | p95 search latency reported separately from generation latency | Benchmark script | M3 |
| NFR-05 | Availability | ≥ 99% availability of search and Q&A over a defined pilot window | Health-probe log over the window | M7 (pilot) |
| NFR-06 | Integrity | 100% of displayed citations resolve to persisted chunks (deterministic check) | Citation validator + tests | M2, M3 |
| NFR-07 | Integrity | Abstention on unanswerable questions; precision and recall reported | Unanswerable subset of the eval set | M3 |
| NFR-08 | Reproducibility | Same corpus + config ⇒ identical chunks, chunk IDs, and retrieval rankings | Determinism tests | M1, M3 |
| NFR-09 | Reproducibility | Every answer and eval run records model tag, embedding model, chunk config, top-k, prompt version | Schema constraints + tests | M2, M3 |
| NFR-10 | Security | Upload limits, path-traversal protection, parameterized SQL, CORS allow-list, secrets hygiene, prompt-injection handling, SSRF-safe outbound fetches (arXiv hosts only) | Security audit (protocol step 5) | M4, M7 |
| NFR-11 | Privacy | No uploaded document text or secrets in logs; no data sent to hosted LLM services | Log review + config audit | M1+, M7 |
| NFR-12 | Resource bounds | Max upload size, page count, question length, top-k, generation tokens, context size, and job concurrency are configured and enforced | Config + tests | M1, M2, M4 |
| NFR-13 | Hardware fit | Runs on the reference machine: 16 GB RAM, RTX 3050 Laptop 4 GB VRAM, Ryzen 7 7435HS, Windows 11 | Documented runs | All |
| NFR-14 | Maintainability | CI green (lint, format, mypy strict, tests, build) on every PR to `main` | GitHub Actions | M0+ |
| NFR-15 | Accessibility | Keyboard-navigable UI, labelled controls, sufficient contrast, usable at 360 px width | Role-based Testing Library queries + manual check | M1+ |
| NFR-16 | Graceful degradation | Search keeps working when Ollama is unavailable; Q&A returns an explicit 503 (no hosted fallback) | Tests with a failing provider | M2 |
