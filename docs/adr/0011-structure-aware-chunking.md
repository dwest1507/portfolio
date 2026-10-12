---
status: accepted
---

# Chunks are cut along each source's structure, with the heading repeated on every piece

The index build packed paragraphs into ~1,000-character windows with a 100-character
overlap. That put several unrelated question-and-answer pairs in one Chunk and split
others across two, which blurred embeddings and triggered BM25's length penalty. The
spec (#62) replaced it with one rule per source kind: one Chunk per question-and-answer
pair, per project section (headed `<project title> — <section>`), and per resume section
or role (headed `<employer> — <role>`), with an over-long pair split by sentence and its
question repeated. `chunk_document` in `backend/scripts/build_index.py` is the single
entry point.

Building it settled four things the spec did not.

- **The size limit applies to every kind, not only questions.** Resume roles and project
  sections run to 3,000 characters, past the 384-token window of the embedding model.
  Any unit over `CHUNK_SIZE` (unchanged at 1,000 characters) is split at line and then
  sentence boundaries, never inside a sentence, and every piece starts with the unit's
  heading. A question is just the heading of a Q&A pair, so this is one rule rather than
  a special case. The limit was kept as it was so the change measured structure, not size.
- **An unanswered question is not indexed.** `docs/chatbot-questions.md` can hold a
  question with no answer yet. Alone in a Chunk it would match its own paraphrases and
  give the model nothing, so it is skipped. Text before the first question (the
  document's title and authoring instructions) is not a pair either and is not indexed.
- **Project titles come from `frontend/data/projects.ts`.** The MDX write-ups carry no
  title of their own; the project card data does. Reading it there keeps one source of
  truth, and an MDX file with no matching project fails the build.
- **A source that parses into nothing fails the build.** A document whose rule finds no
  structure raises rather than contributing zero Chunks, and `tests/test_rag.py` checks
  the committed sources against their structure counted with looser patterns, so a
  formatting change cannot silently drop a source or index it as one block.

## Consequences

- The overlap and fixed-size packing are gone. Nothing needs them: every source is
  structured.
- Adding a new kind of source means adding a rule to `chunk_document`. An unknown source
  raises.
- Editing a source's format (un-bolding questions, demoting `##` headings, reflowing the
  resume's role layout) now fails `make backend-test` until the rule or the source is
  fixed.
