"""The Judge for the generation harness: TypeSafe's Jev, pinned to an exact version.

Jev returns typed judgments with probabilities rather than text, its quota is separate
from the generation provider's, and it is from a different model family than the
generator, which avoids self-preference bias (ADR-0007).

Each judgment is one question about the smallest state that answers it. Jev is weak on
multi-claim input, long context and negation, which is why the harness asks it about one
sentence and one chunk at a time, and asks about a Decline directly.
"""

from __future__ import annotations

import time

import httpx

from eval.generation import Relation

JEV_URL = "https://api.typesafe.ai/v1/systemone"

#: Never `jev-latest`: a Judge that changes silently makes Measured Runs incomparable,
#: just as a changed Corpus does. Moving the pin is a new measurement.
JEV_MODEL = "jev-1.13.0"

# Rate-limited (429) and overloaded (529) requests are retried with exponential backoff,
# as TypeSafe's own SDKs do.
RETRY_STATUSES = (429, 529)
MAX_ATTEMPTS = 6

SUPPORT_QUESTION = {
    "type": "choice",
    "instructions": (
        "How does `section`, an excerpt from David West's portfolio, bear on `claim`, a "
        "sentence from a chatbot's answer about David?"
    ),
    "criteria": {
        "supports": "The section states the claim, or clearly implies that it is true.",
        "contradicts": "The section states the opposite, or clearly implies the claim is false.",
        "says_nothing": "The section does not address the claim either way.",
    },
}

FACTUAL_QUESTION = {
    "type": "noul",
    "instructions": (
        "Does `sentence`, from a chatbot's answer about David West, state a fact about "
        "David: his work, skills, projects, background or circumstances?"
    ),
    "criteria": {
        "true": "It asserts something about David that could be true or false.",
        "false": (
            "It is filler, such as a greeting, an offer to help, a heading or a "
            "transition, and asserts nothing about David."
        ),
    },
}

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


class JevJudge:
    """A Judge asking TypeSafe's Jev, pinned to `JEV_MODEL`.

    Every answer is checked against the pin, so `model` is the version that actually
    judged the run, not only the one requested. `usage` totals billed tokens.
    """

    def __init__(self, api_key: str, client: httpx.Client | None = None) -> None:
        self.model = JEV_MODEL
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._client = client or httpx.Client(timeout=60)

    def is_factual(self, sentence: str) -> bool:
        return self._yes({"sentence": sentence}, FACTUAL_QUESTION)

    def relation(self, sentence: str, chunk: str) -> Relation:
        answer = self._ask({"claim": sentence, "section": chunk}, SUPPORT_QUESTION)
        return Relation(answer["choice"], answer["probabilities"])

    def conveys(self, answer: str, fact: str) -> bool:
        return self._yes({"answer": answer, "fact": fact}, CONVEYS_QUESTION)

    def declines(self, question: str, answer: str) -> bool:
        return self._yes({"question": question, "answer": answer}, DECLINES_QUESTION)

    def _yes(self, state: dict, question: dict) -> bool:
        return self._ask(state, question)["noul"] >= 0.5

    def _ask(self, state: dict, question: dict) -> dict:
        body = {"model": self.model, "state": state, "questions": {"judgment": question}}
        for attempt in range(MAX_ATTEMPTS):
            response = self._client.post(JEV_URL, json=body, headers=self._headers)
            if response.status_code not in RETRY_STATUSES or attempt == MAX_ATTEMPTS - 1:
                break
            time.sleep(2**attempt)
        response.raise_for_status()
        data = response.json()
        if data["model"] != self.model:
            raise JudgeVersionChanged(
                f"Asked for {self.model}, answered by {data['model']}. Judgments from two "
                "versions are not one measurement."
            )
        for field in self.usage:
            self.usage[field] += data["usage"][field]
        return data["answers"]["judgment"]
