"""
List daily logs in the vault that have not yet been compiled into knowledge
articles. Used by the /journal compile mode and by the nudge mechanism in
/journal and /journal recall.

A log is considered "unprocessed" if either:
  - it has no entry in compile_state.py's recorded map, or
  - its current SHA-256-first-16 hash differs from the recorded hash.

Output is always JSON on stdout. With --quiet, no human-readable progress is
written to stderr.

CLI:
    --vault <path>          (required)  Vault directory containing daily-log-*.md
    --threshold <N>         (default 5) Count above which `above_threshold` is true
    --quiet                 Suppress stderr; stdout JSON unchanged

Output JSON shape:
    {
      "unprocessed": ["daily-log-2026-05-05.md", ...],
      "count": <int>,
      "threshold": <int>,
      "above_threshold": <bool>
    }
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / ".compile-state.json"


def file_hash(path: Path) -> str:
    """SHA-256 hash of a file (first 16 hex chars). Matches scripts/utils.py:file_hash."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _load_compiled() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data.get("compiled", {})


def list_unprocessed(vault: Path) -> list[str]:
    if not vault.exists():
        return []
    compiled = _load_compiled()
    out: list[str] = []
    for log_path in sorted(vault.glob("daily-log-*.md")):
        name = log_path.name
        recorded = compiled.get(name)
        current = file_hash(log_path)
        if recorded is None or recorded.get("hash") != current:
            out.append(name)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="List uncompiled daily logs in the vault")
    parser.add_argument("--vault", required=True, help="Vault directory")
    parser.add_argument("--threshold", type=int, default=5, help="Threshold for above_threshold flag")
    parser.add_argument("--quiet", action="store_true", help="Suppress stderr")
    args = parser.parse_args()

    vault = Path(args.vault).expanduser()
    if not args.quiet and not vault.exists():
        print(f"warn: vault does not exist: {vault}", file=sys.stderr)

    unprocessed = list_unprocessed(vault)
    count = len(unprocessed)
    payload = {
        "unprocessed": unprocessed,
        "count": count,
        "threshold": args.threshold,
        "above_threshold": count > args.threshold,
    }
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
