# Functional Requirements

Source: `Project Proposal/main.tex`, refined by `CLAUDE.md` and the Step 2 master prompt.
IDs are permanent. Never renumber; retire an ID by marking it *Withdrawn*.

Priority classes: **Required** (proposal scope), **Infrastructure** (needed to deliver or verify required features),
**Recommended** (valuable, scheduled if time permits), **Optional** (only with explicit approval).

| ID | Requirement | Priority | Proposal ref | Milestone |
|----|-------------|----------|--------------|-----------|
| FR-01 | Search the official arXiv API by query and/or arXiv ID; show metadata (ID, version, title, authors, abstract, categories, dates). | Required | Overview; Ingestion | M1 (by ID), M4 (search UI) |
| FR-02 | Import an arXiv paper (metadata + PDF) into the corpus; re-import of a known `arxiv_id` updates rather than duplicates. | Required | Ingestion and chunking | M1 |
| FR-03 | Upload a scientific PDF with validation (type, size, page count, encryption, text layer) and safe storage. | Required | Overview | M4 |
| FR-04 | Page-aware text extraction with PyMuPDF; every extracted character traceable to a page and offset. | Required | Ingestion and chunking | M1 |
| FR-05 | Deterministic chunking with a documented tokenizer, window, and overlap; chunks spanning pages record all pages. | Required | Ingestion and chunking | M1 |
| FR-06 | Local embeddings via `sentence-transformers/all-MiniLM-L6-v2`; dimension validated = 384. | Required | Stack | M1 |
| FR-07 | Persist papers, documents, chunks, and embeddings in PostgreSQL + pgvector with constraints and Alembic migrations. | Required | Data model | M1 |
| FR-08 | Semantic search: ranked passages with score, chunk ID, paper metadata, page(s); corpus filter. | Required | Retrieval and grounding | M1 |
| FR-09 | Grounded Q&A using a local Ollama model, answering only from retrieved passages. | Required | Retrieval and grounding | M2 |
| FR-10 | Inline citations resolved server-side to persisted chunks (paper + page + passage); unresolvable citations are flagged, never shown as valid. | Required | Retrieval and grounding | M2 |
| FR-11 | Explicit insufficient-evidence (abstention) response when retrieved context does not support an answer. | Required | Retrieval and grounding | M2 |
| FR-12 | Single-paper summary with provenance to source chunks. | Required | Overview | M5 |
| FR-13 | Cross-paper evidence synthesis over a selected paper set, with per-claim citations. | Required | Overview | M5 |
| FR-14 | Structured extraction: task, method, dataset, metric, result, limitations; each field evidence-linked or explicitly `unknown`. | Required | Overview (knowledge extraction) | M5 |
| FR-15 | Multi-paper comparison table built from FR-14 fields, with caveats where datasets, protocols, or units differ. | Required | Overview | M5 |
| FR-16 | Corpus browsing: list, filter (source, year, category, status), paper details, delete with confirmation. | Required | Subsequent deliverables | M4 |
| FR-17 | Ingestion job tracking: explicit states (queued, fetching, extracting, chunking, embedding, ready, failed), actionable errors, retry. | Required | Risks (parsing failures) | M1 (states), M4 (UI, retry) |
| FR-18 | Query history: questions, answers, citations, model/config, latency. | Required | Data model (`queries`, `answers`) | M2 (persist), M4 (UI) |
| FR-19 | Retrieval evaluation harness: Recall@k and MRR on a versioned, manually labeled set; reproducible run records. | Required | Evaluation | M3 |
| FR-20 | Answer-quality evaluation: citation validity, groundedness/faithfulness, abstention behavior, latency. | Required | Secondary metrics | M3 (citation, abstention, latency), M5 (groundedness) |
| FR-21 | Automated regression gate in CI on retrieval quality. | Required | CI/CD | M3 |
| FR-22 | Research dashboard summarizing corpus, ingestion status, and recent queries. | Recommended | — | M4 |
| FR-23 | Settings view showing configured models, endpoints, and dependency health (read-only). | Recommended | — | M4 |
| FR-24 | Hybrid retrieval (dense + BM25) with rank fusion. | Recommended | Retrieval upgrade | M6 |
| FR-25 | Cross-encoder reranking, adopted only if it beats the baseline on the eval set within the latency budget. | Optional | Retrieval upgrade | M6 |
| FR-26 | OCR for scanned PDFs. | Optional | — | Deferred; scanned PDFs are rejected with a clear error (FR-03) |

## Infrastructure requirements

| ID | Requirement | Milestone |
|----|-------------|-----------|
| IR-01 | Versioned REST API (`/api/v1`), typed schemas, consistent error envelope, pagination, OpenAPI. | M0 (base), ongoing |
| IR-02 | Environment-based configuration; `.env.example`; no secrets in version control. | M0 |
| IR-03 | Docker Compose for PostgreSQL + pgvector, backend, and frontend. | M1 |
| IR-04 | GitHub Actions CI: lint, format, type check, tests, build. | M0 |
| IR-05 | Health endpoints: liveness; readiness reporting DB, embedding model, and Ollama status separately. | M0 (liveness), M1/M2 (readiness) |
| IR-06 | Structured (JSON) logs with request IDs; no secrets or full document text in logs. | M1 |
| IR-07 | Ollama provider adapter isolating API details; timeouts, bounded generation, error mapping. | M2 |
| IR-08 | Background execution for ingestion jobs. | M1 |
| IR-09 | Reproducible setup, troubleshooting, and handover documentation. | Ongoing; complete in M7 |
