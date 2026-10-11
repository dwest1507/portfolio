"""Tests for the claim splitter's adapter: the requests it sends, not the model's splits.

How claims are judged is tested through the harness with a fake Judge
(test_generation_harness.py). What is pinned down here is what a fake cannot show: that
each request names the model and reasoning effort, carries the question with the
sentence, and asks for a list of claims, and that usage and the answering model are
recorded (ADR-0007).
"""

from __future__ import annotations

import json

import httpx
from openai import OpenAI

from eval.splitter import SPLITTER_MODEL, SPLITTER_REASONING_EFFORT, OpenAISplitter


def openai_answering(claims: list[str], requests: list | None = None) -> OpenAI:
    """An OpenAI client whose transport answers every request with `claims`."""

    def handle(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-6-luna-2026-09-01",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps({"claims": claims})},
                    }
                ],
                "usage": {"prompt_tokens": 300, "completion_tokens": 40, "total_tokens": 340},
            },
        )

    return OpenAI(
        api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handle))
    )


def test_a_sentence_is_split_with_its_question_by_the_pinned_model_and_effort():
    requests = []
    split = OpenAISplitter(openai_answering(["David works at Booz Allen."], requests))

    claims = split("Where does David work?", "He works at Booz Allen.")

    assert claims == ["David works at Booz Allen."]
    [body] = requests
    assert body["model"] == SPLITTER_MODEL == "gpt-6-luna"
    assert body["reasoning_effort"] == SPLITTER_REASONING_EFFORT == "low"
    assert body["response_format"]["type"] == "json_schema"
    assert json.loads(body["messages"][-1]["content"]) == {
        "question": "Where does David work?",
        "sentence": "He works at Booz Allen.",
    }


def test_the_answering_model_and_billed_usage_are_recorded():
    """The model the provider reports is the one recorded, as for a Generation."""
    split = OpenAISplitter(openai_answering(["David works at Booz Allen."]))

    split("Where does David work?", "He works at Booz Allen.")
    split("Where does David work?", "He is a Lead AI Engineer.")

    assert split.model == "gpt-6-luna-2026-09-01"
    assert split.usage == {"prompt_tokens": 600, "completion_tokens": 80, "total_tokens": 680}
