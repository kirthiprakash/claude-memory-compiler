# LLM Personal Knowledge Base

**Your AI conversations compile themselves into a searchable knowledge base.**

Adapted from [Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture, but instead of clipping web articles, the raw data is your own conversations with AI coding agents. Whenever you finish a meaningful chunk of work, you invoke a slash command (`/journal`); the active LLM extracts decisions, lessons, action items, and references from the conversation it just had with you and appends them to a daily log in your vault. A second mode (`/journal recall`) loads relevant prior context back into a future session, and a third (`/journal compile`) extracts cross-cutting knowledge articles from accumulated daily logs. Retrieval uses a simple index file instead of RAG — no vector database, no embeddings, just markdown.

The vault is plain markdown with YAML frontmatter (`type:`, `tags:`, `[[wikilinks]]`, relationship fields) — drops cleanly into any flat-file knowledge tool you already use.

This skill works in any coding agent that supports a SKILL.md format — Claude Code and GitHub Copilot CLI today; portable to others without changes. Because all the LLM work happens *inside the active session*, there's no separate API round-trip and no extra billing on personal subscriptions.

## Quick Start

1. **Clone and install dependencies:**
   ```bash
   git clone https://github.com/coleam00/claude-memory-compiler && cd claude-memory-compiler
   uv sync
   ```

2. **Pick a vault location** (anywhere you keep markdown notes — or any plain folder):
   ```bash
   export MEMORY_OUTPUT_DIR="$HOME/path/to/your/vault"
   ```
   Persist this in your shell rc file so every coding agent session inherits it.

3. **Install the journal skill** into your agent(s):
   ```bash
   ./scripts/install-skills.sh
   ```
   This symlinks `skills/journal` into `~/.claude/skills/journal` (and `~/.copilot/skills/journal` if Copilot CLI is installed). Restart your coding agent to pick up the new skill.

4. **Use it.** Inside any coding agent session:
   ```
   /journal                  # save the current conversation as today's daily-log entry
   /journal recall           # show the index of past sessions
   /journal recall yesterday # load yesterday's daily log into context
   /journal recall cwd       # entries tied to the current working directory
   /journal compile          # turn unprocessed daily logs into knowledge articles
   ```

That's the whole system. Three commands behind one skill.

## How It Works

```
Conversation
   ├── /journal             → writes daily-log-YYYY-MM-DD.md + memory-index.md row
   │                         (active LLM uses Read/Edit/Write — no separate API call)
   ├── /journal recall …    → loads relevant prior context (today / yesterday / cwd / topic / session id)
   └── /journal compile     → distills daily logs into flat knowledge articles
                              with type: Knowledge Article frontmatter + cross-references
```

Vault layout (everything flat at the vault root):

```
$MEMORY_OUTPUT_DIR/
├── memory-index.md              # Two tables: ## Knowledge Articles + ## Sessions
├── daily-log-YYYY-MM-DD.md      # One per day, type: Daily Log
├── <slug>.md                    # Knowledge articles, type: Knowledge Article
├── <connection-slug>.md         # Cross-cutting, type: Connection
└── <qa-slug>.md                 # Filed Q&A answers, type: Q&A
```

The skill doesn't impose subdirectories — articles are organized by `type:` frontmatter so they coexist with whatever else lives in your vault.

## Why No RAG?

Karpathy's insight: at personal scale (50–500 articles), the LLM reading a structured `memory-index.md` outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words. RAG becomes necessary at ~2,000+ articles when the index exceeds the context window.

## Costs

Because all LLM work happens inside your active coding-agent session:

- **On a Claude Pro/Max subscription**: zero extra cost. `/journal`, `/journal recall`, and `/journal compile` are part of your normal session billing.
- **On API-key billing**: you pay only for the additional turn(s) the skill triggers in your session — no separate `claude_agent_sdk.query()` round-trip.

Compare to the older hook-based pipeline (still in this repo, opt-in only) which spawned a fresh `claude_agent_sdk.query()` call per session-end (~$0.02–0.05 per flush) plus a heavier compile call (~$0.30–0.45 per daily log). Those numbers no longer apply with the skill.

## Advanced: Automatic Capture via Hooks (legacy / opt-in)

The original implementation used Claude Code hooks (`SessionStart`, `SessionEnd`, `PreCompact`) to auto-capture every session. The skill replaces this for normal use, but the hook code stays in `hooks/` and `copilot-hooks/` if you want it back. Notable trade-offs of the hook path:

- Hooks fire automatically (good for compaction-safety; bad for duplicate fires when both global and project-local settings register them)
- Each hook spawns `flush.py`, which makes a separate `claude_agent_sdk.query()` call billed independently
- The hook only sees the last 30 turns (hard-coded transcript truncation) — long sessions miss substance from earlier
- Copilot's `hooks.json` only loads from the current working directory (no global config)

If you still want hooks active, see `hooks/` for the entry-point scripts, `scripts/flush.py` for the background pipeline, and the empty `.claude/settings.json` in this repo as a starting point. You'll need to add hook entries either there or in your global `~/.claude/settings.json`. The skill and the hooks can coexist (they write to the same vault and use compatible formats), but there's no longer a strong reason to run both.

## Key CLI Commands (helpers used by the skill)

The skill calls these for state tracking; you can run them by hand for debugging:

```bash
# How many daily logs are unprocessed (uncompiled)?
python skills/journal/_lib/unprocessed.py --vault "$MEMORY_OUTPUT_DIR" --threshold 5

# Inspect compile state for one log
python skills/journal/_lib/compile_state.py query daily-log-2026-05-07.md

# List everything that's been compiled
python skills/journal/_lib/compile_state.py list
```

## Technical Reference

See **[AGENTS.md](AGENTS.md)** for the complete technical reference: vault schema, skill internals, cross-agent portability, hook architecture (legacy), script internals.
