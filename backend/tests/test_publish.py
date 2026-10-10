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
    leading_arm_ids,
    render_markdown,
    shipped_arm_id,
    update_markdown_block,
    verdict_line,
    write_results_document,
)


def _raw(arm: str, hit: float, mrr: float, by_category: dict | None = None) -> dict:
    summary = {"recall@5": 0.5, "hit@5": hit, "mrr": mrr, "ndcg@5": 0.6}
    return {
        "arm": arm,
        "top_k": 5,
        "summary": summary,
        "by_category": by_category if by_category is not None else {"direct": dict(summary)},
        "cases": [],
    }


def _scored(arm: str, hits: list[int], mrrs: list[float] | None = None) -> dict:
    """An arm's raw output built from made-up per-case outcomes on the gating metric.

    Case `q{i}` is hit by this arm when `hits[i]` is 1. Arms are compared question by
    question, so two arms built from the same-length lists answer the same questions.
    """
    mrrs = mrrs if mrrs is not None else [float(h) for h in hits]
    cases = [
        {"id": f"q{i}", "category": "direct", "hit@5": float(h), "mrr": m}
        for i, (h, m) in enumerate(zip(hits, mrrs, strict=True))
    ]
    hit = sum(hits) / len(hits)
    mrr = sum(mrrs) / len(mrrs)
    raw = _raw(arm, hit, mrr)
    raw["cases"] = cases
    return raw


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
    def test_schema_version_is_4(self):
        """Bumped when the document began carrying per-question comparisons (ADR-0006)."""
        assert SCHEMA_VERSION == 4

    def test_carries_provenance_and_arm_metadata(self):
        doc = _document()
        assert doc["schemaVersion"] == 4
        assert doc["corpusChunks"] == 49
        assert doc["goldenQuestions"] == 55
        assert doc["gatingMetric"] == "hit@5"
        assert doc["split"] == "all"
        assert doc["categories"] == ["direct"]
        assert doc["metricNames"] == ["recall@5", "hit@5", "mrr", "ndcg@5"]

        bm25 = next(a for a in doc["arms"] if a["id"] == "bm25")
        assert bm25["label"] == ARM_SPEC_BY_ID["bm25"].label
        assert bm25["metrics"]["hit@5"] == 1.0
        assert bm25["byCategory"]["direct"]["hit@5"] == 1.0
        assert bm25["shipped"] is True

        rerank = next(a for a in doc["arms"] if a["id"] == "rerank")
        assert rerank["shipped"] is False
        assert rerank["byCategory"]["direct"]["hit@5"] == 0.909

    def test_carries_per_category_metrics_for_each_arm(self):
        bm25_cat = {
            "direct": {"recall@5": 0.8, "hit@5": 1.0, "mrr": 0.9, "ndcg@5": 0.85},
            "paraphrase": {"recall@5": 0.4, "hit@5": 0.6, "mrr": 0.5, "ndcg@5": 0.45},
        }
        doc = _document(results=[_raw("bm25", 0.9, 0.7, by_category=bm25_cat)])
        assert doc["schemaVersion"] == 4
        assert doc["categories"] == ["direct", "paraphrase"]
        bm25 = next(a for a in doc["arms"] if a["id"] == "bm25")
        assert bm25["byCategory"]["direct"]["hit@5"] == 1.0
        assert bm25["byCategory"]["paraphrase"]["hit@5"] == 0.6

    def test_carries_category_counts(self):
        cases = [
            {"id": "c1", "category": "direct", "hit@5": 1.0, "mrr": 1.0},
            {"id": "c2", "category": "direct", "hit@5": 1.0, "mrr": 0.5},
            {"id": "c3", "category": "paraphrase", "hit@5": 1.0, "mrr": 1.0},
        ]
        results = [_raw("bm25", 1.0, 0.9)]
        results[0]["cases"] = cases
        doc = _document(results=results)
        assert doc["categoryCounts"] == {"direct": 2, "paraphrase": 1}

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
        """The published file is read by humans; \\u2192 in it is noise.

        Anchored to whichever arm actually uses an arrow rather than to `rerank` by name,
        so rewording one description cannot quietly turn this into a test of nothing.
        """
        arm = next((a for a in ARM_SPECS if "\u2192" in a.technical), None)
        assert arm is not None, "no arm description contains an arrow for this to check"

        path = tmp_path / "evalResults.json"
        write_results_document(
            _document(results=[_raw(arm.id, 0.9, 0.85)]),
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

    def test_a_ci_run_replaces_a_local_one_even_when_nothing_moved(self, tmp_path):
        """Otherwise a developer's local --publish freezes its own provenance forever.

        A local run records a bare commit and no run link. If the next CI run measures
        the same numbers, the unconditional skip would leave that unattested provenance
        on the public page indefinitely — "measured at <sha>" with nothing to check it
        against. A run carrying a runUrl is allowed to take over.
        """
        path = tmp_path / "evalResults.json"
        local = _document()
        local["runUrl"] = None
        write_results_document(local, path)

        from_ci = _document()
        from_ci["runUrl"] = "https://example.test/run/7"
        from_ci["commit"] = "ci12345"
        document, written = write_results_document(from_ci, path)

        assert written is True
        assert document["runUrl"] == "https://example.test/run/7"
        assert json.loads(path.read_text(encoding="utf-8"))["commit"] == "ci12345"

    def test_the_takeover_happens_only_once(self, tmp_path):
        """The replacement carries a runUrl of its own, so the next identical CI run
        takes the ordinary "nothing to commit" branch. Otherwise every push to main
        would commit a re-measurement that found nothing — the bug MEASURED_KEYS exists
        to prevent."""
        path = tmp_path / "evalResults.json"
        local = _document()
        local["runUrl"] = None
        write_results_document(local, path)

        first = _document()
        first["runUrl"] = "https://example.test/run/7"
        write_results_document(first, path)

        second = _document()
        second["runUrl"] = "https://example.test/run/8"
        _, written = write_results_document(second, path)

        assert written is False

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

    def test_a_changed_disagreement_counts_as_a_new_measurement(self, tmp_path):
        """Two runs can share every average and still disagree with the shipped arm on
        different questions; the won/lost column is part of what was measured."""
        path = tmp_path / "evalResults.json"
        shipped = [1, 0, 1, 0]
        write_results_document(
            _document(results=[_scored("bm25", shipped), _scored("dense", [1, 0, 1, 0])]), path
        )

        swapped = _document(results=[_scored("bm25", shipped), _scored("dense", [0, 1, 0, 1])])
        document, written = write_results_document(swapped, path)

        assert written is True
        assert _arm(document, "dense")["vsShipped"]["won"] == 2

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
# Comparison against the shipped arm
# ---------------------------------------------------------------------------


def _arm(doc: dict, arm_id: str) -> dict:
    return next(a for a in doc["arms"] if a["id"] == arm_id)


class TestComparisonAgainstShipped:
    def test_a_lopsided_disagreement_puts_the_arm_ahead(self):
        """Eight questions only `dense` hit, none only `bm25` hit: p ≈ 0.008."""
        shipped = [0] * 8 + [1] * 25
        doc = _document(results=[_scored("bm25", shipped), _scored("dense", [1] * 33)])

        assert _arm(doc, "dense")["vsShipped"] == {"won": 8, "lost": 0, "outcome": "ahead"}

    def test_a_lopsided_disagreement_the_other_way_puts_the_arm_behind(self):
        """`dense` misses nine questions the shipped arm hits and wins one: p ≈ 0.021."""
        shipped = [1] * 9 + [0] + [1] * 23
        dense = [0] * 9 + [1] + [1] * 23
        doc = _document(results=[_scored("bm25", shipped), _scored("dense", dense)])

        assert _arm(doc, "dense")["vsShipped"] == {"won": 1, "lost": 9, "outcome": "behind"}

    def test_a_balanced_disagreement_is_indistinguishable(self):
        """The case the old verdict got wrong: 4 won, 2 lost is a 0.06 lead on hit@5 out of
        33 questions — and p ≈ 0.69, well inside sampling noise."""
        shipped = [1, 1, 0, 0, 0, 0] + [1] * 27
        dense = [0, 0, 1, 1, 1, 1] + [1] * 27
        doc = _document(results=[_scored("bm25", shipped), _scored("dense", dense)])

        assert _arm(doc, "dense")["vsShipped"] == {
            "won": 4,
            "lost": 2,
            "outcome": "indistinguishable",
        }

    def test_the_smallest_significant_split_is_six_to_nothing(self):
        """Five discordant questions can never be significant (p = 0.0625 at 5–0), which is
        why a 33-question sample rarely calls anything."""
        five = _document(results=[_scored("bm25", [0] * 5 + [1]), _scored("dense", [1] * 6)])
        six = _document(results=[_scored("bm25", [0] * 6), _scored("dense", [1] * 6)])

        assert _arm(five, "dense")["vsShipped"]["outcome"] == "indistinguishable"
        assert _arm(six, "dense")["vsShipped"]["outcome"] == "ahead"

    def test_each_category_is_compared_on_its_own_questions(self):
        """The page filters by Query Category, and its verdict follows the filter. A
        category's verdict must rest on that category's disagreements alone."""
        shipped = _scored("bm25", [0] * 6 + [1] * 4)
        dense = _scored("dense", [1] * 6 + [0] * 1 + [1] * 3)
        for raw in (shipped, dense):
            for case in raw["cases"][6:]:
                case["category"] = "paraphrase"
        doc = _document(results=[shipped, dense])

        assert _arm(doc, "dense")["vsShippedByCategory"] == {
            "direct": {"won": 6, "lost": 0, "outcome": "ahead"},
            "paraphrase": {"won": 0, "lost": 1, "outcome": "indistinguishable"},
        }
        assert _arm(doc, "bm25")["vsShippedByCategory"] is None

    def test_the_shipped_arm_is_not_compared_with_itself(self):
        doc = _document(results=[_scored("bm25", [1, 0]), _scored("dense", [1, 1])])
        assert _arm(doc, "bm25")["vsShipped"] is None


# ---------------------------------------------------------------------------
# Derived claims
# ---------------------------------------------------------------------------


class TestVerdict:
    """The Verdict Line names an arm only when the sign test can tell it apart (ADR-0006)."""

    def test_says_no_arm_is_distinguishable_and_names_the_sample(self):
        """The intended outcome on a 33-question sample, not a defect: dense leads by two
        questions on hit@5 and the old verdict would have called that a lead."""
        shipped = [1, 1, 0, 0, 0, 0] + [1] * 27
        dense = [0, 0, 1, 1, 1, 1] + [1] * 27
        doc = _document(
            results=[_scored("bm25", shipped), _scored("dense", dense)],
            golden_questions=33,
            split="holdout",
        )
        assert verdict_line(doc) == (
            "Production runs Keyword only. Across the 33 held-out questions, no other arm "
            "is distinguishable from it on hit@5."
        )

    def test_names_an_arm_that_is_distinguishably_ahead(self):
        shipped = [0] * 8 + [1] * 25
        doc = _document(
            results=[_scored("bm25", shipped), _scored("dense", [1] * 33)],
            golden_questions=33,
            split="holdout",
        )
        assert verdict_line(doc) == (
            "Production runs Keyword only. Across the 33 held-out questions, Meaning only "
            "(won 8, lost 0) is distinguishably ahead of it on hit@5."
        )

    def test_names_an_arm_that_is_distinguishably_behind(self):
        shipped = [1] * 9 + [0] + [1] * 23
        dense = [0] * 9 + [1] + [1] * 23
        doc = _document(
            results=[_scored("bm25", shipped), _scored("dense", dense)],
            golden_questions=33,
            split="holdout",
        )
        assert verdict_line(doc) == (
            "Production runs Keyword only. Across the 33 held-out questions, Meaning only "
            "(won 1, lost 9) is distinguishably behind it on hit@5."
        )

    def test_names_arms_ahead_and_behind_and_leaves_out_the_indistinguishable(self):
        """Labels contain commas ("Both combined, then re-ranked"), so each name is closed
        by its won/lost counts rather than left to run into the next one."""
        shipped = [1] * 7 + [0] * 7 + [1] * 19
        rerank = [1] * 7 + [1] * 7 + [1] * 19  # wins the 7 the shipped arm missed
        dense = [0] * 7 + [0] * 7 + [1] * 19  # loses the 7 the shipped arm hit
        hybrid = [0, 0, 1, 1] + [1] * 3 + [0] * 7 + [1] * 19  # 2 won, 2 lost
        doc = _document(
            results=[
                _scored("bm25", shipped),
                _scored("dense", dense),
                _scored("hybrid", hybrid),
                _scored("rerank", rerank),
                _scored("bm25+rerank", rerank),
            ],
            golden_questions=33,
            split="holdout",
        )
        assert verdict_line(doc) == (
            "Production runs Keyword only. Across the 33 held-out questions, "
            "Both combined, then re-ranked (won 7, lost 0) and Keyword, then re-ranked "
            "(won 7, lost 0) are distinguishably ahead of it on hit@5, and Meaning only "
            "(won 0, lost 7) is behind it."
        )

    def test_names_the_sample_for_a_run_over_the_whole_set(self):
        doc = _document(results=[_scored("bm25", [1, 0]), _scored("dense", [0, 1])])
        assert "Across all 55 questions," in verdict_line(doc)

    def test_leading_arm_ids_returns_every_tied_arm(self):
        doc = _document(results=[_raw("bm25", 1.0, 0.5), _raw("rerank", 1.0, 0.99)])
        assert leading_arm_ids(doc, "hit@5") == ["bm25", "rerank"]
        assert leading_arm_ids(doc, "mrr") == ["rerank"]

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
        assert verdict_line(doc) == "Production runs Keyword only. No other arm was measured."


# ---------------------------------------------------------------------------
# Markdown block
# ---------------------------------------------------------------------------


class TestMarkdown:
    def test_bolds_every_arm_tied_for_a_column(self):
        """The caption says "Best score per column in bold", so it has to be every arm
        holding the best score, not the first one listed."""
        md = render_markdown(_document(results=[_raw("bm25", 1.0, 0.9), _raw("rerank", 1.0, 0.8)]))
        assert md.count("**1.000**") == 2

    def test_renders_a_row_per_arm_with_the_winner_bolded(self):
        md = render_markdown(_document())
        assert "| `bm25` _(shipped)_ |" in md
        assert "| `rerank` |" in md
        assert "**1.000**" in md  # bm25 leads hit@5
        assert "Measured on 49 chunks and 55 golden questions" in md
        # Column labels match the page's, so the two surfaces read identically.
        assert "| MRR |" in md and "| mrr |" not in md

    def test_renders_won_and_lost_against_the_shipped_arm(self):
        shipped = [0] * 8 + [1] * 25
        dense = [1] * 8 + [0] * 2 + [1] * 23
        md = render_markdown(_document(results=[_scored("bm25", shipped), _scored("dense", dense)]))
        header = next(line for line in md.splitlines() if line.startswith("| Arm |"))
        assert header.endswith("| vs shipped (won / lost) |")
        assert next(line for line in md.splitlines() if "`dense`" in line).endswith("| 8 / 2 |")
        # The shipped arm is the reference, not a contestant against itself.
        assert next(line for line in md.splitlines() if "`bm25`" in line).endswith("| — |")

    def test_renders_a_bootstrap_interval_for_mrr(self):
        """An engineer judging a 0.03 MRR gap needs to see how wide MRR's own noise is."""
        flat = _scored("bm25", [1] * 20, mrrs=[0.5] * 20)
        spread = _scored("dense", [1] * 20, mrrs=[0.0, 1.0] * 10)
        md = render_markdown(_document(results=[flat, spread]))

        header = next(line for line in md.splitlines() if line.startswith("| Arm |"))
        assert "| MRR 95% CI |" in header
        # No variation between questions means no uncertainty to report.
        assert "| 0.500–0.500 |" in next(line for line in md.splitlines() if "`bm25`" in line)

        dense_row = next(line for line in md.splitlines() if "`dense`" in line)
        lo, hi = (float(x) for x in dense_row.split("|")[-3].strip().split("–"))
        assert 0.0 < lo < 0.5 < hi < 1.0

    def test_the_mrr_interval_is_reproducible(self):
        """Resampling is seeded: a re-run over the same outcomes must not rewrite the doc."""
        results = [_scored("bm25", [1] * 20, mrrs=[0.0, 1.0, 0.5, 0.25] * 5)]
        assert render_markdown(_document(results=results)) == render_markdown(
            _document(results=results)
        )

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
