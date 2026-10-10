"""Generation evaluation harness: what the chatbot answers, not only what it retrieves.

Separate from the retrieval harness (run_eval.py) because it is none of the things that
make that one trustworthy: it calls a paid or rate-limited model, its output varies, and
it is not free to rerun. See docs/adr/0007-generation-evaluation-harness.md.

The single entry point, `run_generation`, takes the cases, a retriever (an Arm) and a
generator, all injected. Each case records the exact chunks the generator was shown, so a
Judge can score the run later and another generator can replay identical contexts, leaving
the model as the only variable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.llm import MAX_TOKENS, TEMPERATURE, build_messages, format_context

if TYPE_CHECKING:
    from groq import Groq

#: The usage fields recorded per answer. Groq's usage also carries timings, which are
#: not billed and vary from run to run.
USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")


@dataclass(frozen=True)
class Generation:
    """One generated answer, with the usage it was billed for and the model that wrote it.

    `model` is the ID the provider reports answering with, not the one requested: a
    provider that silently serves a different revision is a different measurement.
    """

    text: str
    usage: dict[str, int]
    model: str


#: Given a question, the chunk texts retrieval returns for it, best first.
Retriever = Callable[[str], list[str]]

#: Given a question and its retrieved chunk texts, the answer.
Generator = Callable[[str, list[str]], Generation]


def groq_generator(client: Groq, model: str) -> Generator:
    """A Generator answering with `model` on Groq, the provider being migrated away from.

    It has no prompt of its own: messages come from the production builder and sampling
    settings from production's constants, so the baseline measures what visitors were
    served. It does not stream; the answer is the same, and a whole response carries
    the billed usage.
    """

    def generate(question: str, chunks: list[str]) -> Generation:
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(format_context(chunks), [], question),
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return Generation(
            text=response.choices[0].message.content or "",
            usage={field: getattr(response.usage, field) for field in USAGE_FIELDS},
            model=response.model,
        )

    return generate


class TokenBudgetExhausted(RuntimeError):
    """The next call would take the run past its token budget."""


def throttled(
    generate: Generator,
    tokens_per_minute: int,
    token_budget: int | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Generator:
    """`generate`, paced so billed tokens never exceed `tokens_per_minute`.

    Each call earns the next one a wait proportional to the tokens it billed, measured
    from when it started. Pacing by what was actually billed, rather than estimating
    ahead, means a short answer does not hold up the next question for a long one.

    With a `token_budget`, a call that could take total spend past it is refused with
    TokenBudgetExhausted rather than made. A call's cost is only known afterwards, so
    the next one is assumed to cost as much as the largest so far.
    """
    next_start = 0.0
    spent = 0
    largest = 0

    def generate_paced(question: str, chunks: list[str]) -> Generation:
        nonlocal next_start, spent, largest
        if token_budget is not None and spent + largest > token_budget:
            raise TokenBudgetExhausted(
                f"{spent:,} tokens spent; another call of up to {largest:,} would pass the "
                f"budget of {token_budget:,}."
            )
        wait = next_start - clock()
        if wait > 0:
            sleep(wait)
        started = clock()
        generation = generate(question, chunks)
        tokens = generation.usage["total_tokens"]
        spent += tokens
        largest = max(largest, tokens)
        next_start = started + tokens * 60 / tokens_per_minute
        return generation

    return generate_paced


def run_generation(
    cases: list[dict],
    retrieve: Retriever,
    generate: Generator,
    on_case: Callable[[dict], None] | None = None,
) -> dict:
    """Retrieve and generate for every case, recording what each answer was written from.

    `on_case` receives each case's result as soon as it is recorded, so a run that stops
    partway (a spent token budget, a provider error) keeps the answers already paid for.
    """
    results = []
    for case in cases:
        chunks = retrieve(case["question"])
        generation = generate(case["question"], chunks)
        result = {
            "id": case["id"],
            "split": case["split"],
            "answerable": case.get("answerable", True),
            "question": case["question"],
            "chunks": chunks,
            "answer": generation.text,
            "usage": generation.usage,
            "model": generation.model,
        }
        results.append(result)
        if on_case is not None:
            on_case(result)
    return {"cases": results, "usage": total_usage(results)}


def total_usage(results: list[dict]) -> dict[str, int]:
    """Billed usage summed over recorded cases, per usage field."""
    totals: dict[str, int] = {}
    for result in results:
        for field, tokens in result["usage"].items():
            totals[field] = totals.get(field, 0) + tokens
    return totals
