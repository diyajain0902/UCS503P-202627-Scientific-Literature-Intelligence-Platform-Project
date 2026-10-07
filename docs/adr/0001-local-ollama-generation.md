# ADR-0001: Local Ollama for generation instead of hosted Gemini

- Status: Accepted (2026-10-08)
- Deciders: project team (per `CLAUDE.md` engineering contract)

## Context

The proposal (`Project Proposal/main.tex`, Stack and Engine sections) specifies Gemini 2.5 Flash, a hosted LLM,
for final answer and summary generation. The engineering contract requires local generation via Ollama and
forbids any hosted LLM as a silent fallback.

## Decision

Use a locally running Ollama server, accessed through a provider interface in `backend/app/generation/`.
Endpoint and model tag come from `SLIP_OLLAMA_BASE_URL` and `SLIP_OLLAMA_MODEL`. If Ollama is unreachable or the
model is missing, Q&A returns an explicit error; semantic search continues to work. No hosted provider is
implemented. Adding one later requires a new ADR, explicit approval, opt-in configuration, and visible labelling.

Initial model: `qwen2.5:3b` (Q4_K_M, ~1.9 GB on disk, ~2.16 GB loaded) — already installed on the reference
machine. Verified on 2026-10-08: loads fully into the RTX 3050's 4 GB VRAM; returns valid JSON in `format: json`
mode; cold load ≈ 9.7 s, warm short completion ≈ 0.24 s. Its suitability for grounded scientific QA is
**not yet evaluated**; M2/M3 will measure it, and alternative ≤4B models may be compared only after checking
VRAM fit.

## Consequences

- + Zero per-query cost, no data leaves the machine, reproducible model version (digest recorded).
- + Removes a deviation between proposal and contract by documenting it here.
- − Smaller local models are weaker at instruction following and long context than Gemini; answer quality and the
  NFR-03 latency target must be measured, not assumed.
- − Ollama's default context window on this machine is 4096 tokens; `num_ctx` must be set explicitly and the
  context budget bounded (retrieved chunks × size + prompt + answer).
- − Cold-start latency (~10 s) exceeds the 3 s target; the backend should warm the model and latency reports must
  distinguish cold and warm.
- The course proposal should note this change when submitted/updated (team action).
