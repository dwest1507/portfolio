"""The embedding model and the cross-encoder, run on ONNX Runtime instead of torch.

The Candidate Arms (ADR-0009) use these. They are the same two models the torch-based
Reference Arms load through sentence-transformers, exported to ONNX by their publishers,
so a production image could serve either without torch: ONNX Runtime, a tokenizer and the
weights, and nothing GPU-oriented.

Nothing here is on the serving path yet. onnxruntime, tokenizers and huggingface_hub are
in the `dev` dependency group until an Arm built on them is chosen to ship, so each is
imported inside the loader that needs it, never at module scope.

Each model is pinned to an exact Hub revision: a re-export upstream would otherwise change
what a Measured Run measured with nothing in the repository recording it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # imported for typing only; see the module docstring
    import onnxruntime
    from tokenizers import Tokenizer

EMBEDDING_MODEL = "sentence-transformers/all-mpnet-base-v2"
EMBEDDING_REVISION = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
#: sentence-transformers' max_seq_length for this model. The tokenizer file itself says
#: 128, which would truncate long Chunks the torch model reads in full.
EMBEDDING_MAX_TOKENS = 384

CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
CROSS_ENCODER_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
CROSS_ENCODER_MAX_TOKENS = 512

#: Texts per inference call. Bounds memory when the index builder embeds the Corpus.
BATCH_SIZE = 32


def _load(
    repo_id: str, revision: str, max_tokens: int
) -> tuple[Tokenizer, onnxruntime.InferenceSession]:
    """The model's tokenizer, padding to the longest text in a batch, and its ONNX session."""
    import onnxruntime
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    def fetch(filename: str) -> str:
        return hf_hub_download(repo_id, filename, revision=revision)

    tokenizer = Tokenizer.from_file(fetch("tokenizer.json"))
    pad_token = json.loads(Path(fetch("tokenizer_config.json")).read_text())["pad_token"]
    tokenizer.enable_truncation(max_length=max_tokens)
    tokenizer.enable_padding(pad_id=tokenizer.token_to_id(pad_token), pad_token=pad_token)

    session = onnxruntime.InferenceSession(
        fetch("onnx/model.onnx"), providers=["CPUExecutionProvider"]
    )
    return tokenizer, session


def _inputs(session: onnxruntime.InferenceSession, encodings) -> dict[str, np.ndarray]:
    """The arrays the session asks for, from a batch of tokenizer encodings."""
    available = {
        "input_ids": [e.ids for e in encodings],
        "attention_mask": [e.attention_mask for e in encodings],
        "token_type_ids": [e.type_ids for e in encodings],
    }
    return {i.name: np.asarray(available[i.name], dtype=np.int64) for i in session.get_inputs()}


class OnnxEmbedder:
    """Sentence embeddings: mean-pooled token states, L2-normalized, as sentence-transformers
    computes them for this model."""

    def __init__(self, tokenizer=None, session=None) -> None:
        if tokenizer is None or session is None:
            tokenizer, session = _load(EMBEDDING_MODEL, EMBEDDING_REVISION, EMBEDDING_MAX_TOKENS)
        self._tokenizer = tokenizer
        self._session = session

    def encode(self, texts: list[str]) -> np.ndarray:
        """One normalized float32 row per text."""
        rows = []
        for start in range(0, len(texts), BATCH_SIZE):
            encodings = self._tokenizer.encode_batch(texts[start : start + BATCH_SIZE])
            inputs = _inputs(self._session, encodings)
            (states,) = self._session.run(["last_hidden_state"], inputs)
            # Mean over real tokens only: padding positions carry states too.
            mask = inputs["attention_mask"][..., None].astype(np.float32)
            pooled = (states * mask).sum(axis=1) / np.clip(mask.sum(axis=1), 1e-9, None)
            norms = np.linalg.norm(pooled, axis=1, keepdims=True)
            rows.append(pooled / np.clip(norms, 1e-12, None))
        return np.concatenate(rows).astype(np.float32) if rows else np.zeros((0, 0), np.float32)


class OnnxCrossEncoder:
    """Relevance scores for (query, passage) pairs. Higher is more relevant.

    Raw logits: the torch CrossEncoder applies no activation to this model's single
    output, and any monotonic one would leave the ranking unchanged anyway.
    """

    def __init__(self, tokenizer=None, session=None) -> None:
        if tokenizer is None or session is None:
            tokenizer, session = _load(
                CROSS_ENCODER_MODEL, CROSS_ENCODER_REVISION, CROSS_ENCODER_MAX_TOKENS
            )
        self._tokenizer = tokenizer
        self._session = session

    def predict(self, pairs: list[list[str]]) -> np.ndarray:
        scores = []
        for start in range(0, len(pairs), BATCH_SIZE):
            batch = [tuple(p) for p in pairs[start : start + BATCH_SIZE]]
            encodings = self._tokenizer.encode_batch(batch)
            (logits,) = self._session.run(["logits"], _inputs(self._session, encodings))
            scores.append(logits[:, 0])
        return np.concatenate(scores) if scores else np.zeros(0, np.float32)
