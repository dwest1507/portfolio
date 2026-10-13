"""The retrieval eval's input fingerprint: can a Measured Run differ from the published one?

The retrieval eval is deterministic. Given the same Corpus, indexes, retrieval code,
harness, Golden Set, retrieval Floors record and locked dependencies, it measures the same
numbers and reaches the same gate verdict. So when a run's inputs hash to the fingerprint
recorded in `frontend/data/evalResults.json`, measuring again can only repeat what was
published, and `scripts/backend-eval.sh` skips it (#97).

The one input that changes for unrelated reasons is `backend/uv.lock`: every release bumps
the `backend` package's own version inside it. That line cannot move a measurement, so it
is stripped before hashing. Every other lockfile change (a real dependency bump of
onnxruntime, tokenizers, rank-bm25, ...) changes the fingerprint.

This follows the Floors records' fingerprints (ADR-0012), but hashes files, not cases.
Usage:

    uv run --frozen python eval/inputs.py   # exit 0: unchanged since the published run
                                            # exit 1: changed, or nothing published yet
"""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from eval.recalibration import fingerprint  # (needs the sys.path line above)

#: Everything a retrieval Measured Run depends on, relative to the repository root, apart
#: from the lockfile. A directory stands for every file under it. Keep this in step with the
#: path filter in .github/workflows/retrieval-eval.yml; a test checks that they agree.
RETRIEVAL_INPUTS = (
    # Retrieval as production runs it, the indexes, and the script that builds them
    "backend/app/rag",
    "backend/indexes",
    "backend/scripts/build_index.py",
    # The Corpus sources
    "docs/resume.txt",
    "docs/chatbot-questions.md",
    "frontend/content/projects",
    # The retrieval harness, this fingerprint included, and the script that runs it
    "backend/eval/run_eval.py",
    "backend/eval/publish.py",
    "backend/eval/recalibration.py",
    "backend/eval/inputs.py",
    "scripts/backend-eval.sh",
    # The Golden Set and the retrieval Floors record
    "backend/eval/golden_set.json",
    "backend/eval/floors/retrieval.json",
)

#: Hashed with the project's own version stripped; see `lockfile_digest`.
LOCKFILE = "backend/uv.lock"
PYPROJECT = "backend/pyproject.toml"

RESULTS_PATH = REPO_ROOT / "frontend" / "data" / "evalResults.json"


def _files(root: Path, entry: str) -> list[Path]:
    """The files an input entry names: the file itself, or every file under a directory.

    Bytecode caches are a local artefact of running the code, never an input.
    """
    path = root / entry
    if path.is_file():
        return [path]
    return sorted(
        p
        for p in path.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )


def lockfile_digest(lock_text: str, project: str) -> str:
    """A hash of `uv.lock` that ignores the project's own version.

    Release-please rewrites that one line on every release. The project is a virtual
    package that nothing measured depends on by version, so the line cannot move a metric;
    every other field, and every other package's version, is kept.
    """
    lock = tomllib.loads(lock_text)
    for package in lock.get("package", []):
        if package.get("name") == project:
            package.pop("version", None)
    return fingerprint(lock)


def retrieval_inputs_fingerprint(root: Path = REPO_ROOT) -> str:
    """The fingerprint of every input a retrieval Measured Run depends on, under `root`.

    A listed path that does not exist hashes as absent, so deleting an input changes the
    fingerprint too.
    """
    files: dict[str, str | None] = {}
    for entry in RETRIEVAL_INPUTS:
        found = _files(root, entry)
        if not found:
            files[entry] = None
        for path in found:
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()

    project = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))["project"]["name"]
    files[LOCKFILE] = lockfile_digest((root / LOCKFILE).read_text(encoding="utf-8"), project)
    return fingerprint(files)


def published_fingerprint(results_path: Path = RESULTS_PATH) -> str | None:
    """The input fingerprint the published Measured Run was measured with, if it has one."""
    try:
        document = json.loads(results_path.read_text(encoding="utf-8"))
    except FileNotFoundError, json.JSONDecodeError:
        return None
    return document.get("inputsFingerprint")


def main() -> int:
    current = retrieval_inputs_fingerprint()
    published = published_fingerprint(RESULTS_PATH)
    if published == current:
        commit = json.loads(RESULTS_PATH.read_text(encoding="utf-8")).get("commit")
        print(
            f"Retrieval inputs unchanged since the published Measured Run at {commit} "
            f"({current[:19]}…): skipping the eval. Its gate verdict cannot differ. "
            "Set EVAL_FORCE=1 to measure anyway."
        )
        return 0
    print(
        f"Retrieval inputs changed (published {(published or 'none')[:19]}…, "
        f"now {current[:19]}…): measuring."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
