/**
 * The findings log: what the evaluation showed, and what changed in the code because of it.
 *
 * HAND-WRITTEN AND APPEND-ONLY. This is the one part of the eval write-up a human authors —
 * a finding is a judgement, and no metric delta implies it on its own. Add entries; do not
 * rewrite them. An entry that turned out to be wrong gets a later entry saying so, because
 * a log that edits its own past is not evidence of anything.
 *
 * It lives here as data rather than as prose in portfolio.mdx on purpose:
 * `backend/scripts/build_index.py` globs the project MDX into the retrieval corpus, so
 * publishing a finding as MDX would change the corpus that produces the next finding. See
 * docs/adr/0002-findings-log-outside-the-corpus.md.
 *
 * Each metric delta must name the corpus it was measured on. Values from different corpora
 * are not comparable, which is also why this log exists instead of a trend chart.
 */

export interface MetricMove {
  /** Metric name as the harness reports it, e.g. `MRR` or `hit@5`. */
  metric: string
  before: number
  after: number
  /** Which arm moved, in the language the scoreboard uses. */
  arm: string
}

export interface Finding {
  id: string
  /** ISO date the finding was concluded. */
  date: string
  title: string
  /** What the measurement showed. One or two sentences, past tense. */
  observed: string
  /** What changed in the code or the design as a result. */
  changed: string
  /** The movement that made the finding visible, when one number tells the story. */
  move?: MetricMove
  /** Where to read the full account. */
  href?: string
}

/** Newest first. */
export const findings: Finding[] = [
  {
    id: 'rrf-k-scale',
    date: '2026-09-04',
    title: 'A textbook constant, used at the wrong scale, had disabled half the pipeline',
    observed:
      'Reciprocal-rank fusion combines ranked lists as weight / (k + rank), and the ' +
      'standard k of 60 assumes lists thousands of documents long. Over ten-item lists it ' +
      'varied the rank term by 1.15x while the arm weights varied by 2.33x, so every ' +
      'semantic hit outscored every keyword hit and the keyword retriever could never ' +
      'contribute a candidate the other had missed. Fusion was running, passing its tests, ' +
      'and contributing nothing.',
    changed:
      'Dropped k to 1 so rank position outweighs the arm weighting at this list length, and ' +
      'added fusion tests that assert a low-weighted retriever can still introduce a ' +
      'candidate. No unit test could have caught this: every component behaved exactly as ' +
      'specified, and only a metric moved.',
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#a-textbook-constant-used-at-the-wrong-scale-disabled-half-the-system',
  },
  {
    id: 'shared-tokenizer',
    date: '2026-09-04',
    title: 'Index-time and query-time tokenizers disagreed, silently costing keyword recall',
    observed:
      'Both the index builder and the query path tokenized with lower().split(), which ' +
      'never matched "engineering" against "engineer", left punctuation welded to terms, ' +
      'and scored stopwords as if they carried meaning.',
    changed:
      'Replaced both with one shared stopword-filtered, Snowball-stemmed tokenizer in ' +
      'app/rag/tokenize.py. Shared is the operative word — a mismatch between the two sides ' +
      'is unfixable at query time, because the terms being searched for were never written ' +
      'into the index.',
    move: { metric: 'MRR', before: 0.745, after: 0.892, arm: 'Keyword only' },
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#the-tokenizer-was-silently-destroying-keyword-recall',
  },
]
