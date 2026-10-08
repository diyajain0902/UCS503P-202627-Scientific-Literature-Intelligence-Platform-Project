# Audit — CI/CD and Reproducibility (protocol step 6)

- **Date:** 2026-10-09. **Commit audited:** `main` at `4eff300` (M6 merged) plus M7 fixes on
  `feature/m7-release-readiness`.
- **Requirements:** NFR-08 (reproducibility), NFR-09 (recorded configuration), NFR-14 (CI green), IR-04.
- **Method:** read `.github/workflows/ci.yml`, both Dockerfiles, `docker-compose.yml`, the lockfiles and the eval
  run records; re-ran the retrieval evaluation in every mode and compared the results with earlier records.
- **Auditor:** the AI assistant, at the team's request. The team has not reviewed this audit yet.

## 1. What CI runs

| Job | Content | Real dependencies |
|-----|---------|-------------------|
| `backend` | ruff, ruff format check, mypy strict, unit tests | none |
| `backend-integration` | `pytest -m "integration or model"` | `pgvector/pgvector:0.8.0-pg17`, MiniLM |
| `frontend` | `npm ci`, oxlint, `tsc`, Vitest, build | none |
| `docker-images` | `compose config`, `compose build` | Docker |
| `retrieval-eval` | build the 20-paper corpus from arXiv, check labels, retrieval gate | arXiv, MiniLM, cross-encoder, pgvector |
| `dependency-audit` (added in M7) | `pip-audit` on the locked export, `npm audit --audit-level=high` | PyPI/OSV, npm |

Triggered on every push; `permissions: contents: read`. There is **no CD job**. That is by design: deployment needs
explicit authorization (`CLAUDE.md` §6).

## 2. Findings

| ID | Finding | Severity | Status |
|----|---------|----------|--------|
| C1 | After M6 the retrieval gate tested `hybrid_rerank` implicitly (it is the config default) against 0.675, a threshold derived from the dense baseline. A fall from 0.875 to 0.70 would have passed. | High | **Fixed in M7.** The mode is now explicit: `hybrid_rerank` ≥ 0.85 (baseline 35/40 minus one item, same rule as M3) and `dense` ≥ 0.675. |
| C2 | The CI model cache key covered MiniLM only, so the cross-encoder was downloaded on every eval run. | Low | **Fixed** (new key covers both models). |
| C3 | No dependency scanning in CI, although `CLAUDE.md` §6 requires it. | Medium | **Fixed** (`dependency-audit` job). Locally: 0 known vulnerabilities; `torch` (+cpu) cannot be audited. |
| C4 | Eval run records marked `dirty: true` whenever *untracked* files existed, such as earlier run records. | Low | **Fixed.** `dirty` now covers tracked files only and `untracked_files` is counted separately. The M7 `192ac2b` retrieval records predate the fix: their `dirty: true` was caused only by untracked files (verified with `git status --untracked-files=no`, which was empty). |
| C5 | GitHub Actions are pinned by major tag (`@v4`, `@v5`), not commit SHA. `setup-uv` installs the latest uv (the Dockerfile pins 0.11.7). | Low | Open. Pin SHAs and `version: "0.11.7"` if supply-chain hardening is wanted. |
| C6 | Docker base images are pinned by tag, not digest (`python:3.12-slim`, `node:24-alpine`, `nginx:1.27-alpine`). | Low | Open. Rebuilds can pick up patch-level changes. |
| C7 | Hugging Face models are pinned by name, not revision (also security S5). | Medium | Open. A silent upstream model update would change embeddings and rankings. |
| C8 | `retrieval-eval` depends on live arXiv. Its first three runs in M3 failed at `build-corpus`, probably from throttling. | Medium | Open (known flake). Failures now emit `::error::` annotations. |
| C9 | CI results for the M6 merge and for M7 were **not observed**: no `gh` CLI, and the unauthenticated GitHub API was rate-limited. | — | **Unverified.** The team should check the Actions tab for this branch. |
| C10 | The new `e2e` tests need a running stack and Ollama, so they are excluded from CI. | — | By design. Run them manually (`docs/operations.md`). |

## 3. Reproducibility evidence

**Retrieval is deterministic across runs and commits** (same corpus, same machine):

| Mode | M3 `3eab94d` | M6 `0006bbd` | M7 `192ac2b` |
|------|--------------|--------------|--------------|
| dense R@5 / MRR | 0.700 / 0.416 | 0.700 / 0.416 | 0.700 / 0.416 |
| bm25 R@5 / MRR | — | 0.525 / 0.393 | 0.525 / 0.393 |
| hybrid R@5 / MRR | — | 0.725 / 0.539 | 0.725 / 0.527 |
| hybrid_rerank R@5 / MRR | — | 0.875 / 0.701 | 0.875 / 0.701 |

The `hybrid` change (R@1 0.400 → 0.375) comes from the M7 tie-break: equal RRF scores are now ordered by chunk ID,
where before they kept list-insertion order. That makes the ordering explicit and independent of insertion
order. It moved one first-relevant rank.

**Generation is not bit-reproducible.** At temperature 0 with a fixed seed, Q&A answer rates still varied between
runs (0.75–0.825 in M3). Reports therefore quote ranges and name each run record.

**Configuration recording (NFR-09):** run records now include the retrieval mode, RRF settings, weights and reranker
model, alongside the git commit, hardware, power source, embedding model, chunker version, generation options and
prompt version. Q&A answers and analyses persist the same retrieval block.

## 4. Verdict

CI covers lint, types, tests, build, a meaningful retrieval gate, and dependency scanning. The remaining
reproducibility gaps are model-revision pinning (C7) and image/action digests (C5, C6). CI status on GitHub for
this branch has to be checked by the team (C9).
