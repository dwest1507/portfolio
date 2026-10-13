---
status: accepted
---

# The torch Reference Arms are retired

Supersedes ADR-0009's clause that "the existing torch-based Arms remain as Reference
Arms". ADR-0009's selection rule, and its restriction to Candidate Arms, stand unchanged.

ADR-0009 kept the four torch-based Arms (`dense`, `hybrid`, `rerank`, `bm25+rerank`) as
baselines beside the Candidate Arms that run the same models on ONNX Runtime. Measured
side by side, they turned out not to be baselines. `onnx-dense` and `onnx-hybrid` matched
`dense` and `hybrid` on all four retrieval metrics for 68 of 68 development questions (158
Chunks), the embeddings agreed to a cosine similarity of 0.9999999, and the cross-encoder
logits put every candidate in the same order (`docs/evaluation.md`, "ONNX Runtime
reproduces the torch models; it does not run them as fast"). A Reference Arm that matches
a Candidate Arm shows no ceiling the Candidates do not already reach. PR #82 had already
hidden them from the Scoreboard for that reason.

They cost no API money: `eval/compare_arms.py` never sent them through generation. They
did cost:

- **CI time on every backend PR.** `sentence-transformers` (with torch and CUDA wheels)
  and `faiss-cpu` sat in the `dev` group that all three Backend CI jobs install, lint
  included. The two torch re-ranking Arms took about 65s of the retrieval gate pass.
- **Code kept only for them**: the FAISS index and its build step, and the
  sentence-transformers paths in `app/rag/pipeline.py`.
- **Concepts kept only for them** in `CONTEXT.md`, ADR-0009 and the published schema.

## Decisions

- The four torch Arms leave `ARM_SPECS`, the pipeline, the index build and the tests.
  `faiss.index` is deleted. `sentence-transformers` and `faiss-cpu` leave the `dev`
  dependency group, so no Backend CI job installs torch, CUDA or FAISS.
- Their published measurements stay where they are. The parity section of
  `docs/evaluation.md` and the `onnx-matches-torch` Findings Log entry are the historical
  record.
- **Reference Arm stays a concept, with none measured at present.** The published schema
  keeps `eligibility`, and the Scoreboard keeps showing Candidate Arms only. An Arm added
  later on purpose as a quality ceiling, too heavy to ship, stays off the public page
  without a frontend change. ADR-0009's "no new Reference Arms" still holds by default:
  adding one is a decision that needs its own record.
- The Floors record is untouched. Floors gate only the Shipped Arm (`bm25`), and the
  fingerprint hashes only the Golden Set.

## Measured effect on Backend CI

Job durations, summed over the three Backend CI jobs. "Cold" is the first run after
`uv.lock` changed, so its uv and Hugging Face cache keys miss and fall back to the nearest
prefix. "Warm" reuses an exact cache hit.

| | Lint | Pytest | Retrieval eval (gate step) | Total |
|---|---:|---:|---:|---:|
| Before, warm ([38282825424](https://github.com/dwest1507/portfolio/actions/runs/38282825424), PR) | 32s | 50s | 3m58s (3m16s) | 5m20s |
| Before, cold ([38287836696](https://github.com/dwest1507/portfolio/actions/runs/38287836696), `main`) | 37s | 47s | 5m33s (4m53s) | 6m57s |
| After, cold ([38326712284](https://github.com/dwest1507/portfolio/actions/runs/38326712284), dispatch) | 11s | 20s | 1m57s (1m27s) | 2m28s |
| After, warm ([38326916635](https://github.com/dwest1507/portfolio/actions/runs/38326916635), dispatch) | 9s | 15s | 1m54s (1m29s) | 2m18s |

The cold "before" run was a push to `main`, so its gate step also ran the held-out publish
pass (about 66s) and its job a publish step. No pull request run since the last lockfile
change was cold, so this is the closest comparison available. The "after" runs restored
the old Hugging Face cache entry by prefix, torch weights included, so the cache entry
has not shrunk yet. Re-keying that cache is #99.

## Consequences

- Every Arm in the harness could ship, so every Arm `make eval` measures is also one
  `eval/compare_arms.py` runs through generation.
- The ONNX Arms are no longer checked against torch on every run. If the ONNX exports or
  `app/rag/onnx_models.py` drift from what sentence-transformers computes, nothing in CI
  will notice. The pinned Hub revisions in `onnx_models.py` are what stop the exports
  changing on their own.
