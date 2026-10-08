# Known Failure Modes

Observed behaviour only. Each entry names its evidence. IDs are permanent. Status as of the step 4 audit
(2026-10-09).

| ID | Failure mode | Evidence | Frequency observed | Status |
|----|--------------|----------|--------------------|--------|
| FM-01 | **Wrong-paper answer.** The question names paper A; the model answers with a fact from paper B because B's passage was retrieved and A's relevant passage was not. | q002 (Transformer optimizer answered with LLaMA's AdamW β values; the relevant chunk was at rank 10, outside the Q&A top 6); q050 (DistilBERT energy answered with LLaMA's 449 MWh) | 2 of 50 questions in the `20261008T204611Z` run; q050 in both M7 runs | Open (RA-01) |
| FM-02 | **Cited passage does not contain the claim.** The citation is structurally valid, but the content comes from a different passage or from the model's own knowledge. | q040 (SwiGLU claim cites the T5 passage while the LLaMA passage P1 was in context); q033 (LoRA claim not in either cited passage) | 2 of 14 claims in the audit spot check | Open (RA-02). The UI states that semantic support is not verified |
| FM-03 | **Non-responsive claim.** A correct, cited sentence that doesn't answer the question. | q017 (ELMo: the claim restates the 2L+1 representations, not the learned combination) | 1 of 14 spot-checked claims | Open, low |
| FM-04 | **Relevant passage ranked below the cut-off.** The right paper is retrieved but the passage that answers is not in the top k. | All 5 `hybrid_rerank` misses at k = 5 and all 12 dense misses | 5/40 (`hybrid_rerank`), 12/40 (dense) | Open; a held-out set is needed before tuning |
| FM-05 | **Flattened tables.** Numbers from PDF tables lose their row and column structure; the model can pick the wrong cell. | M5 extraction: perplexity 4.67 reported as BLEU | Seen once in manual runs | Open (ingestion limitation) |
| FM-06 | **Overlapping neighbours in context.** Adjacent chunks share 38 tokens, so context repeats text. | 47 neighbour pairs in 300 top-6 slots (`20261008T214608Z_profile-retrieval_03fb705.json`) | Systematic | Open, medium (wastes context; no measured quality effect) |
| FM-07 | **Self-judge disagrees with inspection.** The local judge marked 3 supported claims "not supported" or "partial", and marked a wrong-paper answer "supported". | Audit spot check (q016, q030, q039; q002) | 4 of 14 spot-checked claims | Open; the judge is supplementary, not ground truth |
| FM-08 | **Model abstains or cites nothing on answerable questions.** | `20261008T204611Z`: 3 abstentions + 2 withheld; `20261008T205117Z`: 1 + 1 | 2–5 of 40 | Accepted (the safe direction) |
| FM-09 | **No clarification for ambiguous questions.** The system never asks the user to clarify; it answers or abstains. | Code review: no clarification path in `services/qa.py` or the prompt | Not measured (no ambiguous items) | Open, low |
| FM-10 | **Latency above target.** The cross-encoder costs about 0.9 s and generation about 1.9 s (p50). | Profile and Q&A records | Every query in `hybrid_rerank` | Open (NFR-03 not met) |

## Failure modes tested and not observed

- **Fabricated citation accepted as valid.** Unit and integration tests reject unknown labels. In the database,
  every one of 422 stored citations resolves to evidence of the same answer.
- **Wrong page or paper recorded for a citation.** Evidence snapshots match their chunks' text, pages and paper in
  all 2,364 evidence rows. Chunks match their original PDFs: `check-provenance`, 0 problems in 1,654 chunks.
- **Following instructions embedded in a retrieved passage.** Real-model test passed (`test_qa_ollama.py`, 3/3).
- **Answer shown when no citation is valid.** 0 "answered" rows without a valid citation; such answers are withheld
  (2 + 1 cases in M7 runs).
