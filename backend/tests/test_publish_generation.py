"""Tests for the published generation results document (ADR-0007).

Mirrors tests/test_publish.py: the document is built from a judged run's output alone, so
none of these call a model. Generation metrics move from run to run on an unchanged
commit, so what these pin down above all is that noise alone never rewrites the file.
"""

from __future__ import annotations

import json

import pytest

from eval.publish_generation import (
    SCHEMA_VERSION,
    STEPS,
    build_section,
    write_section,
)


def _case(
    case_id: str,
    split: str = "holdout",
    supported: int = 9,
    unsupported: int = 1,
    conveyed: int = 3,
    missed: int = 1,
    answerable: bool = True,
    declined: bool = False,
    usage: dict | None = None,
    model: str = "gpt-6-luna-2026-08-01",
) -> dict:
    """One judged case, as run_generation returns it, built from counts."""
    sentences = [{"text": "s", "supported": True}] * supported
    sentences += [{"text": "s", "supported": False}] * unsupported
    facts = [{"fact": "f", "conveyed": True}] * conveyed + [
        {"fact": "f", "conveyed": False}
    ] * missed
    return {
        "id": case_id,
        "split": split,
        "answerable": answerable,
        "declined": declined,
        "sentences": sentences if answerable and not declined else [],
        "facts": facts if answerable else [],
        "contradictions": [],
        "usage": usage or {"prompt_tokens": 1000, "completion_tokens": 200, "total_tokens": 1200},
        "model": model,
    }


def _run(cases: list[dict] | None = None, judge: str = "jev-1.13.0") -> dict:
    return {
        "cases": cases if cases is not None else [_case("a"), _case("b")],
        "judge": judge,
        "splitter": "gpt-6-luna-2026-08-01",
    }


def _section(run: dict | None = None, **kwargs) -> dict:
    defaults = {
        "arm": "bm25",
        "requested_model": "gpt-6-luna",
        "reasoning_effort": "low",
        "corpus_chunks": 123,
    }
    section = build_section(run or _run(), **{**defaults, **kwargs})
    section["runUrl"] = "https://example.test/run/1"
    return section


def _published(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# A section
# ---------------------------------------------------------------------------


class TestSection:
    def test_metrics_are_rounded_to_each_metrics_step(self):
        """Steps from the spread study: 0.1, 0.05 and 0.005 (docs/evaluation.md)."""
        assert STEPS == {"factRecall": 0.1, "faithfulness": 0.05, "declineAccuracy": 0.005}

        # Faithfulness 18/20 = 0.9; Fact Recall 6/8 = 0.75 → 0.8; Decline accuracy 1.0.
        section = _section()

        assert section["metrics"] == {
            "factRecall": 0.8,
            "faithfulness": 0.9,
            "declineAccuracy": 1.0,
        }
        assert section["steps"] == STEPS

    def test_only_the_held_out_split_is_published(self):
        """A dev number is one a decision was made on; publishing it would flatter it."""
        run = _run([_case("a"), _case("dev-case", split="dev", supported=0, unsupported=10)])

        section = _section(run)

        assert section["split"] == "holdout"
        assert section["questions"] == 1
        assert section["metrics"]["faithfulness"] == 0.9

    def test_counts_answerable_and_out_of_scope_questions(self):
        run = _run([_case("a"), _case("oos", answerable=False, declined=True)])

        section = _section(run)

        assert (section["questions"], section["answerable"], section["outOfScope"]) == (2, 1, 1)

    def test_records_what_was_measured(self):
        section = _section()

        assert section["arm"] == "bm25"
        assert section["armLabel"] == "Keyword only"
        assert section["generationModel"] == "gpt-6-luna-2026-08-01"
        assert section["reasoningEffort"] == "low"
        assert section["judge"] == "jev-1.13.0"
        assert section["splitter"] == "gpt-6-luna-2026-08-01"
        assert section["corpusChunks"] == 123

    def test_cost_per_answer_comes_from_billed_usage(self):
        """Luna bills $0.10 per million input tokens and $0.50 per million output tokens.

        1,000 prompt tokens ($0.0001) and 200 completion tokens ($0.0001) is $0.0002.
        """
        assert _section()["costPerAnswerUsd"] == 0.0002

    def test_cost_per_answer_is_rounded_to_one_significant_figure(self):
        """Billed tokens vary with every reworded answer; the cost moves only by a digit.

        Means of $0.000205 and $0.000195 both publish as $0.0002.
        """
        more = {"prompt_tokens": 1000, "completion_tokens": 210, "total_tokens": 1210}
        less = {"prompt_tokens": 1000, "completion_tokens": 190, "total_tokens": 1190}

        assert _section(_run([_case("a", usage=more)]))["costPerAnswerUsd"] == 0.0002
        assert _section(_run([_case("a", usage=less)]))["costPerAnswerUsd"] == 0.0002

    def test_refuses_a_model_with_no_recorded_price(self):
        """A published cost nothing priced would be invented."""
        with pytest.raises(ValueError, match="gpt-7"):
            _section(requested_model="gpt-7")

    def test_refuses_an_arm_with_no_published_description(self):
        with pytest.raises(ValueError, match="no-such-arm"):
            _section(arm="no-such-arm")


# ---------------------------------------------------------------------------
# Writing a section
# ---------------------------------------------------------------------------


class TestWriteSection:
    def test_writes_a_document_with_both_sections(self, tmp_path):
        path = tmp_path / "generationResults.json"

        _, written = write_section("shippedArm", _section(), path)

        published = _published(path)
        assert written is True
        assert published["schemaVersion"] == SCHEMA_VERSION
        assert published["shippedArm"]["metrics"]["faithfulness"] == 0.9
        assert published["comparison"] is None

    def test_rounding_suppresses_a_noise_only_rewrite(self, tmp_path):
        """Faithfulness 0.957 and 0.940 both round to 0.95: the same measurement.

        Those are two of the three held-out values the spread study measured on one
        commit. Unrounded, every push to main would commit a re-measurement of noise.
        """
        path = tmp_path / "generationResults.json"
        write_section(
            "shippedArm", _section(_run([_case("a", supported=957, unsupported=43)])), path
        )
        before = path.read_text(encoding="utf-8")

        rerun = _section(_run([_case("a", supported=940, unsupported=60)]))
        rerun["commit"] = "deadbee"
        rerun["generatedAt"] = "2027-01-01T00:00:00+00:00"
        rerun["runUrl"] = "https://example.test/run/2"
        document, written = write_section("shippedArm", rerun, path)

        assert written is False
        assert path.read_text(encoding="utf-8") == before
        assert document == json.loads(before)

    def test_a_move_beyond_the_step_is_published(self, tmp_path):
        path = tmp_path / "generationResults.json"
        write_section("shippedArm", _section(_run([_case("a", supported=95, unsupported=5)])), path)

        moved = _section(_run([_case("a", supported=85, unsupported=15)]))
        _, written = write_section("shippedArm", moved, path)

        assert written is True
        assert _published(path)["shippedArm"]["metrics"]["faithfulness"] == 0.85

    def test_a_changed_generation_model_is_a_new_measurement(self, tmp_path):
        """The same numbers from a different model describe a different chatbot."""
        path = tmp_path / "generationResults.json"
        write_section("shippedArm", _section(), path)

        sol = _run(
            [_case("a", model="gpt-6.1-sol-2026-09-01"), _case("b", model="gpt-6.1-sol-2026-09-01")]
        )
        _, written = write_section("shippedArm", _section(sol, requested_model="gpt-6.1-sol"), path)

        assert written is True
        assert _published(path)["shippedArm"]["generationModel"] == "gpt-6.1-sol-2026-09-01"

    def test_a_changed_judge_version_is_a_new_measurement(self, tmp_path):
        """A Judge upgrade can move every number without the chatbot changing at all."""
        path = tmp_path / "generationResults.json"
        write_section("shippedArm", _section(), path)

        _, written = write_section("shippedArm", _section(_run(judge="jev-1.14.0")), path)

        assert written is True
        assert _published(path)["shippedArm"]["judge"] == "jev-1.14.0"

    def test_sections_keep_separate_provenance(self, tmp_path):
        """A comparison run publishes its rows without touching the Shipped Arm's, and the
        reverse: rows from different runs never share one table or one commit."""
        path = tmp_path / "generationResults.json"
        shipped = _section()
        shipped["commit"] = "main123"
        write_section("shippedArm", shipped, path)

        comparison = _section(_run([_case("a", supported=5, unsupported=5)]))
        comparison["commit"] = "cmp4567"
        comparison["runUrl"] = "https://example.test/run/9"
        write_section("comparison", comparison, path)

        published = _published(path)
        assert published["shippedArm"]["commit"] == "main123"
        assert published["shippedArm"]["runUrl"] == "https://example.test/run/1"
        assert published["shippedArm"]["metrics"]["faithfulness"] == 0.9
        assert published["comparison"]["commit"] == "cmp4567"
        assert published["comparison"]["metrics"]["faithfulness"] == 0.5

    def test_an_unchanged_section_leaves_the_other_section_alone_too(self, tmp_path):
        path = tmp_path / "generationResults.json"
        write_section("shippedArm", _section(), path)
        write_section("comparison", _section(), path)
        before = path.read_text(encoding="utf-8")

        _, written = write_section("shippedArm", _section(), path)

        assert written is False
        assert path.read_text(encoding="utf-8") == before

    def test_a_ci_run_replaces_a_local_one_even_when_nothing_moved(self, tmp_path):
        """As for retrieval: a local run's bare commit must not stay on the page forever."""
        path = tmp_path / "generationResults.json"
        local = _section()
        local["runUrl"] = None
        write_section("shippedArm", local, path)

        from_ci = _section()
        from_ci["commit"] = "ci12345"
        _, written = write_section("shippedArm", from_ci, path)

        assert written is True
        assert _published(path)["shippedArm"]["commit"] == "ci12345"

    def test_the_takeover_happens_only_once(self, tmp_path):
        path = tmp_path / "generationResults.json"
        local = _section()
        local["runUrl"] = None
        write_section("shippedArm", local, path)
        write_section("shippedArm", _section(), path)

        second = _section()
        second["runUrl"] = "https://example.test/run/8"
        _, written = write_section("shippedArm", second, path)

        assert written is False

    def test_an_unparseable_file_is_overwritten(self, tmp_path):
        path = tmp_path / "generationResults.json"
        path.write_text("{ truncated", encoding="utf-8")

        _, written = write_section("shippedArm", _section(), path)

        assert written is True
        assert _published(path)["shippedArm"]["metrics"]["faithfulness"] == 0.9

    def test_rejects_an_unknown_section(self, tmp_path):
        with pytest.raises(ValueError, match="nightly"):
            write_section("nightly", _section(), tmp_path / "generationResults.json")
