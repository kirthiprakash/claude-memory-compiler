"""Path constants and configuration for the personal knowledge base."""

import os
from pathlib import Path
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
HOOKS_DIR = ROOT_DIR / "hooks"
AGENTS_FILE = ROOT_DIR / "AGENTS.md"
REPORTS_DIR = ROOT_DIR / "reports"
STATE_FILE = SCRIPTS_DIR / "state.json"
LOG_FILE = SCRIPTS_DIR / "flush.log"

# Tolaria vault — flat structure, all notes at vault root
VAULT_DIR = Path(os.environ["MEMORY_OUTPUT_DIR"]).expanduser() if "MEMORY_OUTPUT_DIR" in os.environ else ROOT_DIR
INDEX_FILE = VAULT_DIR / "memory-index.md"

# Aliases kept for compatibility — all point to vault root (no subdirectories)
KNOWLEDGE_DIR = VAULT_DIR
DAILY_DIR = VAULT_DIR
CONCEPTS_DIR = VAULT_DIR
CONNECTIONS_DIR = VAULT_DIR
QA_DIR = VAULT_DIR

# ── Timezone ───────────────────────────────────────────────────────────
TIMEZONE = "America/Chicago"


def now_iso() -> str:
    """Current time in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today_iso() -> str:
    """Current date in ISO 8601 format."""
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
