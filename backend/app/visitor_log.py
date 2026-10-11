"""The visitor query log: what real visitors ask, and nothing more (ADR-0010).

Each chat request that reaches retrieval writes one JSON line to stdout, where Railway
collects it:

    {"event": "visitor_query", "question": "...", "chunks_retrieved": 3}

The question text grounds new Golden Set cases (Case Origin `visitor`), and the chunk
count gives the production Empty Context rate. Nothing else is recorded: no IP address,
no conversation history, no answer. docs/chatbot-rag.md describes how the log is read.
"""

import json
import logging
import sys

EVENT = "visitor_query"

logger = logging.getLogger("app.visitor_queries")
logger.setLevel(logging.INFO)
# Uvicorn configures only its own loggers, so without a handler of its own an INFO record
# from the app would be dropped. The root logger has no handler in production, so letting
# records propagate as well (which is how tests capture them) writes no duplicate line.
_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)


def log_visitor_query(question: str, chunks_retrieved: int) -> None:
    """Record one visitor question and how many chunks were retrieved for it."""
    record = {"event": EVENT, "question": question, "chunks_retrieved": chunks_retrieved}
    logger.info(json.dumps(record, ensure_ascii=False))
