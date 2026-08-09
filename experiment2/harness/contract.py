"""The interface a submitted procedure must satisfy. This file IS given to the agent.

Deliberately minimal and strategy-neutral. It states the required output shape and
provides a way to decline, and nothing else. It contains no hint about how to get
there -- no parsing helpers, no lookup scaffolding, no locale utilities.
"""

from __future__ import annotations

CANONICAL_COLUMNS = ["country", "product_id", "period", "sales"]


class Escalate(Exception):
    """Raise when the source cannot be normalized on available evidence.

    Correct escalation is a success, not a failure. Escalating something that
    could have been resolved safely is a cost, and is measured separately.
    """

    def __init__(self, reason: str, details: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.details = details or {}


class AskHuman(Exception):
    """Raise when a human must supply information that is NOT present in the source.

    Every use is recorded and later classified as inferable-from-source or
    genuinely-unavailable. Asking for something the data already contains counts
    against the procedure.
    """

    def __init__(self, question: str, why_not_inferable: str):
        super().__init__(question)
        self.question = question
        self.why_not_inferable = why_not_inferable
