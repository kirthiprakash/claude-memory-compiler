"""
Compile-state tracker for the journal skill.

Tracks which daily-log files have already been compiled into knowledge
articles, keyed by filename, with the file's content hash and the time of
compilation. Used by the /journal compile mode to skip already-processed logs
and by the nudge mechanism in /journal and /journal recall to count how many
daily logs are pending compilation.

State file: skills/journal/_lib/.compile-state.json (gitignored)

Schema:
    {
      "compiled": {
        "daily-log-2026-05-06.md": {
          "hash": "<sha256-first-16-hex>",
          "compiled_at": "2026-05-06T20:09:41+05:30"
        },
        ...
      }
    }

CLI:
    record <log-file> <hash>   Mark log as compiled with the given hash.
    query  <log-file>          Print JSON for one log (empty if not recorded).
    list                       Print the full compiled map as JSON.
    migrate <state-json>       One-time: import scripts/state.json["ingested"]
                               into this state file. Skips entries that already
                               exist locally.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent / ".compile-state.json"


def _load() -> dict:
    if not STATE_FILE.exists():
        return {"compiled": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"compiled": {}}
    if "compiled" not in data:
        data["compiled"] = {}
    return data


def _save(data: dict) -> None:
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def cmd_record(log_file: str, file_hash: str) -> int:
    data = _load()
    data["compiled"][log_file] = {"hash": file_hash, "compiled_at": _now_iso()}
    _save(data)
    print(json.dumps({"ok": True, "log": log_file, "hash": file_hash}))
    return 0


def cmd_query(log_file: str) -> int:
    data = _load()
    entry = data["compiled"].get(log_file)
    print(json.dumps(entry or {}))
    return 0


def cmd_list() -> int:
    print(json.dumps(_load()["compiled"], indent=2))
    return 0


def cmd_migrate(state_json_path: str) -> int:
    """One-time import from scripts/state.json's `ingested` map."""
    src = Path(state_json_path)
    if not src.exists():
        print(json.dumps({"ok": False, "error": f"not found: {state_json_path}"}))
        return 1
    src_data = json.loads(src.read_text(encoding="utf-8"))
    ingested = src_data.get("ingested", {})
    data = _load()
    imported = 0
    skipped = 0
    for log_file, entry in ingested.items():
        if log_file in data["compiled"]:
            skipped += 1
            continue
        data["compiled"][log_file] = {
            "hash": entry.get("hash", ""),
            "compiled_at": entry.get("compiled_at", _now_iso()),
        }
        imported += 1
    _save(data)
    print(json.dumps({"ok": True, "imported": imported, "skipped": skipped}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compile state tracker for the journal skill")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_record = sub.add_parser("record", help="Record a successful compile")
    p_record.add_argument("log_file")
    p_record.add_argument("file_hash")

    p_query = sub.add_parser("query", help="Print compile state for one log")
    p_query.add_argument("log_file")

    sub.add_parser("list", help="Print all compiled-log state as JSON")

    p_migrate = sub.add_parser("migrate", help="Import from scripts/state.json")
    p_migrate.add_argument("state_json_path")

    args = parser.parse_args()
    if args.cmd == "record":
        return cmd_record(args.log_file, args.file_hash)
    if args.cmd == "query":
        return cmd_query(args.log_file)
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "migrate":
        return cmd_migrate(args.state_json_path)
    return 1


if __name__ == "__main__":
    sys.exit(main())
