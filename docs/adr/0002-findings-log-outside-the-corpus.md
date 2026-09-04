---
status: accepted
---

# The Findings Log lives in data, outside the indexed corpus

`backend/scripts/build_index.py` globs `frontend/content/projects/*.mdx` into the Corpus,
so the write-up about the evaluation is itself retrieved by the system the evaluation
measures. The Findings Log therefore lives in `frontend/data/evalFindings.ts` and is
rendered by a component, rather than being written as MDX prose on the page.

Putting it in MDX would mean that publishing a Finding changes the Corpus that produces
the next Finding — injecting text dense in the vocabulary of the metrics (`MRR`, `hit@5`,
`cross-encoder`) into the very index being scored. That is a sibling of the
fitting-to-the-test-set problem: contaminating the instrument with commentary about its
own readings.

The chatbot should still be able to answer questions about this evaluation work. That is
served by adding question-and-answer pairs to `docs/chatbot-questions.md`, which is a
deliberate Corpus document with a stable voice and a controlled rate of change, rather
than by letting an append-only log leak in through the MDX glob.

## Consequences

- Findings are structured entries (date, commit, Arm, metric delta, conclusion, change),
  not paragraphs — which is also what lets them be rendered compactly and checked by tests.
- Moving the log into MDX later is not cleanly reversible: once Findings have been indexed,
  every subsequent Measured Run is scored against a contaminated Corpus.
