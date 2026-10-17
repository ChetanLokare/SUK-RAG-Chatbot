# backend/core/conversation.py
"""
Conversation-history helpers for the /query endpoint.

The frontend already sends the running chat as `history`; the backend used
to ignore it, so follow-ups like "what about its fees?" had no context.

These helpers are pure functions (no web/LLM/DB imports) so they are easy
to test.
"""

import re
from typing import Any, Dict, List, Optional

MAX_HISTORY_MESSAGES = 6      # last N messages used
MAX_MESSAGE_CHARS = 500       # each message is truncated to this
FOLLOW_UP_MAX_WORDS = 5       # shorter questions are treated as follow-ups

_WORD = re.compile(r"\w+", flags=re.UNICODE)


def _role(value: Optional[str]) -> str:
    # the frontend calls the assistant "bot"
    return "user" if (value or "").lower() == "user" else "assistant"


def normalize_history(
    history: Optional[List[Any]],
    current_question: str,
) -> List[Dict[str, str]]:
    """
    Turn raw client history into [{"role": "user"|"assistant", "content": str}].

    - accepts "text" or "content" for the message body
    - drops empty messages
    - drops the trailing copy of the current question (the frontend appends
      the new question to history before sending it)
    - keeps only the most recent messages, each truncated
    """

    cleaned: List[Dict[str, str]] = []

    for item in history or []:

        if isinstance(item, dict):
            role, body = item.get("role"), item.get("text") or item.get("content")
        else:
            role = getattr(item, "role", None)
            body = getattr(item, "text", None) or getattr(item, "content", None)

        body = (body or "").strip()

        if not body:
            continue

        cleaned.append({"role": _role(role), "content": body[:MAX_MESSAGE_CHARS]})

    q = (current_question or "").strip()[:MAX_MESSAGE_CHARS]

    if cleaned and cleaned[-1]["role"] == "user" and cleaned[-1]["content"] == q:
        cleaned.pop()

    return cleaned[-MAX_HISTORY_MESSAGES:]


def build_retrieval_query(question: str, history: List[Dict[str, str]]) -> str:
    """
    Short follow-up questions ("and the fees?") search badly on their own.
    Prefix the previous user question so retrieval has the topic.
    """

    question = (question or "").strip()

    if len(_WORD.findall(question)) > FOLLOW_UP_MAX_WORDS:
        return question

    for msg in reversed(history):
        if msg["role"] == "user":
            return f"{msg['content']} {question}".strip()

    return question


def format_history(history: List[Dict[str, str]]) -> str:
    """Prompt block for the LLM. Empty string when there is no history."""

    if not history:
        return ""

    lines = [
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in history
    ]

    return (
        "PREVIOUS CONVERSATION (only to understand references such as "
        "'it' or 'that'; it is NOT a source of facts):\n"
        + "\n".join(lines)
    )
