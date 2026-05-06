"""
SessionEnd hook for GitHub Copilot CLI.

Copilot's sessionEnd hook input is {timestamp, cwd, reason} — there is no
session_id and no transcript path. We resolve the active session by querying
the Copilot SQLite session store for the most-recently-updated session whose
cwd matches the hook input, then read its turns, format them as markdown, and
spawn flush.py as a detached background process (same pattern as the Claude
Code hooks).

Operational state (logs, temp context files) lives in the repo's scripts/
directory, just like the Claude Code path. Only the daily log output respects
MEMORY_OUTPUT_DIR.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Recursion guard
if os.environ.get("CLAUDE_INVOKED_BY"):
    sys.exit(0)

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
COPILOT_HOME = Path(os.environ.get("COPILOT_HOME", str(Path.home() / ".copilot")))
SESSION_DB = COPILOT_HOME / "session-store.db"

logging.basicConfig(
    filename=str(SCRIPTS_DIR / "flush.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [copilot-hook] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

MAX_TURNS = 30
MAX_CONTEXT_CHARS = 15_000
MIN_TURNS_TO_FLUSH = 1


def find_session_for_cwd(cwd: str) -> str | None:
    """Return the session_id of the most-recently-updated session matching cwd."""
    if not SESSION_DB.exists():
        logging.info("No Copilot session DB at %s", SESSION_DB)
        return None
    try:
        # Open read-only to avoid lock contention with Copilot itself
        conn = sqlite3.connect(f"file:{SESSION_DB}?mode=ro", uri=True, timeout=2)
        try:
            row = conn.execute(
                "SELECT id FROM sessions WHERE cwd = ? ORDER BY updated_at DESC LIMIT 1",
                (cwd,),
            ).fetchone()
        finally:
            conn.close()
        return row[0] if row else None
    except sqlite3.Error as e:
        logging.error("SQLite error finding session for %s: %s", cwd, e)
        return None


def extract_conversation(session_id: str) -> tuple[str, int]:
    """Read the last N turns from the session and format as markdown."""
    conn = sqlite3.connect(f"file:{SESSION_DB}?mode=ro", uri=True, timeout=2)
    try:
        rows = conn.execute(
            "SELECT user_message, assistant_response FROM turns "
            "WHERE session_id = ? ORDER BY turn_index DESC LIMIT ?",
            (session_id, MAX_TURNS),
        ).fetchall()
    finally:
        conn.close()

    rows.reverse()
    parts: list[str] = []
    for user_msg, assistant_msg in rows:
        if user_msg:
            parts.append(f"**User:** {user_msg.strip()}\n")
        if assistant_msg:
            parts.append(f"**Assistant:** {assistant_msg.strip()}\n")

    context = "\n".join(parts)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[-MAX_CONTEXT_CHARS:]
        boundary = context.find("\n**")
        if boundary > 0:
            context = context[boundary + 1:]

    return context, len(rows)


def main() -> None:
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, ValueError) as e:
        logging.error("Failed to parse stdin: %s", e)
        return

    cwd = hook_input.get("cwd", "")
    reason = hook_input.get("reason", "unknown")
    logging.info("Copilot SessionEnd: cwd=%s reason=%s", cwd, reason)

    if not cwd:
        logging.info("SKIP: no cwd in hook input")
        return

    session_id = find_session_for_cwd(cwd)
    if not session_id:
        logging.info("SKIP: no Copilot session found for cwd=%s", cwd)
        return

    try:
        context, turn_count = extract_conversation(session_id)
    except sqlite3.Error as e:
        logging.error("Failed to extract conversation for %s: %s", session_id, e)
        return

    if not context.strip():
        logging.info("SKIP: empty context for session %s", session_id)
        return

    if turn_count < MIN_TURNS_TO_FLUSH:
        logging.info("SKIP: only %d turns (min %d)", turn_count, MIN_TURNS_TO_FLUSH)
        return

    timestamp = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")
    context_file = SCRIPTS_DIR / f"copilot-flush-{session_id}-{timestamp}.md"
    context_file.write_text(context, encoding="utf-8")

    flush_script = SCRIPTS_DIR / "flush.py"
    cmd = ["uv", "run", "--directory", str(ROOT), "python", str(flush_script),
           str(context_file), f"copilot-{session_id}"]

    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        logging.info("Spawned flush.py for Copilot session %s (%d turns, %d chars)",
                     session_id, turn_count, len(context))
    except Exception as e:
        logging.error("Failed to spawn flush.py: %s", e)


if __name__ == "__main__":
    main()
