"""
SessionStart hook for GitHub Copilot CLI.

Reads the knowledge base index and recent daily log from the vault and outputs
JSON that Copilot CLI injects as additionalContext at the start of every
session — same pattern as the Claude Code session-start hook.

Hook input on stdin (Copilot format):
    {"timestamp": <ms>, "cwd": "<dir>", "source": "new|resume|startup",
     "initialPrompt": "..."}

Hook output on stdout:
    {"additionalContext": "<markdown>"}

If MEMORY_OUTPUT_DIR is unset the script falls back to the repo root.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_VAULT = Path(os.environ["MEMORY_OUTPUT_DIR"]).expanduser() if "MEMORY_OUTPUT_DIR" in os.environ else ROOT
INDEX_FILE = _VAULT / "claude-memory-index.md"

MAX_CONTEXT_CHARS = 20_000
MAX_LOG_LINES = 30


def get_recent_log() -> str:
    today = datetime.now(timezone.utc).astimezone()
    for offset in range(2):
        date = today - timedelta(days=offset)
        log_path = _VAULT / f"daily-{date.strftime('%Y-%m-%d')}.md"
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            recent = lines[-MAX_LOG_LINES:] if len(lines) > MAX_LOG_LINES else lines
            return "\n".join(recent)
    return "(no recent daily log)"


def build_context() -> str:
    parts = []
    today = datetime.now(timezone.utc).astimezone()
    parts.append(f"## Today\n{today.strftime('%A, %B %d, %Y')}")

    if INDEX_FILE.exists():
        parts.append(f"## Knowledge Base Index\n\n{INDEX_FILE.read_text(encoding='utf-8')}")
    else:
        parts.append("## Knowledge Base Index\n\n(empty - no articles compiled yet)")

    parts.append(f"## Recent Daily Log\n\n{get_recent_log()}")

    context = "\n\n---\n\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n\n...(truncated)"
    return context


def main() -> None:
    # Drain stdin to be polite (input is provided but we don't need any field from it)
    try:
        sys.stdin.read()
    except Exception:
        pass

    print(json.dumps({"additionalContext": build_context()}))


if __name__ == "__main__":
    main()
