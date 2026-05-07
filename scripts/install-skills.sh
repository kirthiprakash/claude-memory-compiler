#!/usr/bin/env bash
#
# install-skills.sh — symlink the journal skill into your coding agent(s).
#
# Idempotent: safe to run multiple times. Removes a stale symlink/file at the
# target before creating the new symlink. Leaves a real (non-symlink) file at
# the target alone, prints a warning, and asks you to remove it manually.
#
# Targets:
#   ~/.claude/skills/journal     (Claude Code) — always attempted
#   ~/.copilot/skills/journal    (Copilot CLI) — only if ~/.copilot/skills exists
#
# Run from anywhere; resolves the repo root from this script's location.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_SRC="$REPO_DIR/skills/journal"

if [ ! -d "$SKILL_SRC" ]; then
  echo "error: skill source not found at $SKILL_SRC" >&2
  exit 1
fi

install_one() {
  local target_dir="$1"
  local target_link="$target_dir/journal"

  if [ ! -d "$target_dir" ]; then
    echo "skip: $target_dir does not exist (agent likely not installed)"
    return 0
  fi

  if [ -L "$target_link" ]; then
    rm "$target_link"
  elif [ -e "$target_link" ]; then
    echo "warn: $target_link exists and is not a symlink — leaving alone"
    echo "      (move or delete it manually, then re-run)"
    return 0
  fi

  ln -s "$SKILL_SRC" "$target_link"
  echo "ok:   $target_link -> $SKILL_SRC"
}

mkdir -p "$HOME/.claude/skills"
install_one "$HOME/.claude/skills"

# Copilot CLI: only install if the agent is set up
install_one "$HOME/.copilot/skills"

echo
echo "Done. The journal skill is now installed for the agents above."
echo "Restart your coding agent (or open a new session) to pick up the new skill."
