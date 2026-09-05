"""Tests for the artefacts that publish a measured run.

None of these load a pipeline or download model weights: the point of eval/publish.py
being its own module is that the published document, the verdict, and the markdown block
can be checked from fixture numbers alone.
"""

from __future__ import annotations

import json

import pytest

from eval.publish import (
    ARM_SPEC_BY_ID,
    ARM_SPECS,
    ARMS,
    BEGIN_MARKER,
    END_MARKER,
    SCHEMA_VERSION,
    build_results_document,
    leading_arm,
    render_markdown,
    shipped_arm_id,
    update_markdown_block,
    verdict_line,
    write_results_document,
)


def _raw(arm: str, hit: float, mrr: float) -> dict:
    return {
        "arm": arm,
        "top_k": 5,
        "summary": {"recall@5": 0.5, "hit@5": hit, "mrr": mrr, "ndcg@5": 0.6},
        "cases": [],
    }


def _document(results=None, **kwargs) -> dict:
    defaults = {
        "corpus_chunks": 49,
        "golden_questions": 55,
        "top_k": 5,
        "gating_metric": "hit@5",
        "split": "all",
    }
    defaults.update(kwargs)
    return build_results_document(
        results or [_raw("bm25", 1.0, 0.892), _raw("rerank", 0.909, 0.853)], **defaults
    )


# ---------------------------------------------------------------------------
# Arm specs
# ---------------------------------------------------------------------------


class TestArmSpecs:
    def test_exactly_one_arm_is_shipped(self):
        """The verdict names the shipped arm, so an ambiguous flag has no answer."""
        assert [a.id for a in ARM_SPECS if a.shipped] == [shipped_arm_id()]

    def test_shipped_arm_matches_the_production_pipeline(self):
        """Guards the one fact that goes stale silently.

        RAGPipeline.retrieve is sparse_search and nothing else, so `bm25` is what
        production runs. If retrieve() changes shape, this flag has to move with it or
        the public page reports a configuration the site does not actually serve.
        """
        import inspect

        from app.rag.pipeline import RAGPipeline

        source = inspect.getsource(RAGPipeline.retrieve)
        assert "sparse_search" in source
        assert "hybrid_search" not in source and "self.rerank" not in source
        assert shipped_arm_id() == "bm25"

    def test_every_arm_has_both_registers_of_description(self):
        for arm in ARM_SPECS:
            assert arm.description and arm.technical
            assert arm.description != arm.technical

    def test_arms_tuple_is_derived_from_the_specs(self):
        assert ARMS == tuple(ARM_SPEC_BY_ID)


# ---------------------------------------------------------------------------
# The measured-run document
# ---------------------------------------------------------------------------


class TestResultsDocument:
    def test_carries_provenance_and_arm_metadata(self):
        doc = _document()
        assert doc["corpusChunks"] == 49
        assert doc["goldenQuestions"] == 55
        assert doc["gatingMetric"] == "hit@5"
        assert doc["split"] == "all"
        assert doc["metricNames"] == ["recall@5", "hit@5", "mrr", "ndcg@5"]

        bm25 = next(a for a in doc["arms"] if a["id"] == "bm25")
        assert bm25["label"] == ARM_SPEC_BY_ID["bm25"].label
        assert bm25["metrics"]["hit@5"] == 1.0
        assert bm25["shipped"] is True

        rerank = next(a for a in doc["arms"] if a["id"] == "rerank")
        assert rerank["shipped"] is False

    def test_metric_names_follow_the_cutoff(self):
        """--top-k 10 publishes hit@10, so nothing downstream may assume @5."""
        doc = _document(
            results=[
                {
                    "arm": "bm25",
                    "top_k": 10,
                    "summary": {"recall@10": 0.8, "hit@10": 1.0, "mrr": 0.9, "ndcg@10": 0.8},
                    "cases": [],
                }
            ],
            top_k=10,
            gating_metric="hit@10",
        )
        assert doc["metricNames"] == ["recall@10", "hit@10", "mrr", "ndcg@10"]

    def test_rejects_an_arm_with_no_published_description(self):
        with pytest.raises(ValueError, match="ARM_SPECS"):
            _document(results=[_raw("colbert", 1.0, 0.9)])

    def test_writes_json_the_frontend_can_import(self, tmp_path):
        path = tmp_path / "nested" / "evalResults.json"
        document, written = write_results_document(_document(), path)
        loaded = json.loads(path.read_text())
        assert written is True
        assert loaded == document
        assert loaded["schemaVersion"] == SCHEMA_VERSION
        assert {a["id"] for a in loaded["arms"]} == {"bm25", "rerank"}

    def test_writes_arrows_rather_than_escapes(self, tmp_path):
        """The published file is read by humans; \\u2192 in it is noise."""
        path = tmp_path / "evalResults.json"
        write_results_document(
            _document(results=[_raw("rerank", 0.9, 0.85)]),
            path,
        )
        assert "\u2192" in path.read_text(encoding="utf-8")

    def test_an_unchanged_measurement_leaves_the_file_alone(self, tmp_path):
        """Provenance moves on every run; a rewrite that only moves it is a false change.

        Rewriting unconditionally made the publishing job's "nothing to commit" branch
        unreachable, so every push to main committed a re-measurement that found nothing.
        """
        path = tmp_path / "evalResults.json"
        write_results_document(_document(), path)
        before = path.read_text(encoding="utf-8")

        rerun = _document()
        rerun["generatedAt"] = "2027-01-01T00:00:00+00:00"
        rerun["commit"] = "deadbee"
        document, written = write_results_document(rerun, path)

        assert written is False
        assert path.read_text(encoding="utf-8") == before
        assert document == json.loads(before)

    def test_a_changed_split_counts_as_a_new_measurement(self, tmp_path):
        """Identical metrics over a different sample are not the same measurement.

        `split` sits in MEASURED_KEYS for this reason: without it, switching what is
        published from the whole set to the held-out portion would leave the old
        document in place whenever the two happened to score alike.
        """
        path = tmp_path / "evalResults.json"
        write_results_document(_document(), path)

        _, written = write_results_document(_document(split="holdout"), path)

        assert written is True
        assert json.loads(path.read_text(encoding="utf-8"))["split"] == "holdout"

    def test_a_moved_metric_is_published(self, tmp_path):
        path = tmp_path / "evalResults.json"
        write_results_document(_document(), path)

        moved = _document(results=[_raw("bm25", 1.0, 0.892), _raw("rerank", 0.99, 0.99)])
        document, written = write_results_document(moved, path)

        assert written is True
        assert json.loads(path.read_text(encoding="utf-8")) == document

    def test_an_unparseable_file_is_overwritten(self, tmp_path):
        path = tmp_path / "evalResults.json"
        path.write_text("{ truncated", encoding="utf-8")

        _, written = write_results_document(_document(), path)

        assert written is True
        assert json.loads(path.read_text(encoding="utf-8"))["schemaVersion"] == SCHEMA_VERSION


# ---------------------------------------------------------------------------
# Derived claims
# ---------------------------------------------------------------------------


class TestVerdict:
    def test_names_the_leader_when_the_shipped_arm_loses(self):
        """The state the page was in before #23: production was not the best arm."""
        doc = _document(results=[_raw("bm25", 0.909, 0.853), _raw("dense", 1.0, 0.892)])
        line = verdict_line(doc)
        assert "Production runs" in line
        assert ARM_SPEC_BY_ID["bm25"].label in line
        assert ARM_SPEC_BY_ID["dense"].label in line
        assert "1.000 vs 0.909" in line

    def test_says_so_when_the_shipped_arm_also_leads(self):
        """The point of generating this line: it healed when the architecture was fixed.

        This is what the published verdict says today — the shipped arm is the leading
        arm, because the shipped arm was chosen by the measurement.
        """
        line = verdict_line(_document())
        assert "which also leads" in line
        assert " vs " not in line

    def test_reports_honestly_when_no_arm_is_flagged(self):
        doc = _document(results=[_raw("bm25", 1.0, 0.9)])
        for arm in doc["arms"]:
            arm["shipped"] = False
        assert "No arm is flagged as shipped" in verdict_line(doc)

    def test_leading_arm_is_per_metric(self):
        doc = _document(results=[_raw("bm25", 1.0, 0.5), _raw("rerank", 0.9, 0.99)])
        assert leading_arm(doc, "hit@5")["id"] == "bm25"
        assert leading_arm(doc, "mrr")["id"] == "rerank"

    def test_a_retired_arm_stays_publishable(self):
        """Arms come and go; #23 retired three from production in one change.

        Nothing downstream may assume a fixed set, so a document listing only the
        arms that ran must still render a verdict.
        """
        doc = _document(results=[_raw("bm25", 1.0, 0.9)])
        assert [a["id"] for a in doc["arms"]] == ["bm25"]
        assert "which also leads" in verdict_line(doc)


# ---------------------------------------------------------------------------
# Markdown block
# ---------------------------------------------------------------------------


class TestMarkdown:
    def test_renders_a_row_per_arm_with_the_winner_bolded(self):
        md = render_markdown(_document())
        assert "| `bm25` _(shipped)_ |" in md
        assert "| `rerank` |" in md
        assert "**1.000**" in md  # bm25 leads hit@5
        assert "Measured on 49 chunks and 55 golden questions" in md
        # Column labels match the page's, so the two surfaces read identically.
        assert "| MRR |" in md and "| mrr |" not in md

    def test_provenance_names_a_held_out_sample_as_held_out(self):
        """A number measured on 22 questions nothing was tuned against is a different
        claim from one measured on all 55, and the reader is told which it is."""
        md = render_markdown(_document(golden_questions=22, split="holdout"))
        assert "the 22 held-out golden questions" in md

    def test_replaces_only_the_marked_block(self, tmp_path):
        path = tmp_path / "evaluation.md"
        path.write_text(
            f"# Doc\n\nBefore.\n\n{BEGIN_MARKER}\nstale table\n{END_MARKER}\n\nAfter.\n"
        )

        assert update_markdown_block(path, _document()) is True
        text = path.read_text()
        assert "stale table" not in text
        assert text.startswith("# Doc\n\nBefore.\n")
        assert text.endswith("After.\n")
        assert "| `bm25` _(shipped)_ |" in text

    def test_is_idempotent(self, tmp_path):
        path = tmp_path / "evaluation.md"
        path.write_text(f"{BEGIN_MARKER}\n{END_MARKER}\n")
        doc = _document()
        update_markdown_block(path, doc)
        assert update_markdown_block(path, doc) is False

    def test_missing_markers_fail_loudly(self, tmp_path):
        """Appending a second table to a doc that already has one is worse than failing."""
        path = tmp_path / "evaluation.md"
        path.write_text("# Doc with no markers\n")
        with pytest.raises(ValueError, match="markers"):
            update_markdown_block(path, _document())
