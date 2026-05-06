# LLM Personal Knowledge Base

**Your AI conversations compile themselves into a searchable knowledge base.**

Adapted from [Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture, but instead of clipping web articles, the raw data is your own conversations with Claude Code. When a session ends (or auto-compacts mid-session), Claude Code hooks capture the conversation transcript and spawn a background process that uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) to extract the important stuff - decisions, lessons learned, patterns, gotchas - and appends it to a daily log. You then compile those daily logs into structured, cross-referenced knowledge articles organized by concept. Retrieval uses a simple index file instead of RAG - no vector database, no embeddings, just markdown.

Anthropic has clarified that personal use of the Claude Agent SDK is covered under your existing Claude subscription (Max, Team, or Enterprise) - no separate API credits needed. Unlike OpenClaw, which requires API billing for its memory flush, this runs on your subscription.

## Quick Start

Tell your AI coding agent:

> "Clone https://github.com/coleam00/claude-memory-compiler into this project. Set up the Claude Code hooks so my conversations automatically get captured into daily logs, compiled into a knowledge base, and injected back into future sessions. Read the AGENTS.md for the full technical reference on how everything works."

The agent will:
1. Clone the repo and run `uv sync` to install dependencies
2. Copy `.claude/settings.json` into your project (or merge the hooks into your existing settings)
3. The hooks activate automatically next time you open Claude Code

From there, your conversations start accumulating. After 6 PM local time, the next session flush automatically triggers compilation of that day's logs into knowledge articles. You can also run `uv run python scripts/compile.py` manually at any time.

## How It Works

```
Conversation -> SessionEnd/PreCompact hooks -> flush.py extracts knowledge
    -> daily-YYYY-MM-DD.md -> compile.py -> flat knowledge articles + index
        -> SessionStart hook injects index into next session -> cycle repeats
```

- **Hooks** capture conversations automatically (session end + pre-compaction safety net)
- **flush.py** calls the Claude Agent SDK to decide what's worth saving, and after 6 PM triggers end-of-day compilation automatically
- **compile.py** turns daily logs into organized concept articles with cross-references (triggered automatically or run manually)
- **query.py** answers questions using index-guided retrieval (no RAG needed at personal scale)
- **lint.py** runs 7 health checks (broken links, orphans, contradictions, staleness)

Output is structured as flat markdown files identified by `type:` frontmatter (`Daily Log`, `Knowledge Article`, `Connection`, `Q&A`), so it drops cleanly into a Tolaria or Obsidian vault.

## Global Setup (Capture All Sessions, Write to a Vault)

The Quick Start above sets up project-local hooks that only fire when Claude Code is opened *inside this repo*. To capture every Claude Code session across all projects and route output to an external knowledge vault:

1. **Configure global hooks** in `~/.claude/settings.json` with absolute paths so they fire everywhere:

   ```json
   {
     "env": {
       "MEMORY_OUTPUT_DIR": "~/path/to/your/vault"
     },
     "hooks": {
       "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run --directory /abs/path/to/claude-memory-compiler python /abs/path/to/claude-memory-compiler/hooks/session-start.py", "timeout": 15 }] }],
       "PreCompact":   [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run --directory /abs/path/to/claude-memory-compiler python /abs/path/to/claude-memory-compiler/hooks/pre-compact.py",   "timeout": 10 }] }],
       "SessionEnd":   [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run --directory /abs/path/to/claude-memory-compiler python /abs/path/to/claude-memory-compiler/hooks/session-end.py",   "timeout": 10 }] }]
     }
   }
   ```

2. **`MEMORY_OUTPUT_DIR`** redirects daily logs and knowledge articles to your chosen folder. If unset, output stays in this repo's directory. Useful values:
   - A Tolaria vault (`~/workspace/documents/my-vault`) — files render as native notes
   - An Obsidian vault (`~/Documents/Obsidian/MyVault`) — same idea, picked up by Obsidian
   - Any plain folder if you just want them collected somewhere outside the repo

3. **`uv run --directory <repo>`** points uv at this project's `pyproject.toml` and `.venv`, so dependencies stay isolated to the project and don't pollute your global Python environment.

Operational state (`flush.log`, `state.json`, temp context files) always stays in the repo — only your knowledge output respects `MEMORY_OUTPUT_DIR`.

## GitHub Copilot CLI Support

The memory compiler also works with the GitHub Copilot CLI (`copilot`). Hook scripts adapted for Copilot's input format and SQLite session store live in `copilot-hooks/`.

**Differences vs. Claude Code:**
- Copilot's `sessionEnd` input has no `session_id` or transcript path — only `cwd` and `reason`. The hook resolves the session by querying `~/.copilot/session-store.db` for the most recent session matching `cwd`.
- Copilot loads `hooks.json` from the **current working directory** (not a global file), so hooks fire only in projects that have a `hooks.json`.
- Output reuses the same `flush.py` + vault format as Claude Code, so daily logs and knowledge articles end up alongside Claude Code's output in the same `MEMORY_OUTPUT_DIR`.

### Setup

1. Set two environment variables (e.g. in `~/.zshrc` or `~/.bashrc`):
   ```bash
   export MEMORY_OUTPUT_DIR="$HOME/path/to/your/vault"
   export MEMORY_COMPILER_DIR="$HOME/path/to/claude-memory-compiler"
   ```

2. Drop `copilot-hooks/hooks.json` into any project where you want Copilot conversations captured. Easiest: symlink it.
   ```bash
   ln -s "$MEMORY_COMPILER_DIR/copilot-hooks/hooks.json" hooks.json
   ```
   Or copy it if you don't want a symlink in the project tree. The committed `hooks.json` already uses `${MEMORY_COMPILER_DIR}` so the same file works across all projects without edits.

3. Run `copilot` in that project — `sessionStart` injects the vault index, `sessionEnd` queues a flush in the background.

To capture **every** Copilot session everywhere, drop the symlink into each project's root, or wrap `copilot` in a shell function that creates the symlink on demand:
```bash
copilot() {
  [ -e hooks.json ] || ln -s "$MEMORY_COMPILER_DIR/copilot-hooks/hooks.json" hooks.json
  command copilot "$@"
}
```

## Key Commands

```bash
uv run python scripts/compile.py                    # compile new daily logs
uv run python scripts/query.py "question"            # ask the knowledge base
uv run python scripts/query.py "question" --file-back # ask + save answer back
uv run python scripts/lint.py                        # run health checks
uv run python scripts/lint.py --structural-only      # free structural checks only
```

## Why No RAG?

Karpathy's insight: at personal scale (50-500 articles), the LLM reading a structured `index.md` outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words. RAG becomes necessary at ~2,000+ articles when the index exceeds the context window.

## Technical Reference

See **[AGENTS.md](AGENTS.md)** for the complete technical reference: article formats, hook architecture, script internals, cross-platform details, costs, and customization options. AGENTS.md is designed to give an AI agent everything it needs to understand, modify, or rebuild the system.
