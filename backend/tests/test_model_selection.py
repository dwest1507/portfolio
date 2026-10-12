"""Tests for choosing the generation model by ADR-0008's rule, with ADR-0006's sign test.

Judged runs are given as literals, so no model or Judge is called: what these pin down is
which model the rule picks from a set of per-case judgments.
"""

from __future__ import annotations

import pytest

from eval.select_model import cost_per_answer, select_model


def judged(case_id, faithful=True, declined=False, answerable=True, conveyed=(True,)):
    """One judged case: its one factual sentence supported or not, and its facts conveyed."""
    return {
        "id": case_id,
        "split": "dev",
        "answerable": answerable,
        "declined": declined,
        "sentences": [] if declined or not answerable else [{"supported": faithful}],
        "facts": [
            {"fact": f"Fact {i}.", "conveyed": c and not declined}
            for i, c in enumerate(conveyed if answerable else ())
        ],
        "contradictions": [],
    }


def run(cases):
    return {"cases": cases}


def same(n=8):
    return run([judged(f"case-{i}") for i in range(n)])


def test_luna_replaces_groq_when_no_gated_metric_tells_them_apart():
    """The cheaper model wins unless the data can see it is worse."""
    decision = select_model(same(), same(), same())

    assert decision["chosen"] == "luna"


def test_groq_stays_when_luna_is_distinguishably_worse_on_decline_accuracy():
    """Six fair questions Luna declines and Groq answers, against none the other way."""
    luna = run([judged(f"case-{i}", declined=i < 6) for i in range(8)])

    decision = select_model(same(), luna, same())

    assert decision["chosen"] == "groq"
    assert decision["comparisons"]["luna-vs-groq"]["declineAccuracy"] == {
        "won": 0,
        "lost": 6,
        "outcome": "behind",
    }


def test_a_single_disagreement_is_not_enough_to_reject_luna():
    """One case either way is sampling noise, so the cheaper model still wins."""
    luna = run([judged(f"case-{i}", declined=i == 0) for i in range(8)])

    decision = select_model(same(), luna, same())

    assert decision["chosen"] == "luna"
    assert decision["comparisons"]["luna-vs-groq"]["declineAccuracy"]["outcome"] == (
        "indistinguishable"
    )


def test_groq_stays_when_luna_is_distinguishably_worse_on_faithfulness():
    """A case is faithful only when every factual sentence of its answer is supported."""
    luna = run([judged(f"case-{i}", faithful=i >= 6) for i in range(8)])

    decision = select_model(same(), luna, same())

    assert decision["chosen"] == "groq"
    assert decision["comparisons"]["luna-vs-groq"]["faithfulness"] == {
        "won": 0,
        "lost": 6,
        "outcome": "behind",
    }


def test_a_case_either_model_declined_is_left_out_of_faithfulness():
    """A Decline states nothing, so it can't be paired against an answer's sentences."""
    groq = run([judged(f"case-{i}", declined=i < 6) for i in range(8)])
    luna = run([judged(f"case-{i}", faithful=i >= 6) for i in range(8)])

    decision = select_model(groq, luna, same())

    assert decision["comparisons"]["luna-vs-groq"]["faithfulness"] == {
        "won": 0,
        "lost": 0,
        "outcome": "indistinguishable",
    }


def test_out_of_scope_cases_are_left_out_of_faithfulness():
    """An answer to an Out-of-Scope Case is scored only on whether it declined."""
    groq = run([judged(f"oos-{i}", answerable=False, declined=True) for i in range(6)])
    luna = run([judged(f"oos-{i}", answerable=False, declined=False) for i in range(6)])

    comparison = select_model(groq, luna, same())["comparisons"]["luna-vs-groq"]

    assert comparison["faithfulness"]["won"] + comparison["faithfulness"]["lost"] == 0
    assert comparison["declineAccuracy"]["outcome"] == "behind"


def test_sol_replaces_luna_when_distinguishably_better_on_faithfulness():
    """Sol costs ~20× as much, so it wins only on a difference the data can see."""
    unfaithful = run([judged(f"case-{i}", faithful=i >= 6) for i in range(8)])

    decision = select_model(unfaithful, unfaithful, same())

    assert decision["chosen"] == "sol"
    assert decision["comparisons"]["sol-vs-luna"]["faithfulness"]["outcome"] == "ahead"


def test_sol_is_not_chosen_for_better_fact_recall_alone():
    """Fact Recall breaks ties and never justifies an upgrade on its own."""
    forgetful = run([judged(f"case-{i}", conveyed=(i >= 6,)) for i in range(8)])

    decision = select_model(forgetful, forgetful, same())

    assert decision["chosen"] == "luna"
    assert decision["comparisons"]["sol-vs-luna"]["factRecall"]["outcome"] == "ahead"


def test_fact_recall_breaks_a_tie_between_sol_better_on_one_gated_metric_and_worse_on_the_other():
    """Ahead on Faithfulness and behind on Decline accuracy is no reason to pay more,
    unless Sol also conveys distinguishably more of the Required Facts."""

    def sol_conveying(conveyed):
        return run(
            [judged(f"a-{i}", conveyed=conveyed) for i in range(6)]
            + [judged(f"b-{i}", declined=True) for i in range(6)]
        )

    luna = run(
        [judged(f"a-{i}", faithful=False, conveyed=(False,) * 3) for i in range(6)]
        + [judged(f"b-{i}") for i in range(6)]
    )

    assert select_model(luna, luna, sol_conveying((False,) * 3))["chosen"] == "luna"
    assert select_model(luna, luna, sol_conveying((True,) * 3))["chosen"] == "sol"


def billed(model, *usages):
    return {
        "record": {"requestedModel": model},
        "cases": [
            {"usage": {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}}
            for p, c in usages
        ],
    }


def test_cost_per_answer_is_billed_usage_at_the_models_prices():
    """gpt-6-luna bills $0.10 per 1M input tokens and $0.50 per 1M output tokens."""
    luna = billed("gpt-6-luna", (1000, 200), (3000, 600))

    # (4,000 × 0.10 + 800 × 0.50) / 1M, over two answers
    assert cost_per_answer(luna) == pytest.approx(0.0004)


def test_groqs_free_tier_answers_cost_nothing():
    """The baseline ran on a free tier with no paid price to compare against."""
    assert cost_per_answer(billed("openai/gpt-oss-120b", (1000, 200))) == 0
