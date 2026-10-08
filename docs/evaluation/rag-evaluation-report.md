# RAG Evaluation Audit Report (protocol step 4)

- **Date:** 2026-10-09.
- **System audited:** `main` at `9adc518` (M0–M7 merged). Audit tooling added on `chore/step4-rag-evaluation-audit`
  (commit `03fb705`); all new run records come from that clean commit.
- **Auditor:** the AI assistant, acting in the specialist role the team requested. **This audit is not independent**:
  the same assistant wrote the evaluation labels and much of the code. No human spot checks have been performed.
- **Supersedes:** `docs/audits/2026-10-09-rag-evaluation-audit.md` (M7 findings R1–R14, kept for history).
- **Companion documents:** `dataset-and-annotation-methodology.md`, `experiment-log.md`, `known-failure-modes.md`.

## 0. Baseline and setup corrections

The system was not modified before the baseline was taken. The only additions are two read-only evaluation commands,
committed before any new measurement and with no effect on the system under test:

- `check-provenance`: compares stored chunks with their original PDFs.
- `profile-retrieval`: times each retrieval stage and measures redundancy.

Baselines re-run on `03fb705` reproduced earlier records exactly (dense R@5 0.700 / MRR 0.416; `hybrid_rerank`
0.875 / 0.701).

Conditions: Ryzen 7 7435HS, 16 GB RAM, Windows 11, AC power; MiniLM and the cross-encoder on CPU; Ollama
`qwen2.5:3b` (Q4_K_M) on an RTX 3050 4 GB, temperature 0, seed 0, `num_ctx` 4096; corpus 20 papers / 1,654 chunks.

## 1. Retrieval quality

### Configuration inspected

| Aspect | Finding |
|--------|---------|
| Query preprocessing | Whitespace collapsed; length ≤ 1,000 chars. BM25 keeps alphanumeric terms of 2+ characters, OR-ed (unit-tested). No stemming beyond PostgreSQL's English config; no query expansion. |
| Embeddings | `all-MiniLM-L6-v2`, 384-dim, L2-normalised, max 256 tokens (tests: `test_real_model.py`). The database enforces `vector(384)`. |
| Similarity / score | Cosine similarity `1 − cosine_distance`, returned as `score` in every mode. The mode's ordering score is a separate `rank_score`. Neither is a probability. The UI labels it "score" with 3 decimals. |
| Chunking | 256-token windows, 38-token overlap, page-aware offsets; 433/1,654 chunks span two or more pages and record both `page_start` and `page_end`. |
| Filters | `paper_ids` filter applied in both dense and BM25 SQL before ranking; with HNSW, `iterative_scan = strict_order` would keep filtered results complete. |
| Duplicates | 0 exact duplicate chunk texts in the corpus. **47 neighbouring-chunk pairs in 300 top-6 slots** (FM-06). |
| Limits and context | Search top_k ≤ 50; Q&A top_k 6, cosine ≥ 0.30, ≤ 12,000 characters of context. |
| HNSW | Index `hnsw (embedding vector_cosine_ops)` exists, but **the planner uses an exact sequential scan** (12 ms at 1,654 rows). The production query also orders by `(distance, chunk_id)`, which prevents index use at any size. Results are exact, so quality is unaffected, but HNSW settings have no effect (RA-06). |
| Stability | Ranking is deterministic: identical metrics across 4 commits. Ties are broken by chunk ID. |

### Results (relevance unit: chunk containing a labelled quote; 40 answerable items)

| Mode | R@1 | R@5 | R@10 | MRR | Search p50 / p95 | Failures at k = 5 | Record |
|------|----:|----:|-----:|----:|-----------------:|------------------:|--------|
| dense (baseline) | 0.200 | 0.700 | 0.775 | 0.416 | 42 / 49 ms | 12 | `20261008T214635Z_retrieval_03fb705.json` |
| bm25 | 0.300 | 0.525 | 0.650 | 0.393 | 56 / 91 ms | 19 | `20261008T203750Z_retrieval_192ac2b.json` |
| hybrid | 0.375 | 0.725 | 0.825 | 0.527 | 102 / 137 ms | 11 | `20261008T203825Z_retrieval_192ac2b.json` |
| **hybrid_rerank (default)** | **0.575** | **0.875** | **0.925** | **0.701** | 1,734 / 1,955 ms | **5** | `20261008T214832Z_retrieval_03fb705.json` |

**NFR-01 target Recall@5 ≥ 0.80: met, 0.875 (35/40), 95% Wilson interval ≈ 0.74–0.95.** The interval crosses the
target. The mode was selected on this set, and the labels are unreviewed.

**Failure category:** every miss, in every mode, is "right paper, passage ranked too low". The gold paper was in the
top 5 for all 5 `hybrid_rerank` misses and all 12 dense misses. No miss retrieved a wrong paper exclusively.
Per-category R@5 (`hybrid_rerank`): numeric 15/16, textual 19/23, multi-paper 1/1.

**Metric definitions** were verified against `metrics.py` and its 12 hand-computed unit tests. Recall@k here is a
hit rate (≥ 1 relevant chunk in the top k), per the proposal.

## 2. Citation integrity

The model only emits labels (`P1…Pn`). The server maps them to the evidence it supplied, so a page number, chunk ID
or paper the model makes up cannot enter the system.

| Check | Method | Result |
|-------|--------|--------|
| Nonexistent / out-of-range labels | `test_generation.py`, `test_qa_integration.py` (fabricated labels stored invalid, never linked) | Pass |
| Duplicate, label-only, malformed output | `test_generation.py`; `test_qa_integration.py::test_malformed_model_output_is_an_error_not_an_answer` | Pass |
| Every valid citation points to evidence supplied to *that* answer | SQL over all 418 eval answers, 422 citations | **0 violations** |
| Invalid citations never linked to evidence | SQL | 0 violations |
| Evidence snapshot = stored chunk (text, pages, paper) | SQL over 2,364 evidence rows | **0 mismatches** |
| Stored chunk = original PDF (text at span, pages, words on the recorded page) | `check-provenance`, 20 PDFs, 1,654 chunks | **0 problems** |
| Multi-page chunks keep both pages | Schema stores `page_start`/`page_end`; provenance checks both | Pass (433 chunks) |
| Deleted source | Main DB: 1 evidence row whose chunk was deleted keeps its snapshot (`chunk_id` null); covered by M4 tests | Pass |
| Answer shown without a valid citation | SQL: answered rows with 0 valid citations | 0; such answers are withheld (3 cases in M7 runs) |
| Frontend inspector shows the cited passage | `QAPanel.test.tsx` (citation chips open the inspector, M2); browser check in M2 | Pass (not re-tested in a browser this audit) |

**Citation validity rate** (valid citations ÷ citations in answers returned as "answered"): **52/52** (run
`204611Z`) and **57/57** (run `205117Z`); 422/422 across all stored eval answers.

**Structural validity is not semantic support** (next section).

## 3. Groundedness and faithfulness

| Measure | Method | Result |
|---------|--------|--------|
| Claim support (LLM judge) | `judge-v1`, rubric supported / partial / not supported against the cited passages; judge = `qwen2.5:3b` (the answering model) | 31/37 supported (83.8%), 3 partial, 3 not supported (`204611Z`) |
| Claim support (assistant spot check) | The auditor read 14 claims (all 6 the judge flagged + 8 random judge-"supported", seed 7) against the full cited text | 10 supported and responsive; 1 supported but not answering (q017); 1 supported by a passage from the **wrong paper**, so the answer is wrong (q002); **2 not supported by the cited passage** (q033, q040) |
| Judge reliability | Agreement with the spot check on "does the cited passage support the claim" | 11/14. The judge wrongly rejected q016, q030 and q039, and rated the q002 wrong-paper answer supported |
| Unsupported-claim frequency | Claims with no valid citation are dropped or withheld (structural); semantic: 2/14 in the spot check | Structural 0 shown; semantic not measured at scale |
| Prompt injection | Real-model test with an instruction inside a passage | Not followed (pass) |

**Coverage gaps:** no ambiguous, conflicting-findings, or partially supported items, and 1 multi-paper item. This
is a dataset gap, not a measured strength.

Prompt and schema were inspected (`generation/prompts.py`, `qa-v1`): passages are delimited and neutralised, the
rules forbid outside knowledge and say to abstain if no passage states the answer, and a JSON schema puts citations
before claim text. **Nothing checks claim-to-passage entailment, or that the passage's paper matches the paper the
question names.**

## 4. Abstention and uncertainty

**Decision policy (ADR-0006).** The system abstains at three points:

1. No passage reaches cosine ≥ 0.30: no model call; reason "No passage in the corpus was relevant enough".
2. The model returns `insufficient_evidence`.
3. No claim has a valid citation: the answer is withheld.

| Measure | `204611Z` | `205117Z` |
|---------|----------:|----------:|
| Unanswerable correctly abstained | 9/10 | 9/10 |
| False answers (unanswerable answered) | 1/10 (q050) | 1/10 (q050) |
| Abstention precision | 9/14 | 9/11 |
| Path 1 (threshold) used | 0 times | 0 times |

- **Threshold never fires.** All abstentions came from the model or from the citation check. On this corpus the
  0.30 threshold never fired on these questions; the model's judgement does the work.
- **Absence vs. absence of evidence.** The message says the *retrieved passages* don't contain enough
  information, not that the fact is false. That is the correct distinction.
- **Score not presented as a probability.** The UI says "score" and "retrieval rank" and does not call it a
  probability.
- **Evidence vs. synthesis.** Each claim lists its citations, and evidence is shown separately. The UI states that
  semantic support is not verified.
- **No clarification requests** for ambiguous questions (FM-09).
- **No explicit uncertainty labelling** beyond cited / unsupported / insufficient evidence. `CLAUDE.md` §4 asks for
  supported / unsupported / uncertain; "uncertain" does not exist (RA-05).

## 5. Latency (NFR-03, NFR-04)

| Stage (Q&A top_k 6, warm, p50 / p95) | ms |
|--------------------------------------|---:|
| Query embedding | 17 / 30 |
| Dense SQL (exact scan) | 29 / 36 |
| BM25 SQL | 36 / 66 |
| Hybrid call (dense + BM25 + RRF) | 61 / 85 |
| **Cross-encoder (24 candidates)** | **895 / 985** |
| Retrieval inside Q&A (from stored answers) | 1,157 / 1,363 |
| Generation (from stored answers) | 1,945 / 3,255 |
| **End-to-end warm** (n = 50 per run, server-side) | **3,058–3,104 / 4,428–4,498** |
| Cold start (3 samples per run) | 8,051–12,008 |

Context construction and citation validation are not timed separately. Their cost is part of end-to-end latency
minus retrieval and generation (about 0 to 100 ms, inferred, not measured).

**NFR-03 (p95 ≤ 3 s): not met** (4.4–4.5 s warm). The evidence requirements were not weakened to improve it. The
two levers are the reranker pool (about 37 ms per candidate) and generation length.

## 6. Findings

| ID | Severity | Finding | Evidence / reproduction | Requirements | Root cause | Remediation | Regression test | Status |
|----|----------|---------|-------------------------|--------------|------------|-------------|-----------------|--------|
| RA-01 | **High** | Wrong-paper answers presented as answers (q050 unanswerable; q002 answerable but answered from LLaMA) | `python -m app.evaluation qa`, items q050, q002; spot check | FR-09, FR-11, NFR-07 | Retrieval returns a near-topic passage from another paper; nothing checks that the cited paper matches the entity named in the question | Add a check that the answer comes from the paper the question names (or flag a mismatch to the user), designed and tuned on a **held-out** set | Eval items q002 and q050 (exist); add held-out adversarial items | **Open.** A fix tuned on these items would leak test data, so it was not done in this audit |
| RA-02 | **High** | Valid citation, unsupported claim (q033, q040) | Spot check; judge also flags them | FR-10, FR-20, NFR-06 | Only structural validation; the model sometimes cites the wrong label | Claim-level entailment check (a local NLI model or lexical support score) shown as "unverified" in the UI; human spot-check protocol | Fixture with a claim/passage mismatch once the check exists | **Open.** The UI already states that support is not verified |
| RA-03 | Medium | Evaluation labels are assistant-written, unreviewed, and the mode was chosen on the same set | `eval/qa_v1.json` `review_status` | FR-19, NFR-01 | Team decision ADR-0007; no held-out split | Human review of ≥ 15 items; a new held-out set (about 20 items) | `check-labels` | Open (team action) |
| RA-04 | Medium | NFR-03 not met (p95 4.4–4.5 s) | Q&A run records; profile | NFR-03 | CPU cross-encoder (~0.9 s) + generation (~1.9 s) | Smaller reranker pool or `hybrid` mode, tuned on a held-out set; or restate the target | Q&A eval latency | Open (decision needed) |
| RA-05 | Medium | No "uncertain" label and no clarification path | Code review | `CLAUDE.md` §4, FR-11 | Not designed | Add an uncertainty status for partially supported answers | — | Open |
| RA-06 | Medium | HNSW index not used; HNSW settings inert; docs imply HNSW search | `EXPLAIN ANALYZE`: Seq Scan + top-N sort | FR-08, NFR-04 | Small table + `ORDER BY distance, id` | Order by distance only and break ties in Python, if/when the corpus grows; record exact vs. approximate search in run records | Plan assertion test at scale | Open (no quality impact now) |
| RA-07 | Medium | Coverage gaps: 1 multi-paper item, no conflicting or ambiguous items | Methodology §2 | FR-19, FR-20 | Dataset scope | Add these categories to the held-out set | — | Open |
| RA-08 | Low | Context redundancy (47 neighbour pairs in 300 slots) | Profile record | FR-09 | Overlapping chunks are not de-duplicated | Merge or drop neighbours before prompting (experiment) | Profile metric | Open |
| RA-09 | Low | Self-judge is unreliable (3 false rejections, 1 false acceptance in 14) | Spot check | FR-20 | Judge = answering model, 3B | Report the judge as supplementary only (done); add human spot checks | — | Documented |

**No critical findings** in this audit. The two critical M6 defects (fabricated ADR numbers; threshold on reranker
logits) were fixed in M7 and are verified: the ADR now matches its records, and the regression tests pass.

## 7. Fixes completed in this audit

No system behaviour was changed. The High findings (RA-01, RA-02) need either model or prompt changes that would be
tuned on the test set, or new components (entailment check). Both are outside safe audit scope and need a team
decision.

Tooling added and verified:

- `check-provenance`: integration test `test_provenance_check_passes_on_ingested_corpus_and_detects_tampering`
  passes; real corpus has 0 problems.
- `profile-retrieval`: record `20261008T214608Z_profile-retrieval_03fb705.json`.

Checks run:

- Eval integration tests: 5 passed.
- Real-model tests: `pytest -m ollama` 3/3.
- Ruff and mypy strict (77 files) clean.

## 8. Conclusion

1. **Overall assessment.** Retrieval is good on this set, and citation integrity is strong and verified end to end:
   PDF → chunk → evidence → citation. Faithfulness is the weak point: 1 wrong-paper answer per run, a second
   wrong-paper answer to an answerable question, and 2 of 14 spot-checked claims not supported by their cited
   passage. All numbers rest on an assistant-labelled, unreviewed set of 50 questions.
2. **Metrics.** R@1 0.575, R@5 0.875, R@10 0.925, MRR 0.701 (`hybrid_rerank`). Citation validity 52/52 and 57/57.
   Judge support 83.8%. Spot-check support 11/14. Abstention 9/10, false answers 1/10. Warm p95 4.4–4.5 s.
3. **Requirements.**
   - **Passed:** NFR-01 (on this set, with caveats), NFR-02, NFR-04, NFR-06 (structural), FR-10.
   - **Failed:** NFR-03.
   - **Partial:** NFR-07 (1 false answer), FR-20 (no human spot checks), FR-11 (no "uncertain" status).
4. **Critical / High findings.** No critical. High: RA-01 (wrong-paper answers), RA-02 (valid-but-unsupported
   citations).
5. **Fixes.** None to system behaviour. Audit tooling added and verified (§7).
6. **Outstanding remediation.**
   - Human label review and a held-out set (RA-03, RA-07).
   - Paper-consistency and entailment checks (RA-01, RA-02), developed on the held-out set.
   - The latency decision (RA-04).
7. **Readiness.** The RAG system is **ready for the next approved phase** (step 5b security pass and step 7
   acceptance), **provided** RA-01 and RA-02 are carried as known High issues in the acceptance report. They are
   not suitable to "fix" without new, held-out evaluation data.
