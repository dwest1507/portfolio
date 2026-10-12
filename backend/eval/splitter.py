"""Splits a sentence of an answer into claims for the Judge to check one at a time.

Jev is weak on multi-claim input. Asked about a whole compound sentence, it calls the
sentence supported when a chunk backs one part of it, and a strict question that it
backs every part fails the sentences whose parts different chunks back. A sentence is
therefore split into standalone claims first, and each claim is checked against each
chunk (ADR-0007, #81).

Jev returns judgments, not text, so the splitting is done by OpenAI's `gpt-6-luna`: the
cheapest candidate generator, already used by the harness (ADR-0008). It is the second
LLM step in judging, and it is not checked on its own: the Judge validation's pass bar
(docs/evaluation.md) measures the splitter and Jev together.
"""

from __future__ import annotations

import json
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from openai import OpenAI

SPLITTER_MODEL = "gpt-6-luna"
#: Pinned, because it changes the split: "low" is the one explicit value OpenAI's
#: reasoning models all accept (ADR-0007, amendment).
SPLITTER_REASONING_EFFORT = "low"
#: Caps reasoning and output tokens together; a split is a few short sentences.
SPLITTER_MAX_TOKENS = 2000

USAGE_FIELDS = ("prompt_tokens", "completion_tokens", "total_tokens")

INSTRUCTIONS = """You prepare sentences for fact-checking. Each sentence comes from a \
chatbot's answer to a question about David West, a software and AI engineer. Split the \
sentence into claims that can each be checked on its own against David's portfolio.

Rules:
- Each claim states one fact. A list becomes one claim per item, written as a plain \
statement ("David has used SQS."), never as "the following" or a heading followed by a colon.
- Keep every detail: numbers, dates, names, qualifiers such as "only", "every" or "about". \
Every detail of the sentence must appear in some claim.
- Add nothing. Do not infer, correct, soften or drop anything, even if it looks wrong.
- Make each claim stand alone: replace "he", "it", "the system" and the like with what \
they refer to, using the question. Write "David" for "I" or "he" when it means David.
- A sentence that states one fact is returned as one claim."""

CLAIMS_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "claims",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"claims": {"type": "array", "items": {"type": "string"}}},
            "required": ["claims"],
            "additionalProperties": False,
        },
    },
}


class OpenAISplitter:
    """Splits a sentence into claims with `SPLITTER_MODEL` on OpenAI.

    `model` is the ID the provider reports answering with, once it has answered, and
    `usage` totals billed tokens. Answers vary from run to run: OpenAI's reasoning models
    accept no temperature but the default. Safe to call from several threads at once: the
    usage total is updated under a lock, so no billed token is lost to a race.
    """

    def __init__(self, client: OpenAI) -> None:
        self.model = SPLITTER_MODEL
        self.usage = dict.fromkeys(USAGE_FIELDS, 0)
        self._client = client
        self._usage_lock = threading.Lock()

    def __call__(self, question: str, sentence: str) -> list[str]:
        response = self._client.chat.completions.create(
            model=SPLITTER_MODEL,
            messages=[
                {"role": "system", "content": INSTRUCTIONS},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "sentence": sentence}, ensure_ascii=False
                    ),
                },
            ],
            reasoning_effort=SPLITTER_REASONING_EFFORT,
            max_completion_tokens=SPLITTER_MAX_TOKENS,
            response_format=CLAIMS_FORMAT,
        )
        with self._usage_lock:
            self.model = response.model
            for field in USAGE_FIELDS:
                self.usage[field] += getattr(response.usage, field)
        return json.loads(response.choices[0].message.content or '{"claims": []}')["claims"]
