# 3. Contact PII purged from history, and treated as already disclosed

Date: 2026-09-05

## Status

Accepted.

## Context

A home address and phone number sat in `docs/resume.txt` from the first commit,
and in `backend/indexes/chunks.json` as chunk 0 of the committed retrieval index.
The chatbot is a public endpoint that reads indexed text back on request, so
*"where does David live?"* returned a grounded answer.

The remediation in #21 stopped that at three levels — removed at the source,
redacted during the index build, and guarded by a regression test. All three act
on the *current* tree. None of them touched:

1. **Every earlier commit.** The string was one `git log -p` away in a public
   repository, from the initial commit onward.
2. **The fixtures and documentation of the fix itself.** `test_pii.py`,
   `build_index.py`'s pattern comments, and `docs/chatbot-rag.md` all used the
   real number and the real address as worked examples. The remediation
   re-published the data it was written to remove.

## Decision

**Purge the strings from history, and stop claiming that undoes the exposure.**

- Fixtures and documentation now use fictional contact details — a `555-01xx`
  number from the range reserved for fiction, and an invented street address.
  Test data that has to *look* like PII must never *be* PII: a regression test is
  read by everyone who reads the repository.
- All history was rewritten (`git filter-repo`, replacing the strings in every
  blob on every branch and tag), and the rewritten refs force-pushed.
- One historical `bm25.pkl` blob carried the same data as pickled tokens.
  Byte-substitution inside a pickle corrupts it, so that blob's content was
  replaced wholesale. Historical copies of a generated index are not worth
  preserving.

**And: the data is treated as disclosed, not recovered.** The repository was
public throughout. A rewrite removes the strings from the surface people
normally read; it cannot un-publish them. Specifically, what a rewrite does not
reach:

- `refs/pull/*` — pull request head refs are immutable and still carry the old
  blobs, and the PR file views render them. Removing those requires GitHub
  Support.
- Unreachable objects on GitHub's side, until Support runs garbage collection.
- Forks, clones, mirrors, search indexes, and anything that scraped the repo
  while the data was live.

## Consequences

- Every commit SHA changed. Existing clones must re-clone (a `git pull` on an
  old checkout will conflict or re-introduce objects). Release tags now point at
  rewritten commits, and commit links in `CHANGELOG.md` and in closed pull
  requests resolve to SHAs that no longer exist.
- A GitHub Support request to garbage-collect unreachable objects and purge the
  PR refs is the remaining step. Until it completes, treat the data as reachable.
- Because the exposure is assumed rather than hoped away: do not reuse that
  number, and treat any future appearance of it as a fresh incident rather than
  an echo of this one.
- `test_pii.py` guards the corpus. It does not guard the repository's own source
  from carrying contact details in a comment or a fixture — that is a review
  habit, and this ADR is its statement of record.
