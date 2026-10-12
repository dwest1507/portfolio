"""The Judge for the generation harness: TypeSafe's Jev, pinned to an exact version.

Jev returns typed judgments with probabilities rather than text, its quota is separate
from the generation provider's, and it is from a different model family than the
generator, which avoids self-preference bias (ADR-0007).

Each judgment is one question about the smallest state that answers it. Jev is weak on
multi-claim input, long context and negation, which is why the harness asks it about one
claim and one chunk at a time, and asks about a Decline directly. Jev returns judgments,
not text, so splitting a sentence into claims is done by another model (eval/splitter.py).

The filler and support questions were revised in #81, after validation against hand
labels found Jev dropping factual sentences as filler and passing partly supported ones
(docs/evaluation.md). Changing any question is a new measurement.
"""

from __future__ import annotations

import random as _random
import threading
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx

from eval.generation import Relation

JEV_URL = "https://api.typesafe.ai/v1/systemone"

#: Never `jev-latest`: a Judge that changes silently makes Measured Runs incomparable,
#: just as a changed Corpus does. Moving the pin is a new measurement.
JEV_MODEL = "jev-1.13.0"

# Rate-limited (429) and overloaded (529) requests are retried with exponential backoff,
# as TypeSafe's own SDKs do. TypeSafe publishes no numeric limits, so the backoff is
# what keeps eight concurrent workers within them.
RETRY_STATUSES = (429, 529)
MAX_ATTEMPTS = 6

# Strict: a chunk supports a claim only if it backs every part of it, since the splitter
# can leave a list whole. `contradicts` is kept to incompatible statements about the same
# thing: Jev took a chunk naming another item of the same kind as a contradiction.
SUPPORT_QUESTION = {
    "type": "choice",
    "instructions": (
        "How does `section`, an excerpt from David West's portfolio, bear on `claim`, a "
        "sentence from a chatbot's answer about David? The claim may make several "
        "statements, for example in a list or joined by 'and'. Check each one."
    ),
    "criteria": {
        "supports": {
            "what": "The section states or clearly implies every statement in the claim.",
            "not_for": (
                "A section that backs some statements but not all of them, or only the "
                "general topic: that is says_nothing."
            ),
        },
        "contradicts": {
            "what": (
                "The section states something incompatible with a statement in the claim, "
                "about the same thing: a different number, date, level or outcome for it."
            ),
            "not_for": (
                "A section that names a different item of the same kind, such as another "
                "certificate, tool or model: that is says_nothing."
            ),
        },
        "says_nothing": (
            "Neither: at least one statement in the claim is not in the section, and none "
            "is contradicted."
        ),
    },
}

# Widened from "a fact about David": sentences about his projects and systems that do not
# name him were dropped as filler, and so never checked against a chunk.
FACTUAL_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does `sentence`, from a chatbot's answer about David West, make a statement that "
        "could be checked against his portfolio? That includes any statement about David, "
        "or about a project, system, tool, employer or result of his, even when the "
        "sentence does not name him."
    ),
    "criteria": {
        "true": (
            "It asserts something that could be true or false: what a project does, how a "
            "system is built, a number, a tool, a date, a role, a result."
        ),
        "false": (
            "It asserts nothing that could be checked: a greeting, an offer to help, a bare "
            "heading, a transition, a yes or no on its own, or a remark about the provided "
            "context or the chatbot itself."
        ),
    },
}

#: A sentence is dropped as filler only when Jev is this unlikely to call it factual. A
#: factual sentence dropped is never checked, which flatters Faithfulness; filler kept is
#: judged unsupported, which only counts against it. On the hand labels, filler scored at
#: most 0.08 and factual sentences at least 0.73.
FACTUAL_BELOW = 0.2

CONVEYS_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does `answer` convey `fact`? Judge the meaning, not the wording: a paraphrase "
        "or an equivalent statement conveys it."
    ),
    "criteria": {
        "true": "A reader of the answer would learn the fact.",
        "false": "The answer leaves the fact out, or says something different.",
    },
}

DECLINES_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does `answer` decline `question`, saying the information is not available, "
        "instead of answering it?"
    ),
    "criteria": {
        "true": "The answer says it does not have the information asked for, and gives none.",
        "false": "The answer answers the question, in full or in part.",
    },
}


class JudgeVersionChanged(RuntimeError):
    """Jev answered with a version other than the pinned one."""


class Splitter(Protocol):
    """Splits a sentence into standalone claims, such as `eval.splitter.OpenAISplitter`."""

    #: The model that split, recorded with every Measured Run.
    model: str

    def __call__(self, question: str, sentence: str) -> list[str]: ...


class JevJudge:
    """A Judge asking TypeSafe's Jev, pinned to `JEV_MODEL`, with claims from `splitter`.

    Every answer is checked against the pin, so `model` is the version that actually
    judged the run, not only the one requested. `usage` totals Jev's billed tokens; the
    splitter totals its own. `retries` counts requests repeated after a 429 or 529, and
    `reported_usage` gives both together, as a run reports them. Safe to call from several
    threads at once: both totals are updated under a lock, so no billed token or retry is
    lost to a race.

    `sleep`, `random` and `clock` are injectable so the backoff can be tested without
    waiting, as the Groq pacer's are (`eval.generation.throttled`).
    """

    def __init__(
        self,
        api_key: str,
        splitter: Splitter,
        client: httpx.Client | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
        random: Callable[[], float] = _random.random,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.model = JEV_MODEL
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.retries = 0
        self.splitter = splitter
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=60)
        self._usage_lock = threading.Lock()
        self._sleep = sleep
        self._random = random
        self._clock = clock

    @property
    def reported_usage(self) -> dict[str, int]:
        """Billed tokens and the retry count, as a run reports the Judge's usage."""
        with self._usage_lock:
            return {**self.usage, "retries": self.retries}

    @property
    def splitter_model(self) -> str:
        return self.splitter.model

    def is_factual(self, sentence: str) -> bool:
        return self._ask({"sentence": sentence}, FACTUAL_QUESTION)["noul"] >= FACTUAL_BELOW

    def claims(self, question: str, sentence: str) -> list[str]:
        return self.splitter(question, sentence)

    def relation(self, claim: str, chunk: str) -> Relation:
        answer = self._ask({"claim": claim, "section": chunk}, SUPPORT_QUESTION)
        return Relation(answer["choice"], answer["probabilities"])

    def conveys(self, answer: str, fact: str) -> bool:
        return self._yes({"answer": answer, "fact": fact}, CONVEYS_QUESTION)

    def declines(self, question: str, answer: str) -> bool:
        return self._yes({"question": question, "answer": answer}, DECLINES_QUESTION)

    def _yes(self, state: dict, question: dict) -> bool:
        return self._ask(state, question)["noul"] >= 0.5

    def _backoff(self, attempt: int, response: httpx.Response) -> float:
        """Seconds to wait before retry `attempt + 1`.

        The base is 2**attempt, or the response's `Retry-After` when that is longer, and
        up to as much again is added at random. The random part spreads the retries of
        workers that were limited together, which would otherwise all retry at the same
        moment and be limited together again.
        """
        base = max(2**attempt, self._retry_after(response))
        return base * (1 + self._random())

    def _retry_after(self, response: httpx.Response) -> float:
        """The wait `Retry-After` asks for, in seconds or as a date; 0 if none is given."""
        value = response.headers.get("Retry-After")
        if value is None:
            return 0.0
        try:
            return max(0.0, float(value))
        except ValueError:
            pass
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - self._clock())
        except TypeError, ValueError:
            return 0.0

    def _ask(self, state: dict, question: dict) -> dict:
        body = {"model": self.model, "state": state, "questions": {"judgment": question}}
        for attempt in range(MAX_ATTEMPTS):
            response = self._client.post(JEV_URL, json=body, headers=self._headers)
            if response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS - 1:
                break
            with self._usage_lock:
                self.retries += 1
            self._sleep(self._backoff(attempt, response))
        response.raise_for_status()
        data = response.json()
        if data["model"] != self.model:
            raise JudgeVersionChanged(
                f"Asked for {self.model}, answered by {data['model']}. Judgments from two "
                "versions are not one measurement."
            )
        with self._usage_lock:
            for field in self.usage:
                self.usage[field] += data["usage"][field]
        return data["answers"]["judgment"]
