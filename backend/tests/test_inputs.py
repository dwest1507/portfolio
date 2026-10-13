"""Tests for the retrieval eval's input fingerprint (#97).

A run whose inputs match the published fingerprint is skipped, gate included, so the
fingerprint must move with everything that can move a measurement, and with nothing else.
The release-please version bump is the case that motivated it: it rewrites
`backend/uv.lock` without changing anything measured.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eval import inputs
from eval.inputs import (
    LOCKFILE,
    PYPROJECT,
    RETRIEVAL_INPUTS,
    lockfile_digest,
    published_fingerprint,
    retrieval_inputs_fingerprint,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "retrieval-eval.yml"

LOCK = """\
version = 1
revision = 5
requires-python = ">=3.14"

[[package]]
name = "backend"
version = "1.4.0"
source = { virtual = "." }
dependencies = [
    { name = "sentence-transformers" },
]

[[package]]
name = "sentence-transformers"
version = "5.1.0"
source = { registry = "https://pypi.org/simple" }
"""


def _release(lock: str, version: str) -> str:
    """The lockfile as release-please leaves it: only the backend package's version moved."""
    return lock.replace(
        'name = "backend"\nversion = "1.4.0"', f'name = "backend"\nversion = "{version}"'
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A minimal repository holding every retrieval input."""
    for entry in RETRIEVAL_INPUTS:
        path = tmp_path / entry
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"contents of {entry}\n", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)
            (path / "a.txt").write_text(f"a file in {entry}\n", encoding="utf-8")
    (tmp_path / PYPROJECT).write_text(
        '[project]\nname = "backend"\nversion = "1.4.0" # x-release-please-version\n',
        encoding="utf-8",
    )
    (tmp_path / LOCKFILE).write_text(LOCK, encoding="utf-8")
    return tmp_path


class TestLockfileDigest:
    def test_ignores_the_projects_own_version(self):
        assert lockfile_digest(_release(LOCK, "1.4.1"), "backend") == lockfile_digest(
            LOCK, "backend"
        )

    def test_a_dependency_version_changes_it(self):
        bumped = LOCK.replace('version = "5.1.0"', 'version = "5.2.0"')
        assert lockfile_digest(bumped, "backend") != lockfile_digest(LOCK, "backend")

    def test_a_new_dependency_changes_it(self):
        added = LOCK + '\n[[package]]\nname = "onnxruntime"\nversion = "1.23.0"\n'
        assert lockfile_digest(added, "backend") != lockfile_digest(LOCK, "backend")

    def test_the_committed_lockfile_ignores_a_release_bump(self):
        """The real uv.lock, bumped the way release-please bumps it (#95)."""
        text = (REPO_ROOT / LOCKFILE).read_text(encoding="utf-8")
        released, count = re.subn(r'(name = "backend"\nversion = )"[^"]+"', r'\g<1>"99.0.0"', text)
        assert count == 1
        assert lockfile_digest(released, "backend") == lockfile_digest(text, "backend")


class TestRetrievalInputsFingerprint:
    def test_a_release_bump_leaves_it_alone(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / LOCKFILE).write_text(_release(LOCK, "1.4.1"), encoding="utf-8")
        (repo / PYPROJECT).write_text(
            '[project]\nname = "backend"\nversion = "1.4.1" # x-release-please-version\n',
            encoding="utf-8",
        )
        assert retrieval_inputs_fingerprint(repo) == before

    def test_a_dependency_change_alters_it(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        bumped = LOCK.replace('version = "5.1.0"', 'version = "5.2.0"')
        (repo / LOCKFILE).write_text(bumped, encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) != before

    def test_a_corpus_change_alters_it(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / "docs/resume.txt").write_text("a new role\n", encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) != before

    def test_a_new_project_page_alters_it(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / "frontend/content/projects/new.mdx").write_text("# New\n", encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) != before

    def test_a_golden_set_change_alters_it(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / "backend/eval/golden_set.json").write_text('{"cases": []}\n', encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) != before

    @pytest.mark.parametrize(
        "path",
        [
            "backend/app/rag/a.txt",
            "backend/indexes/a.txt",
            "backend/eval/run_eval.py",
            "backend/eval/floors/retrieval.json",
            "scripts/backend-eval.sh",
        ],
    )
    def test_any_other_input_alters_it(self, repo, path):
        before = retrieval_inputs_fingerprint(repo)
        (repo / path).write_text("edited\n", encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) != before

    def test_deleting_an_input_alters_it(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / "docs/chatbot-questions.md").unlink()
        assert retrieval_inputs_fingerprint(repo) != before

    def test_a_file_outside_the_inputs_leaves_it_alone(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        (repo / "CHANGELOG.md").write_text("## 1.4.1\n", encoding="utf-8")
        (repo / "backend/eval/generation.py").write_text("edited\n", encoding="utf-8")
        assert retrieval_inputs_fingerprint(repo) == before

    def test_bytecode_caches_leave_it_alone(self, repo):
        before = retrieval_inputs_fingerprint(repo)
        cache = repo / "backend/app/rag/__pycache__"
        cache.mkdir()
        (cache / "pipeline.cpython-314.pyc").write_bytes(b"\x00")
        assert retrieval_inputs_fingerprint(repo) == before


class TestPublishedFingerprint:
    def test_reads_the_published_runs_fingerprint(self, tmp_path):
        path = tmp_path / "evalResults.json"
        path.write_text(json.dumps({"inputsFingerprint": "sha256:abc"}), encoding="utf-8")
        assert published_fingerprint(path) == "sha256:abc"

    def test_a_run_without_one_never_matches(self, tmp_path):
        path = tmp_path / "evalResults.json"
        path.write_text(json.dumps({"commit": "8699e89"}), encoding="utf-8")
        assert published_fingerprint(path) is None
        assert published_fingerprint(tmp_path / "missing.json") is None


class TestMain:
    def test_skips_when_the_inputs_match(self, repo, monkeypatch, capsys):
        results = repo / "evalResults.json"
        results.write_text(
            json.dumps(
                {"commit": "8699e89", "inputsFingerprint": retrieval_inputs_fingerprint(repo)}
            ),
            encoding="utf-8",
        )
        monkeypatch.setattr(inputs, "RESULTS_PATH", results)
        monkeypatch.setattr(
            inputs, "retrieval_inputs_fingerprint", lambda: retrieval_inputs_fingerprint(repo)
        )
        assert inputs.main() == 0
        assert "unchanged since the published Measured Run at 8699e89" in capsys.readouterr().out

    def test_measures_when_they_differ(self, repo, monkeypatch, capsys):
        results = repo / "evalResults.json"
        results.write_text(json.dumps({"inputsFingerprint": "sha256:old"}), encoding="utf-8")
        monkeypatch.setattr(inputs, "RESULTS_PATH", results)
        monkeypatch.setattr(
            inputs, "retrieval_inputs_fingerprint", lambda: retrieval_inputs_fingerprint(repo)
        )
        assert inputs.main() == 1
        assert "Retrieval inputs changed" in capsys.readouterr().out


def _workflow_paths(trigger: str) -> list[str]:
    """The path filter under `trigger` in retrieval-eval.yml, comments dropped."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {trigger}:")
    paths = []
    for line in lines[start + 1 :]:
        if line and not line.startswith("    "):
            break
        match = re.fullmatch(r"\s+- '([^']+)'", line)
        if match:
            paths.append(match.group(1))
    return paths


class TestWorkflowPathFilter:
    def test_pull_request_and_push_lists_match(self):
        assert _workflow_paths("pull_request") == _workflow_paths("push")

    def test_it_covers_exactly_the_fingerprinted_inputs(self):
        """A filtered-out input would never be measured; an extra path would run for nothing
        but the skip. The workflow itself is the one path that is not an input."""
        expected = {
            entry if (REPO_ROOT / entry).is_file() else f"{entry}/**" for entry in RETRIEVAL_INPUTS
        }
        expected |= {LOCKFILE, ".github/workflows/retrieval-eval.yml"}
        assert set(_workflow_paths("pull_request")) == expected

    def test_every_input_exists(self):
        for entry in RETRIEVAL_INPUTS:
            assert (REPO_ROOT / entry).exists(), entry
