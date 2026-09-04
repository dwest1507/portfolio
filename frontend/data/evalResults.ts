/**
 * Measured retrieval-eval results for the portfolio chatbot.
 *
 * These are real numbers, not illustrations. To refresh them after a pipeline
 * or corpus change, run the harness and copy the reported figures:
 *
 *     make eval                                  # prints the arm table
 *     uv run python eval/run_eval.py --json out.json
 *
 * Source of the values below: the `Retrieval eval` job of Backend CI, which is
 * the environment that has the model weights available.
 */

export interface EvalArm {
  /** Harness arm name, matching `--arms` in eval/run_eval.py. */
  id: string
  label: string
  /** What this configuration actually does. */
  description: string
  recallAt5: number
  hitAt5: number
  mrr: number
  ndcgAt5: number
}

export interface EvalRun {
  /** Number of chunks in the indexed corpus. */
  corpusChunks: number
  /** Number of labelled questions in the golden set. */
  goldenQuestions: number
  /** Commit the run was measured on. */
  commit: string
  /** Link to the CI job that produced these numbers. */
  runUrl: string
  arms: EvalArm[]
}

export const evalRun: EvalRun = {
  corpusChunks: 49,
  goldenQuestions: 55,
  commit: 'ee674f2',
  runUrl: 'https://github.com/dwest1507/portfolio/actions/runs/33891968483',
  arms: [
    {
      id: 'bm25',
      label: 'BM25 only',
      description: 'Keyword search. Stemmed, stopword-filtered terms.',
      recallAt5: 0.73,
      hitAt5: 1.0,
      mrr: 0.892,
      ndcgAt5: 0.758,
    },
    {
      id: 'dense',
      label: 'Dense only',
      description: 'FAISS semantic search over all-mpnet-base-v2 vectors.',
      recallAt5: 0.571,
      hitAt5: 0.818,
      mrr: 0.688,
      ndcgAt5: 0.588,
    },
    {
      id: 'hybrid',
      label: 'Hybrid',
      description: 'Weighted reciprocal-rank fusion of both retrievers.',
      recallAt5: 0.653,
      hitAt5: 0.927,
      mrr: 0.75,
      ndcgAt5: 0.651,
    },
    {
      id: 'rerank',
      label: 'Hybrid + re-rank',
      description: 'Hybrid candidates re-ordered by a cross-encoder.',
      recallAt5: 0.652,
      hitAt5: 0.909,
      mrr: 0.853,
      ndcgAt5: 0.698,
    },
  ],
}

/** The arm that scored best on a given metric — used to mark the winner. */
export function bestArmId(metric: keyof Omit<EvalArm, 'id' | 'label' | 'description'>): string {
  return evalRun.arms.reduce((best, arm) => (arm[metric] > best[metric] ? arm : best)).id
}
