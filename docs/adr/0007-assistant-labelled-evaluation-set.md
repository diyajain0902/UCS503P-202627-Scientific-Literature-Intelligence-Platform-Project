# ADR-0007: Evaluation labels produced by the AI assistant, with explicit provenance

- Status: Accepted (2026-10-08, M3) — decided by the team (Diya Jain), overriding `CLAUDE.md` §5's
  "manually labeled by the team"
- Supersedes: the labelling clause of `CLAUDE.md` §5 (contract updated in the same change)

## Context

The proposal plans "a hand-labeled evaluation set" and `CLAUDE.md` §5 required team labels. At the M3 approval
the team instructed the AI coding assistant to produce all labels itself. The integrity rules still apply: labels
must not be fabricated, and human validation must not be claimed when it did not happen.

## Decision

1. The assistant writes every item (question, reference answer, evidence quotes) by reading the extracted text of
   the pinned corpus papers. Items record `labeler: "ai-assistant"`, `labeled_on`, and
   `review_status: "unreviewed"`.
2. **Independence from the system under test:** evidence is located by reading/keyword search of the paper text,
   never by querying the dense retriever, and questions are paraphrased rather than copied from passages.
3. **Checkable labels:** each evidence quote must occur verbatim (whitespace/case-normalised) in the corpus;
   `python -m app.evaluation check-labels` fails otherwise. Unanswerable items are checked by keyword search
   across the corpus for the absence of an answer (best effort, recorded in `notes`).
4. Any human review is recorded per item (`review_status: "human_reviewed"`, `reviewer`). Run records report
   how many items were human-reviewed.
5. All reports state: "labels produced by an AI assistant; not human-validated (n reviewed = k)".

## Consequences

- Metrics measure agreement with assistant-written labels, not with expert human judgement. Label errors and
  question-writing bias (e.g. favouring facts that are easy to quote) are possible.
- Before citing these numbers as validated results in the university report, the team should review a sample
  (recommended: at least 20% of items, all unanswerable items) and record reviews in the dataset.
- The labels follow the project's provenance rules, so they can be upgraded to human-reviewed without a format change.
