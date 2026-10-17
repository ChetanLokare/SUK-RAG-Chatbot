"""
Conversation Memory Service

Purpose
-------
Maintains short-term conversation history
for chat sessions.

Features
--------
• per-session memory
• automatic size limits
• safe cleanup
• LLM-ready formatting
"""

from collections import defaultdict
from typing import List, Dict
import time


# =========================================================
# CONFIG
# =========================================================

MAX_MESSAGES_PER_SESSION = 50
SESSION_TTL_SECONDS = 3600  # 1 hour


# =========================================================
# STORAGE
# =========================================================

# session_id -> list of messages
_MEMORY: defaultdict[str, List[Dict]] = defaultdict(list)

# session_id -> last activity timestamp
_SESSION_ACTIVITY: Dict[str, float] = {}


# =========================================================
# CLEANUP OLD SESSIONS
# =========================================================

def _cleanup_sessions():

    now = time.time()

    expired_sessions = []

    for session_id, ts in _SESSION_ACTIVITY.items():

        if now - ts > SESSION_TTL_SECONDS:
            expired_sessions.append(session_id)

    for sid in expired_sessions:
        _MEMORY.pop(sid, None)
        _SESSION_ACTIVITY.pop(sid, None)


# =========================================================
# ADD MESSAGE
# =========================================================

def add_message(session_id: str, role: str, content: str):

    if not session_id or not role or not content:
        return

    _cleanup_sessions()

    messages = _MEMORY[session_id]

    messages.append({
        "role": role,
        "content": content.strip()
    })

    # limit memory size
    if len(messages) > MAX_MESSAGES_PER_SESSION:
        _MEMORY[session_id] = messages[-MAX_MESSAGES_PER_SESSION:]

    _SESSION_ACTIVITY[session_id] = time.time()


# =========================================================
# GET MEMORY
# =========================================================

def get_memory(session_id: str, limit: int = 8) -> List[Dict]:

    if not session_id:
        return []

    _cleanup_sessions()

    messages = _MEMORY.get(session_id, [])

    return messages[-limit:]


# =========================================================
# FORMAT MEMORY FOR LLM
# =========================================================

def format_memory_for_prompt(session_id: str, limit: int = 6) -> str:

    history = get_memory(session_id, limit)

    if not history:
        return ""

    lines = []

    for msg in history:

        role = msg.get("role", "user")
        content = msg.get("content", "")

        if not content:
            continue

        lines.append(f"{role}: {content}")

    return "\n".join(lines)


# =========================================================
# CLEAR MEMORY
# =========================================================

def clear_memory(session_id: str):

    if not session_id:
        return

    _MEMORY.pop(session_id, None)
    _SESSION_ACTIVITY.pop(session_id, None)


# =========================================================
# DEBUG INFO
# =========================================================

def memory_stats():

    return {
        "active_sessions": len(_MEMORY),
        "total_messages": sum(len(v) for v in _MEMORY.values())
    }