"""Generation evaluation harness: what the chatbot answers, not only what it retrieves.

Separate from the retrieval harness (run_eval.py) because it is none of the things that
make that one trustworthy: it calls a paid or rate-limited model, its output varies, and
it is not free to rerun. See docs/adr/0007-generation-evaluation-harness.md.

The single entry point, `run_generation`, takes the cases, a retriever (an Arm) and a
generator, all injected. Each case records the exact chunks the generator was shown, so a
Judge can score the run later and another generator can replay identical contexts, leaving
the model as the only variable. Cases can be answered and judged several at once; the run
is the same whatever order they finish in.
"""

from __future__ import annotations

import argparse
import re
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol

from app.llm import MAX_TOKENS, TEMPERATURE, build_messages, format_context
from eval.publish import compare_with_shipped

if TYPE_CHECKING:
    from groq import Groq
    from openai import OpenAI

#: The usage fields recorded per answer. Groq's usage also carries timings, which are
#: not billed and vary from run to run. OpenAI counts reasoning tokens as completion tokens.
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


@dataclass(frozen=True)
class Relation:
    """How one retrieved chunk bears on one sentence of an answer.

    `label` is one of RELATIONS; `probabilities` is the Judge's distribution over them.
    """

    label: str
    probabilities: dict[str, float]


#: What a chunk can do to a sentence: state or imply it, state the opposite, or neither.
RELATIONS = ("supports", "contradicts", "says_nothing")


class Judge(Protocol):
    """Decides what an answer conveys and whether its context backs it (ADR-0007).

    One method per judgment, each asked of the smallest input that answers it: the
    Judge is weak on multi-claim input, long context and negation, so a sentence is
    split into claims, each claim is judged against one chunk at a time, and a Decline
    is asked about directly rather than inferred from a lack of support.
    """

    #: The exact Judge version that answered, recorded with every Measured Run.
    model: str
    #: The model that split sentences into claims, recorded with every Measured Run.
    splitter_model: str

    def is_factual(self, sentence: str) -> bool:
        """Whether the sentence states a fact about David or his work, rather than filler."""

    def claims(self, question: str, sentence: str) -> list[str]:
        """The sentence's claims, each standing alone; `question` resolves what it refers to."""

    def relation(self, claim: str, chunk: str) -> Relation:
        """Whether one chunk supports, contradicts, or says nothing about one claim."""

    def conveys(self, answer: str, fact: str) -> bool:
        """Whether the answer conveys a Required Fact, judged on meaning, not wording."""

    def declines(self, question: str, answer: str) -> bool:
        """Whether the answer says the information is unavailable rather than answering."""


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


def openai_generator(client: OpenAI, model: str, reasoning_effort: str) -> Generator:
    """A Generator answering with `model` on OpenAI, the provider being migrated to (ADR-0008).

    Messages come from the production builder, as for Groq. OpenAI's reasoning models
    reject any temperature but the default, so none is sent and answers vary from run to
    run; the reasoning effort is sent instead, because it changes the answer too.
    `max_completion_tokens` caps reasoning and answer tokens together.
    """

    def generate(question: str, chunks: list[str]) -> Generation:
        response = client.chat.completions.create(
            model=model,
            messages=build_messages(format_context(chunks), [], question),
            reasoning_effort=reasoning_effort,
            max_completion_tokens=MAX_TOKENS,
        )
        return Generation(
            text=response.choices[0].message.content or "",
            usage={field: getattr(response.usage, field) for field in USAGE_FIELDS},
            model=response.model,
        )

    return generate


def replay(record: dict) -> tuple[Retriever, Generator]:
    """A retriever and generator that return what a stored record already holds.

    Judging the Groq baseline this way calls no model but the Judge, and judges the exact
    chunks the model was shown, not what retrieval would return over today's Corpus.
    """
    lookup = _stored_cases(record)

    def generate(question: str, chunks: list[str]) -> Generation:
        case = lookup(question)
        return Generation(text=case["answer"], usage=case["usage"], model=case["model"])

    return stored_contexts(record), generate


def stored_contexts(record: dict) -> Retriever:
    """A retriever that returns the chunks a stored record's model was shown.

    Pairing it with a new generator answers the record's questions from identical
    contexts, so comparing the two runs compares the models alone (ADR-0008), whatever
    retrieval over today's Corpus would return.
    """
    lookup = _stored_cases(record)

    def retrieve(question: str) -> list[str]:
        return lookup(question)["chunks"]

    return retrieve


def _stored_cases(record: dict) -> Callable[[str], dict]:
    stored = {case["question"]: case for case in record["cases"]}

    def lookup(question: str) -> dict:
        if question not in stored:
            raise KeyError(f"The record holds no answer to {question!r}.")
        return stored[question]

    return lookup


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


#: How many cases the paid entry scripts answer and judge at once. Each case spends most
#: of its time waiting on OpenAI and Jev, so eight at once turns a ~17-minute gate run
#: into a few minutes, well inside both providers' rate limits. The Groq baseline is
#: always answered one case at a time: its pacing to the free tier assumes one caller.
DEFAULT_WORKERS = 8


def add_workers_argument(
    parser: argparse.ArgumentParser,
    default: int | None = DEFAULT_WORKERS,
    help: str = f"Cases answered and judged at once (default: {DEFAULT_WORKERS}).",
) -> None:
    """The `--workers` flag every entry script that calls `run_generation` takes."""
    parser.add_argument("--workers", type=positive_int, default=default, help=help)


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, not {number}")
    return number


def run_generation(
    cases: list[dict],
    retrieve: Retriever,
    generate: Generator,
    judge: Judge | None = None,
    on_case: Callable[[dict], None] | None = None,
    workers: int = 1,
) -> dict:
    """Retrieve and generate for every case, recording what each answer was written from.

    With a `judge`, each answer is also judged and the run carries its metrics and the
    Judge version. Without one, the run is a record to judge later.

    `on_case` receives each case's result as soon as it is recorded, so a run that stops
    partway (a spent token budget, a provider error) keeps the answers already paid for.

    `workers` cases are answered and judged at once; the default, one, answers them in
    turn. Workers only produce results: each is handed to `on_case` on the calling thread,
    in the order they finish, and the run lists them in case order. The first error starts
    no further case; the cases already under way are finished and handed over, and then
    the error is raised. `retrieve`, `generate` and `judge` must be safe to call from
    several threads at once when `workers` is above one.
    """
    if workers < 1:
        raise ValueError(f"workers must be at least 1, not {workers}")

    def answer(case: dict) -> dict:
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
        if judge is not None:
            result.update(judge_case(case, chunks, generation.text, judge))
        return result

    if workers > 1 and cases:
        # A model the retriever loads on first use is loaded here, once, rather than by
        # every worker at the same moment.
        retrieve(cases[0]["question"])

    results: list[dict | None] = [None] * len(cases)
    waiting = iter(enumerate(cases))
    running: dict[Future, int] = {}
    error: BaseException | None = None
    with ThreadPoolExecutor(max_workers=workers) as pool:

        def start_next() -> None:
            for index, case in waiting:
                running[pool.submit(answer, case)] = index
                return

        for _ in range(workers):
            start_next()
        while running:
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=running.__getitem__):
                index = running.pop(future)
                if future.exception() is not None:
                    error = error or future.exception()
                    continue
                results[index] = future.result()
                if on_case is not None:
                    on_case(future.result())
            if error is None:
                for _ in done:
                    start_next()
    if error is not None:
        raise error

    recorded = [result for result in results if result is not None]
    run = {"cases": recorded, "usage": total_usage(recorded)}
    if judge is not None:
        run["judge"] = judge.model
        run["splitter"] = judge.splitter_model
        run["metrics"] = score(recorded)
        run["contradictions"] = [
            {"case": r["id"], **contradiction}
            for r in recorded
            for contradiction in r["contradictions"]
        ]
    return run


def judge_case(case: dict, chunks: list[str], answer: str, judge: Judge) -> dict:
    """One answer's judgments: whether it declined, and otherwise what it states and conveys.

    A Decline, and any answer to an Out-of-Scope Case, is not judged further. The Judge
    is weak on negation, so "the information doesn't include that" would otherwise be
    counted as an unsupported claim. A Decline conveys none of its Required Facts, so a
    declined fair question lowers Fact Recall as well as Decline accuracy; an
    Out-of-Scope Case has no Required Facts to convey.
    """
    declined = judge.declines(case["question"], answer)
    facts = [{"fact": fact, "conveyed": False} for fact in case.get("required_facts", [])]
    judged = {"declined": declined, "sentences": [], "contradictions": [], "facts": facts}
    if declined or not case.get("answerable", True):
        return judged

    sentences = []
    contradictions = []
    for text in split_sentences(answer):
        claims = judge_sentence(case["question"], text, chunks, judge)
        if claims is None:
            continue
        sentences.append(
            {
                "text": text,
                "supported": all(claim.supported for claim in claims),
                "claims": [{"claim": c.claim, "supported": c.supported} for c in claims],
            }
        )
        contradictions += [
            {"sentence": text, "claim": claim.claim, "chunk": chunk}
            for claim in claims
            for chunk, relation in zip(chunks, claim.relations, strict=True)
            if relation.label == "contradicts"
        ]
    facts = [
        {"fact": fact, "conveyed": judge.conveys(answer, fact)}
        for fact in case.get("required_facts", [])
    ]
    return {**judged, "sentences": sentences, "contradictions": contradictions, "facts": facts}


#: How likely the Judge must find `supports` for a chunk to count as supporting a claim:
#: more likely than not, rather than merely the likeliest of three. Over three runs on the
#: tuned hand labels, 0.6 and 0.7 lost more supported sentences than they caught
#: unsupported ones (#81, docs/evaluation.md).
SUPPORTS_AT = 0.5


@dataclass(frozen=True)
class ClaimJudgment:
    """How each retrieved chunk bears on one claim of a sentence, in chunk order."""

    claim: str
    relations: list[Relation]

    @property
    def supported(self) -> bool:
        """Whether any one chunk supports the claim, with confidence."""
        return any(
            relation.probabilities.get("supports", 0.0) >= SUPPORTS_AT
            for relation in self.relations
        )


def judge_sentence(
    question: str, text: str, chunks: list[str], judge: Judge
) -> list[ClaimJudgment] | None:
    """How each chunk bears on each claim of one sentence, or None if it is filler.

    The sentence is supported only if every claim is; different chunks may support
    different claims (ADR-0007). A factual sentence split into no claims is judged whole,
    or it would pass with nothing checked.
    """
    if not judge.is_factual(text):
        return None
    return [
        ClaimJudgment(claim, [judge.relation(claim, chunk) for chunk in chunks])
        for claim in judge.claims(question, text) or [text]
    ]


LIST_ITEM = re.compile(r"^(?:[-*+•]|\d+[.)])\s+")
HEADING = re.compile(r"^#+\s*")
TABLE_SEPARATOR = re.compile(r"^\|[\s:|-]*-[\s:|-]*$")
# Emphasis and code markers, which are formatting rather than part of any claim.
MARKUP = re.compile(r"\*+|`")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# Abbreviations whose full stop ends no sentence.
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "approx.", "U.S.", "Dr.", "Mr.", "Ms.")


def split_sentences(answer: str) -> list[str]:
    """The answer's sentences, split by code rather than by a model (ADR-0007).

    Each is meant to be judged alone, so each should state its claim alone. A list item
    ("SQLite") carries the line introducing its list ("David has worked with the
    following databases"), and the introducing line is not judged on its own. A table
    row is one claim, its cells labelled with their column headings.
    """
    lines = [line.strip() for line in answer.splitlines()] + [""]
    sentences: list[str] = []
    lead: str | None = None  # the line introducing a list or table, without its colon
    lead_used = False
    headings: list[str] = []
    for line, next_line in pairwise(lines):
        if line.startswith("|"):
            if TABLE_SEPARATOR.match(line):
                continue
            cells = table_cells(line)
            if TABLE_SEPARATOR.match(next_line):
                headings = cells
                continue
            if headings:
                pieces = ["; ".join(f"{h}: {c}" for h, c in zip(headings, cells, strict=False))]
            else:
                pieces = [", ".join(cells)]
        elif item := LIST_ITEM.match(line):
            pieces = sentences_in(line[item.end() :])
        else:
            headings = []
            line = HEADING.sub("", MARKUP.sub("", line)).strip()
            if not line:
                continue
            if lead and not lead_used:
                sentences += sentences_in(lead + ":")
            lead, lead_used = (line[:-1], False) if line.endswith(":") else (None, False)
            if lead is None:
                sentences += sentences_in(line)
            continue
        if lead and pieces:
            pieces[0] = f"{lead}: {pieces[0]}"
            lead_used = True
        sentences += pieces
    if lead and not lead_used:
        sentences += sentences_in(lead + ":")
    return sentences


def table_cells(row: str) -> list[str]:
    """A Markdown table row's cells, with in-cell line breaks and bullets made a list."""
    cells = []
    for cell in MARKUP.sub("", row).strip().strip("|").split("|"):
        parts = [part.strip().lstrip("•").strip() for part in cell.split("<br>")]
        cells.append(", ".join(part for part in parts if part))
    return cells


def sentences_in(text: str) -> list[str]:
    """One line's sentences, with markup removed."""
    sentences: list[str] = []
    for piece in SENTENCE_END.split(MARKUP.sub("", text).strip()):
        if sentences and sentences[-1].endswith(ABBREVIATIONS):
            sentences[-1] += " " + piece
        elif piece:
            sentences.append(piece)
    return sentences


def score(results: list[dict]) -> dict:
    """A judged run's metrics, pooled over its cases.

    Decline accuracy is reported overall and in each direction: declining an Out-of-Scope
    Case and answering an answerable one are both correct, and a model can fail either way.
    """
    sentences = [s for r in results for s in r["sentences"]]
    supported = sum(s["supported"] for s in sentences)
    facts = [f for r in results for f in r["facts"]]
    conveyed = sum(f["conveyed"] for f in facts)
    answerable = [r for r in results if r["answerable"]]
    out_of_scope = [r for r in results if not r["answerable"]]
    answered = sum(not r["declined"] for r in answerable)
    declined = sum(r["declined"] for r in out_of_scope)
    return {
        "factRecall": ratio(conveyed, len(facts)),
        "faithfulness": ratio(supported, len(sentences)),
        "declineAccuracy": ratio(answered + declined, len(results)),
        "answeredAnswerable": ratio(answered, len(answerable)),
        "declinedOutOfScope": ratio(declined, len(out_of_scope)),
        "factualSentences": len(sentences),
        "contradictions": sum(len(r["contradictions"]) for r in results),
    }


# Paired outcomes. Each metric pairs one judged run with another per case, or per
# Required Fact, so two runs over the same cases can be compared by ADR-0006's test,
# whether they differ in the model (ADR-0008, eval/select_model.py) or the Arm
# (ADR-0009, eval/compare_arms.py).


def compare(candidate: dict, incumbent: dict) -> dict:
    """Per metric, the pairs the candidate won and lost against the incumbent, and the outcome.

    A pair only one of the two runs has an outcome for is left out.
    """
    return {
        metric: compare_with_shipped(
            outcomes(candidate, metric), outcomes(incumbent, metric), metric
        )
        for metric in OUTCOMES
    }


def outcomes(run: dict, metric: str) -> list[dict]:
    """Each pair's pass or fail on one metric, leaving out what the metric doesn't score."""
    return [
        {"id": pair, metric: passed}
        for case in run["cases"]
        for pair, passed in OUTCOMES[metric](case)
    ]


def faithful(case: dict) -> list[tuple[str, bool]]:
    """Whether every factual sentence of the answer is supported (ADR-0008 amendment).

    Faithfulness pools sentences, and two runs' answers have different sentences, so
    the cases are what can be paired. A Decline, or any answer to an Out-of-Scope Case,
    is not judged for support, so it has no outcome.
    """
    if case["declined"] or not case["answerable"]:
        return []
    return [(case["id"], all(sentence["supported"] for sentence in case["sentences"]))]


def decline_correct(case: dict) -> list[tuple[str, bool]]:
    """Declining an Out-of-Scope Case and answering an answerable one are both correct."""
    return [(case["id"], case["declined"] != case["answerable"])]


def conveyed(case: dict) -> list[tuple[str, bool]]:
    """Whether each Required Fact was conveyed: the same facts, so each fact is a pair."""
    return [(f"{case['id']}#{i}", fact["conveyed"]) for i, fact in enumerate(case["facts"])]


OUTCOMES = {"faithfulness": faithful, "declineAccuracy": decline_correct, "factRecall": conveyed}


#: The gated metrics' Floors, for the Shipped Arm over the full Golden Set (ADR-0007).
#: Derived by eval/variance.py from three Luna runs judged with the questions fixed in #81
#: (docs/evaluation.md, Run-to-run spread). Not targets: a Floor moves only when the
#: spread study is rerun, for a new generation model, Judge question or splitter.
FLOORS = {"faithfulness": 0.85, "declineAccuracy": 0.915}


def gate_failures(metrics: dict, floors: dict[str, float] = FLOORS) -> list[str]:
    """Each gated metric below its Floor, as a line to print; empty when the gate passes.

    A gated metric that measured nothing (no factual sentence, no case) fails: a run that
    checked nothing has not shown the answers are fine.
    """
    failures = []
    for metric, floor in floors.items():
        value = metrics.get(metric)
        if value is None:
            failures.append(f"{metric} was not measured")
        elif value < floor:
            failures.append(f"{metric} = {value:.3f} < {floor:.3f}")
    return failures


def ratio(part: int, whole: int) -> float | None:
    """`part / whole`, or None when there is nothing to measure."""
    return part / whole if whole else None


def format_report(run: dict) -> str:
    """A judged run for the terminal: its metrics, then every Contradiction in full.

    Contradictions are listed rather than counted because each is a false statement
    about David, to be read and reviewed.
    """
    metrics = run["metrics"]
    models = ", ".join(sorted({r["model"] for r in run["cases"]}))
    answerable = sum(r["answerable"] for r in run["cases"])
    lines = [
        (
            f"Judge: {run['judge']} | Generator: {models} | "
            f"{answerable} answerable + {len(run['cases']) - answerable} out-of-scope"
        ),
        "",
        f"  Fact Recall          {fmt(metrics['factRecall'])}",
        (
            f"  Faithfulness         {fmt(metrics['faithfulness'])}  "
            f"({metrics['factualSentences']} factual sentences)"
        ),
        (
            f"  Decline accuracy     {fmt(metrics['declineAccuracy'])}  "
            f"(answered answerable {fmt(metrics['answeredAnswerable'])}, "
            f"declined out-of-scope {fmt(metrics['declinedOutOfScope'])})"
        ),
        "",
        f"Contradictions ({len(run['contradictions'])}):",
    ]
    for contradiction in run["contradictions"]:
        lines.append(f"  {contradiction['case']}: {contradiction['sentence']}")
        if contradiction["claim"] != contradiction["sentence"]:
            lines.append(f"    claim: {contradiction['claim']}")
        lines.append(f"    contradicted by: {' '.join(contradiction['chunk'].split())}")
    return "\n".join(lines)


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def total_usage(results: list[dict]) -> dict[str, int]:
    """Billed usage summed over recorded cases, per usage field."""
    totals: dict[str, int] = {}
    for result in results:
        for field, tokens in result["usage"].items():
            totals[field] = totals.get(field, 0) + tokens
    return totals
