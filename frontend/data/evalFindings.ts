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
 * Each metric delta must name the corpus AND the sample it was measured on. Values from
 * different corpora are not comparable, which is also why this log exists instead of a
 * trend chart — and since the scoreboard began publishing the held-out portion only, a
 * delta quoted over the whole set sits beside a table of different numbers unless it says
 * which sample it came from.
 */

export interface MetricMove {
  /** Metric name as the harness reports it, e.g. `MRR` or `hit@5`. */
  metric: string
  before: number
  after: number
  /** Which arm moved, in the language the scoreboard uses, and over which sample. */
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
    id: 'torch-arms-retired',
    date: '2026-10-13',
    title: 'Retiring the torch arms cut backend CI by more than half and changed no score',
    observed:
      'The four torch arms only ever duplicated their ONNX twins, but every backend pull ' +
      'request still installed torch, its CUDA wheels and FAISS, and the two torch ' +
      're-rankers took about 65 seconds of each retrieval gate. With them gone, Backend CI ' +
      '(lint, tests and retrieval eval, summed) took 2m18s on a warm cache, against 5m20s ' +
      'before, and 2m28s on the first run after the lockfile changed, against 6m57s for the ' +
      'last such run (which also published results, about 70 seconds of its total). The ' +
      'retrieval gate fell from 3m16s to 1m29s, tests from 50 to 15 seconds and lint from 32 ' +
      'to 9.',
    changed:
      'The torch arms, the FAISS index and the sentence-transformers and faiss-cpu ' +
      'dependencies were removed from the harness, so every arm it measures could ship. The ' +
      'shipped arm, its floors and every remaining arm’s definition are unchanged, and the ' +
      'torch measurements stay in the evaluation docs as the record of the parity check.',
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/adr/0013-torch-reference-arms-retired.md',
  },
  {
    id: 'onnx-matches-torch',
    date: '2026-10-12',
    title: 'Swapping torch for ONNX Runtime changed no retrieval score, only the speed',
    observed:
      'Run on ONNX Runtime instead of torch, semantic search and hybrid search scored ' +
      'identically on all four metrics for 68 of 68 development questions (158 chunks): ' +
      'the embeddings agreed to a cosine similarity of 0.9999999, and the re-ranker put ' +
      'every candidate in the same order. The runtime changed only the cost. The ONNX ' +
      'models load in about a second rather than a tenth of one, and the ONNX re-ranker ran ' +
      '5–9× slower than torch.',
    changed:
      'Each torch Reference Arm was a duplicate row of an arm that could ship, so the ' +
      'scoreboard now shows only the arms that could ship. The torch arms are still ' +
      'measured, and their results stay in the evaluation docs.',
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#onnx-runtime-reproduces-the-torch-models-it-does-not-run-them-as-fast',
  },
  {
    id: 'shipped-arm-decision',
    date: '2026-10-11',
    title: 'No shippable model changed the answers enough to replace keyword search',
    observed:
      'Each arm that could ship (keyword search, ONNX semantic search, ONNX hybrid, and ' +
      'keyword search re-ranked by an ONNX cross-encoder) retrieved for every golden ' +
      'question, gpt-6-luna answered from what it retrieved, and the pinned Judge scored ' +
      'the answers. On the 82 development cases (152 Required Facts), every arm was ' +
      'indistinguishable from keyword search on Fact Recall: the most lopsided split, ' +
      'hybrid’s 20 facts gained to 15 lost, has a sign-test p of 0.50. They were also ' +
      'indistinguishable on Faithfulness and Decline accuracy. The 49 held-out cases (112 ' +
      'Required Facts) gave the same result. The re-ranking arm came closest there (12 ' +
      'gained, 4 lost, p = 0.077), and its ~1s warm Latency Band rules it out anyway. This ' +
      'is not a win for keyword search; with this many cases the arms cannot be told apart.',
    changed:
      'Keyword search stays the shipped arm by ADR-0009’s default, so the shipped flag, the ' +
      'production dependencies and the image are unchanged. Telling these arms apart needs ' +
      'more of the paraphrase, conceptual and visitor questions they disagree on.',
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#result-no-candidate-arm-qualifies-keyword-search-stays-shipped',
  },
  {
    id: 'generation-model-chosen',
    date: '2026-10-11',
    title: 'The cheapest OpenAI model answered more faithfully than the Groq model it replaces',
    observed:
      'Given the exact chunks the Groq baseline answered from, gpt-6-luna and Groq differed ' +
      'on 10 held-out answers where only one of them wrote an unsupported sentence. Every ' +
      'one was Groq’s, a split a sign test rules out as chance (Faithfulness 0.762 → 0.986). ' +
      'gpt-6.1-sol conveyed more Required Facts (Fact Recall 0.782 vs 0.701) but was ' +
      'indistinguishable from Luna on Faithfulness and Decline accuracy, at about 22× the ' +
      'cost per answer ($0.0028 vs $0.00012). The decision was made on dev, and held-out gave ' +
      'the same answer.',
    changed:
      'Chose gpt-6-luna as the production generation model under the written rule ' +
      '(cheapest unless distinguishably worse; Fact Recall alone never justifies an ' +
      'upgrade), and added a replay mode so candidate models answer from stored contexts.',
    move: {
      metric: 'Faithfulness',
      before: 0.762,
      after: 0.986,
      arm: 'Groq gpt-oss-120b → gpt-6-luna, Keyword only, held-out (39 questions)',
    },
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#choosing-the-generation-model',
  },
  {
    id: 'structure-aware-chunking',
    date: '2026-10-11',
    title: 'Cutting the corpus along its sources’ structure moved no arm beyond noise',
    observed:
      'Re-chunking the corpus from ~1,000-character packs into one chunk per question and ' +
      'answer, project section and resume role (123 chunks to 157) was measured on the 54 ' +
      'development questions. Keyword search gained four questions and lost one, including ' +
      '“Where is David based?”, which had missed although its answer chunk contained the ' +
      'question. No arm’s gains and losses were lopsided enough to rule out chance (exact sign ' +
      'test, p ≥ 0.375). Its five remaining misses are vocabulary gaps — “study in college” ' +
      'against “Major: Biochemistry”, “national defense vetting” against “security clearance” — ' +
      'that no stemmer bridges.',
    changed:
      'The index build has one chunking entry point with one rule per source, every chunk ' +
      'carries the heading that says what it is about, and a source that stops parsing into ' +
      'its structure now fails the build instead of indexing as one block. The tokenizer was ' +
      'left alone: no miss that survived re-chunking is a tokenizer problem. The floors were ' +
      're-checked, not edited — over the whole golden set keyword search cleared them at ' +
      'hit@5 0.885 and MRR 0.752, against 0.85 and 0.75.',
    move: {
      metric: 'hit@5',
      before: 0.852,
      after: 0.907,
      arm: 'Keyword only (development questions, all 54)',
    },
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#chunks-cut-along-source-structure-moved-no-arm-beyond-noise',
  },
  {
    id: 'query-categories-evaluated',
    date: '2026-09-13',
    title: 'Query categories revealed where dense and re-ranking models beat keyword search',
    observed:
      'Expanding the Golden Set to 87 cases across direct, paraphrase, and conceptual ' +
      'queries exposed where keyword search succeeds and where semantic retrieval excels. ' +
      'While BM25 dominated direct in-vocabulary questions (hit@5 0.964 vs dense’s 0.818), ' +
      'out-of-vocabulary paraphrases reversed the ordering: hybrid and re-ranking arms ' +
      'achieved hit@5 0.938 compared to BM25’s 0.875, and re-ranking lifted MRR from 0.617 to 0.828 ' +
      'over the full set. Across all 87 questions, the shipped BM25 arm maintained hit@5 0.908 ' +
      'and MRR 0.765, comfortably clearing production regression floors.',
    changed:
      'Categorized the benchmark into direct, paraphrase, and conceptual partitions and ' +
      'shipped interactive Scoreboard filtering in Schema Version 3. Production remains ' +
      'on BM25 for its low latency, light footprint, and strong overall hit rate, but the ' +
      'diagnostic breakdown proves dense retrieval and cross-encoder re-ranking provide ' +
      'measurable recall and reciprocal-rank gains on natural, out-of-vocabulary queries.',
    move: {
      metric: 'MRR',
      before: 0.617,
      after: 0.828,
      arm: 'Both combined, then re-ranked (paraphrase queries, all 16)',
    },
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#query-categories-expose-where-semantic-retrieval-excels',
  },
  {
    id: 'dense-stage-deleted',
    date: '2026-09-05',
    title: 'Plain keyword search beat the hybrid pipeline, so the architecture was deleted',
    observed:
      'On the 73-chunk corpus, across all 55 labelled questions, BM25 alone scored hit@5 ' +
      '0.982 against the shipped hybrid + cross-encoder pipeline’s 0.909, and led every ' +
      'other metric too. (The table above reports the held-out 22 only, so its numbers ' +
      'are the same finding on a smaller sample.) The tempting ' +
      'reaction was to retune the fusion weights, which would have been the wrong ' +
      'experiment: under reciprocal-rank fusion, driving the dense weight toward zero just ' +
      'converges on BM25’s ordering, so “find the optimal ratio” and “turn dense off” are ' +
      'the same question. A new arm asked it directly — BM25 candidates fed straight to the ' +
      'cross-encoder, no dense stage — and beat the full pipeline on hit@5, recall@5 and ' +
      'nDCG@5 on every split. The dense stage was contributing nothing the re-ranker could ' +
      'not recover. The cross-encoder then failed the same test against BM25 alone: it tied ' +
      'on hit@5 everywhere and lost on recall@5 and nDCG@5. Its one advantage was MRR on ' +
      'the development questions, and that reversed on the held-out ones — which is the ' +
      'comparison holding a portion back exists to make possible.',
    changed:
      'Production retrieval is now BM25 and nothing else. That took the semantic search ' +
      'stage, the fusion step and the cross-encoder off the serving path, and with them ' +
      '~500MB of model weights baked into the container image and the faiss-cpu and ' +
      'sentence-transformers dependencies — 87 production packages down to 40, and no model ' +
      'loading on a cold start. Cheaper and better is a stronger outcome than a tuned ' +
      'constant, and it is not the one the architecture was built expecting. Every deleted ' +
      'stage is still measured as an arm on every run: this corpus is written as anticipated ' +
      'questions and answers, exactly the condition that flatters lexical search, so the ' +
      'conclusion is expected to flip as the corpus grows and the harness should be what ' +
      'says so. The golden set was also split into development and held-out portions, and ' +
      'the published table now reports the held-out 22 — an architecture chosen by a ' +
      'measurement must not be scored by the questions that chose it. The container image ' +
      'went from 17.2GB to 544MB, most of it not model weights but the CUDA libraries that ' +
      'torch pulls in behind the embedding model, shipped into a container with no GPU.',
    move: {
      metric: 'hit@5',
      before: 0.909,
      after: 0.982,
      arm: 'shipped configuration, all 55 questions',
    },
    href: 'https://github.com/dwest1507/portfolio/blob/main/docs/evaluation.md#the-pipeline-lost-to-plain-keyword-search',
  },
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
