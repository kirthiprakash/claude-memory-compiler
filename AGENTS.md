# AGENTS.md - Personal Knowledge Base Schema

> Adapted from [Andrej Karpathy's LLM Knowledge Base](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) architecture.
> Instead of ingesting external articles, this system compiles knowledge from your own AI conversations.

## The Compiler Analogy

```
daily-YYYY-MM-DD.md  = source code  (your conversations - the raw material)
LLM                  = compiler     (extracts and organizes knowledge)
knowledge articles   = executable   (structured, queryable knowledge base)
lint                 = test suite   (health checks for consistency)
queries              = runtime      (using the knowledge)
```

You don't manually organize your knowledge. You have conversations, and the LLM handles the synthesis, cross-referencing, and maintenance.

## Output Location

All generated files (daily logs + knowledge articles + index) are written to a single flat directory — the **vault** — controlled by the `MEMORY_OUTPUT_DIR` environment variable. If unset, the vault is the repo root. The vault is plain markdown with YAML frontmatter conventions (`type:`, `tags:`, `[[wikilinks]]`, relationship fields), so it drops cleanly into any flat-file knowledge tool the user already has.

```
$VAULT/
├── daily-2026-04-01.md          # Daily logs (type: Daily Log)
├── daily-2026-04-02.md
├── memory-index.md       # Master catalog of knowledge articles
├── supabase-auth.md             # Knowledge articles (type: Knowledge Article)
├── auth-and-webhooks.md         # Connection articles (type: Connection)
├── how-to-handle-auth.md        # Filed Q&A answers (type: Q&A)
└── ...
```

Articles are distinguished by `type:` frontmatter, not subdirectories — flat by design so they coexist with other vault notes.

---

## Skill Architecture (primary interface)

The system's primary interface is a single skill called **`journal`** with three modes selected by argument:

| Invocation | Mode | What it does |
|---|---|---|
| `/journal` | save (default) | Append/update an entry for the current session in today's daily-log file; upsert a row in `memory-index.md`'s `## Sessions` table |
| `/journal recall [arg]` | recall | Load relevant prior context from the vault. Args: (none) → show index summary; `yesterday` / `today` / `cwd` / `here` / `<session-id>` / `<topic>` |
| `/journal compile [arg]` | compile | Discover uncompiled daily logs, ask user to confirm if too many, extract knowledge articles, update the `## Knowledge Articles` table |

Files:

```
skills/journal/
├── SKILL.md              # Single text-heavy file — instructions for the LLM. Three-mode dispatch.
└── _lib/
    ├── unprocessed.py    # CLI: list uncompiled daily logs, apply threshold check
    └── compile_state.py  # CLI: record/query compile state per log
```

**Why a skill (not hooks):**
- Active-LLM execution: zero extra API round-trip. Free on Pro/Max subscriptions; only marginal turn tokens on API billing.
- Full conversation context: no transcript truncation. Hooks could only see the last 30 turns.
- Cross-agent portability: same SKILL.md works in Claude Code, Copilot CLI, and other coding agents that honor SKILL.md.
- No `hooks.json`-must-be-in-cwd limitation (Copilot CLI specifically had this).

**Concurrency**: skill writes use the Edit tool with the `<!-- MEMORY_MAINTENANCE_BOUNDARY -->` HTML-comment anchor in the daily-log file. Two parallel sessions writing the same daily log get optimistic-CAS retries naturally — if Edit fails because the anchor's surrounding context shifted, re-read and retry once.

**Watermark dedup** (within a session): each Session entry includes a `<!-- last-journaled: <ISO-timestamp> -->` marker. Re-running `/journal` in the same session within 30 minutes updates the existing entry instead of appending a new one, summarising only material added since the marker.

The legacy hook-based pipeline is described later in this document under [Hook System (legacy / opt-in)](#hook-system-legacy--opt-in). Hook source code remains in the repo but its config is removed by default.

---

## Architecture

### Layer 1: Daily Logs (Immutable Source)

Daily logs capture what happened in your AI coding sessions. Filename: `daily-YYYY-MM-DD.md` at the vault root.

Format:

```markdown
---
type: Daily Log
date: YYYY-MM-DD
---
# Daily Log: YYYY-MM-DD

## Sessions

### Session (HH:MM)

**Resume:** `claude --resume <session-id>`

**Context:** What the user was working on.

**Key Exchanges:**
- User asked about X, assistant explained Y
- Decided to use Z approach because...

**Decisions Made:**
- Chose library X over Y because...

**Lessons Learned:**
- Always do X before Y to avoid...

**Action Items:**
- [ ] Follow up on X

**References:**
- https://docs.example.com/some-page — official spec for X
- owner/repo — example plugin layout we adapted from

## Memory Maintenance

### Memory Flush (HH:MM)

FLUSH_OK - Nothing worth saving from this session
```

Session entries route under `## Sessions`, FLUSH_OK / FLUSH_ERROR entries route under `## Memory Maintenance`. The file is appended throughout the day by `flush.py`.

### Layer 2: Knowledge Articles (LLM-Owned)

Compiled by `compile.py` from daily logs. Flat `.md` files at the vault root, distinguished by `type:` frontmatter:

| `type:` value | Purpose |
|---------------|---------|
| `Knowledge Article` | Atomic concept (one per topic) |
| `Connection` | Cross-cutting synthesis linking 2+ concepts |
| `Q&A` | Filed query answer |

Plus the index file `memory-index.md` (master catalog).

### Layer 3: This File (AGENTS.md)

The schema that tells the LLM how to compile and maintain the knowledge base. This is the "compiler specification."

---

## Structural Files

### `memory-index.md` - Master Catalog (two tables)

The index file holds two tables that share one file: `## Knowledge Articles` (owned by the compile mode) and `## Sessions` (owned by the journal save mode).

Format:

```markdown
---
type: Memory Index
tags: [index]
updated: YYYY-MM-DD
---

# Memory Index

## Knowledge Articles

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[supabase-auth]] | Row-level security patterns and JWT gotchas | daily-log-2026-04-02 | 2026-04-02 |
| [[auth-and-webhooks]] | Token verification patterns shared across auth and webhooks | daily-log-2026-04-02, daily-log-2026-04-04 | 2026-04-04 |

## Sessions

| Date | Time | Session | Agent | CWD | Topic | Resume |
|------|------|---------|-------|-----|-------|--------|
| 2026-04-02 | 09:14 | abc12345 | claude-code | my-app | Auth bugs in middleware | `claude --resume abc12345-…` |
```

Wikilinks use the slug (filename without extension) — no subfolder prefix, since articles are flat.

**Ownership rule**: each table is written by exactly one mode of the journal skill. The compile mode never touches the Sessions table; the save mode never touches the Knowledge Articles table.

---

## Article Formats

All knowledge articles are flat `.md` files at the vault root, distinguished by `type:` frontmatter.

### Knowledge Article (`type: Knowledge Article`)

One article per atomic piece of knowledge. Filename: `kebab-case-slug.md`.

```markdown
---
type: Knowledge Article
tags: [domain, topic]
sources:
  - "[[daily-2026-04-01]]"
  - "[[daily-2026-04-03]]"
updated: 2026-04-03
---

# Concept Name

[2-4 sentence core explanation]

## Key Points

- [Bullet points, each self-contained]

## Details

[Deeper explanation, encyclopedia-style paragraphs]

## Related Concepts

- [[related-concept]] — How it connects

## Sources

- [[daily-2026-04-01]] — Initial discovery during project setup
- [[daily-2026-04-03]] — Updated after debugging session
```

### Connection (`type: Connection`)

Cross-cutting synthesis linking 2+ concepts. Created when a conversation reveals a non-obvious relationship.

```markdown
---
type: Connection
connects:
  - "[[concept-x]]"
  - "[[concept-y]]"
sources:
  - "[[daily-2026-04-04]]"
updated: 2026-04-04
---

# Connection: X and Y

## The Connection
## Key Insight
## Evidence
## Related Concepts

- [[concept-x]]
- [[concept-y]]
```

### Q&A (`type: Q&A`)

Filed answers from queries. Every complex question answered by the system can be permanently stored, making future queries smarter.

```markdown
---
type: Q&A
question: "The exact question asked"
consulted:
  - "[[article-1]]"
  - "[[article-2]]"
filed: 2026-04-05
---

# Q: Original Question

## Answer
## Sources Consulted
## Follow-Up Questions
```

---

## Core Operations

### 1. Compile (daily logs -> knowledge articles)

When processing a daily log:

1. Read the daily log file (`daily-YYYY-MM-DD.md`)
2. Read `memory-index.md` to understand current knowledge state
3. Read existing articles that may need updating
4. For each piece of knowledge found in the log:
   - If an existing knowledge article covers this topic: UPDATE it, add the daily log as a source
   - If it's a new topic: CREATE a new flat `slug.md` with `type: Knowledge Article` frontmatter
5. If the log reveals a non-obvious connection between 2+ existing concepts: CREATE a flat article with `type: Connection`
6. UPDATE `memory-index.md` with new/modified entries

**Important guidelines:**
- A single daily log may touch 3-10 knowledge articles
- Prefer updating existing articles over creating near-duplicates
- All output is flat at the vault root — no subdirectories
- Wikilinks reference the slug only (e.g. `[[supabase-auth]]`, no `concepts/` prefix)
- Write in encyclopedia style — factual, concise, self-contained
- Every article must have YAML frontmatter with a `type:` field
- Every article must link back to its source daily logs

### 2. Query (Ask the Knowledge Base)

1. Read `memory-index.md` (the master catalog)
2. Based on the question, identify 3-10 relevant articles from the index
3. Read those articles in full
4. Synthesize an answer with `[[wikilink]]` citations
5. If `--file-back` is specified: create a flat `slug.md` with `type: Q&A` frontmatter and update the index

**Why this works without RAG:** At personal knowledge base scale (50-500 articles), the LLM reading a structured index outperforms cosine similarity. The LLM understands what the question is really asking and selects pages accordingly. Embeddings find similar words; the LLM finds relevant concepts.

### 3. Lint (Health Checks)

Seven checks, run periodically:

1. **Broken links** - `[[wikilinks]]` pointing to non-existent articles
2. **Orphan pages** - Articles with zero inbound links from other articles
3. **Orphan sources** - Daily logs that haven't been compiled yet
4. **Stale articles** - Source daily log changed since article was last compiled
5. **Contradictions** - Conflicting claims across articles (requires LLM judgment)
6. **Missing backlinks** - A links to B but B doesn't link back to A
7. **Sparse articles** - Below 200 words, likely incomplete

Output: a markdown report with severity levels (error, warning, suggestion).

---

## Conventions

- **Wikilinks:** Use Obsidian-style `[[slug]]` without `.md` extension and without subfolder prefixes
- **Writing style:** Encyclopedia-style, factual, third-person where appropriate
- **Dates:** ISO 8601 (YYYY-MM-DD for dates)
- **File naming:** kebab-case (e.g., `supabase-row-level-security.md`); daily logs always `daily-YYYY-MM-DD.md`
- **Frontmatter:** Every article must have YAML frontmatter with at minimum a `type:` field; sources and updated dates required for knowledge articles
- **Sources:** Always link back to the daily log(s) that contributed to an article via `[[daily-YYYY-MM-DD]]`

---

## Full Project Structure

The repo holds the code; the vault holds the output. They are separate by design — the vault is wherever `MEMORY_OUTPUT_DIR` points (defaulting to the repo root if unset).

```
claude-memory-compiler/                # The code (this repo)
|-- .claude/
|   |-- settings.json                  # Project-local hooks (relative paths, portable)
|-- .gitignore
|-- AGENTS.md                          # This file - schema + full technical reference
|-- README.md
|-- pyproject.toml
|-- scripts/
|   |-- compile.py                     # Daily logs -> knowledge articles
|   |-- query.py                       # Ask questions (index-guided, no RAG)
|   |-- lint.py                        # 7 health checks
|   |-- flush.py                       # Extract memories from conversations (background)
|   |-- config.py                      # Path constants + MEMORY_OUTPUT_DIR resolution
|   |-- utils.py                       # Shared helpers
|   |-- state.json                     # Tracking (compile hashes, costs) - gitignored
|   |-- flush.log                      # Background process log - gitignored
|-- hooks/
|   |-- session-start.py               # Injects knowledge index into new sessions
|   |-- session-end.py                 # Extracts transcript -> spawns flush.py
|   |-- pre-compact.py                 # Safety net before auto-compaction
|-- reports/                           # Lint reports (gitignored)

$MEMORY_OUTPUT_DIR/                    # The vault (separate, e.g. ~/notes/)
|-- daily-YYYY-MM-DD.md                # Daily logs - one per day, type: Daily Log
|-- memory-index.md             # Master catalog of knowledge articles
|-- supabase-auth.md                   # Knowledge articles (type: Knowledge Article)
|-- auth-and-webhooks.md               # Connections (type: Connection)
|-- how-to-handle-redirects.md         # Q&A (type: Q&A)
```

Operational state (`state.json`, `flush.log`, temp context files) always lives in the repo's `scripts/` directory, regardless of `MEMORY_OUTPUT_DIR`. Only knowledge output respects the env var.

---

## Hook System (legacy / opt-in)

The hook-based pipeline below predates the skill. It still works (source code is preserved), but the recommended interface is the journal skill above. Reasons to consider hooks:
- You want truly automatic capture (skill requires you to type `/journal`).
- You want a `PreCompact` safety net to capture context before auto-compaction discards it.

Reasons to avoid hooks:
- They don't see beyond the last ~30 turns of the transcript (hardcoded truncation).
- They register at multiple levels (`~/.claude/settings.json` plus project `.claude/settings.json`), and both fire when the agent is opened in the repo, doubling the per-flush cost.
- Each fire spawns a separate `claude_agent_sdk.query()` round-trip (~$0.02-0.05 each on API billing, silent on subscription).

If you re-enable hooks, the recipe is below. The journal skill and the hooks both write to the same vault and are format-compatible — they can coexist if you want both.

Hooks fire automatically when Claude Code starts/ends/compacts. There are two valid scopes for hook configuration:

### Project-Local Hooks: `.claude/settings.json`

Fires only when Claude Code is opened *inside this repo*. Useful for testing or for users who only want to capture sessions in this project. Uses relative paths so the file is portable across users:

```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/session-start.py", "timeout": 15 }] }],
    "PreCompact":   [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/pre-compact.py",   "timeout": 10 }] }],
    "SessionEnd":   [{ "matcher": "", "hooks": [{ "type": "command", "command": "uv run python hooks/session-end.py",   "timeout": 10 }] }]
  }
}
```

### Global Hooks: `~/.claude/settings.json` (Recommended for Daily Use)

Fires for **every** Claude Code session in any project. Requires absolute paths and `MEMORY_OUTPUT_DIR` so output goes to a stable vault location:

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

- `uv run --directory <repo>` keeps Python deps isolated to the project's `.venv` — nothing pollutes global Python
- `MEMORY_OUTPUT_DIR` redirects daily logs and knowledge articles to the chosen vault. If unset, output stays in the repo. Tilde expansion is handled by the scripts.
- Empty `matcher` catches all events for that hook type.

### Hook Details

**`session-start.py`** (SessionStart)
- Pure local I/O, no API calls, runs in under 1 second
- Reads `memory-index.md` and the most recent daily log from the vault
- Outputs JSON to stdout: `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}`
- Claude sees the knowledge base index at the start of every session
- Max context: 20,000 characters

**`session-end.py`** (SessionEnd)
- Reads hook input from stdin (JSON with `session_id`, `transcript_path`, `cwd`)
- Copies the raw JSONL transcript to a temp file (no parsing in the hook - keeps it fast)
- Spawns `flush.py` as a fully detached background process
- Recursion guard: exits immediately if `CLAUDE_INVOKED_BY` env var is set

**`pre-compact.py`** (PreCompact)
- Same architecture as session-end.py
- Fires before Claude Code auto-compacts the context window
- Guards against empty `transcript_path` (known Claude Code bug #13668)
- Critical for long sessions: captures context before summarization discards it

**Why both PreCompact and SessionEnd?** Long-running sessions may trigger multiple auto-compactions before you close the session. Without PreCompact, intermediate context is lost to summarization before SessionEnd ever fires.

### Background Flush Process (`flush.py`)

Spawned by both hooks as a fully detached background process:
- **Windows:** `CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS` flags
- **Mac/Linux:** `start_new_session=True`

This ensures flush.py survives after Claude Code's hook process exits.

**What flush.py does:**
1. Sets `CLAUDE_INVOKED_BY=memory_flush` env var (prevents recursive hook firing)
2. Reads the pre-extracted conversation context from the temp `.md` file
3. Skips if context is empty or if same session was flushed within 60 seconds (deduplication)
4. Calls Claude Agent SDK (`query()` with `allowed_tools=[]`, `max_turns=2`)
5. Claude decides what's worth saving - returns structured bullet points or `FLUSH_OK`
6. Appends result to `$VAULT/daily-YYYY-MM-DD.md`, routing Session entries under `## Sessions` and FLUSH_OK entries under `## Memory Maintenance`
7. Cleans up temp context file
8. **End-of-day auto-compilation:** If it's past 6 PM local time (`COMPILE_AFTER_HOUR = 18`) and today's daily log has changed since its last compilation (hash comparison against `state.json`), spawns `compile.py` as another detached background process. This means compilation happens automatically once a day without needing a cron job or manual trigger.

### JSONL Transcript Format

Claude Code stores conversations as `.jsonl` files. Messages are nested under a `message` key:

```python
entry = json.loads(line)
msg = entry.get("message", {})
role = msg.get("role", "")     # "user" or "assistant"
content = msg.get("content", "")  # string or list of content blocks
```

Content can be a string or a list of blocks (`{"type": "text", "text": "..."}` dicts).

---

## Script Details

### compile.py - The Compiler

Uses the Claude Agent SDK's async streaming `query()`:

```python
async for message in query(
    prompt=compile_prompt,
    options=ClaudeAgentOptions(
        cwd=str(ROOT_DIR),
        system_prompt={"type": "preset", "preset": "claude_code"},
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=30,
    ),
):
```

- Builds a prompt with: AGENTS.md schema, current index, all existing articles, and the daily log
- Claude reads the daily log, decides what concepts to extract, and writes files directly
- `permission_mode="acceptEdits"` auto-approves all file operations
- Incremental: tracks SHA-256 hashes of daily logs in `state.json`, skips unchanged files
- Cost: ~$0.45-0.65 per daily log (increases as KB grows)

**CLI:**
```bash
uv run python scripts/compile.py              # compile new/changed only
uv run python scripts/compile.py --all        # force recompile everything
uv run python scripts/compile.py --file daily-2026-04-01.md
uv run python scripts/compile.py --dry-run
```

### query.py - Index-Guided Retrieval

Loads the entire knowledge base into context (index + all articles). No RAG.

At personal KB scale (50-500 articles), the LLM reading a structured index outperforms vector similarity. The LLM understands what you're really asking; cosine similarity just finds similar words.

**CLI:**
```bash
uv run python scripts/query.py "What auth patterns do I use?"
uv run python scripts/query.py "What's my error handling strategy?" --file-back
```

With `--file-back`, creates a flat Q&A article (`type: Q&A`) at the vault root and updates `memory-index.md`. This is the compounding loop — every question makes the KB smarter.

### lint.py - Health Checks

Seven checks:

| Check | Type | Catches |
|-------|------|---------|
| Broken links | Structural | `[[wikilinks]]` to non-existent articles |
| Orphan pages | Structural | Articles with zero inbound links |
| Orphan sources | Structural | Daily logs not yet compiled |
| Stale articles | Structural | Source logs changed since compilation |
| Missing backlinks | Structural | A links to B but B doesn't link back |
| Sparse articles | Structural | Under 200 words |
| Contradictions | LLM | Conflicting claims across articles |

**CLI:**
```bash
uv run python scripts/lint.py                    # all checks
uv run python scripts/lint.py --structural-only  # skip LLM check (free)
```

Reports saved to `reports/lint-YYYY-MM-DD.md`.

---

## State Tracking

`scripts/state.json` tracks:
- `ingested` - map of daily log filenames to SHA-256 hashes, compilation timestamps, and costs
- `query_count` - total queries run
- `last_lint` - timestamp of most recent lint
- `total_cost` - cumulative API cost

`scripts/last-flush.json` tracks flush deduplication (session_id + timestamp).

Both are gitignored and regenerated automatically.

---

## Dependencies

`pyproject.toml` (at project root):
- `claude-agent-sdk>=0.1.29` - Claude Agent SDK for LLM calls with tool use
- `python-dotenv>=1.0.0` - Environment variable management
- `tzdata>=2024.1` - Timezone data
- Python 3.12+, managed by [uv](https://docs.astral.sh/uv/)

No API key needed - uses Claude Code's built-in credentials at `~/.claude/.credentials.json`.

---

## Costs

| Operation | Cost |
|-----------|------|
| Compile one daily log | $0.45-0.65 |
| Query (no file-back) | ~$0.15-0.25 |
| Query (with file-back) | ~$0.25-0.40 |
| Full lint (with contradictions) | ~$0.15-0.25 |
| Structural lint only | $0.00 |
| Memory flush (per session) | ~$0.02-0.05 |

---

## Customization

### Additional Article Types

Add new types via the `type:` frontmatter field (e.g. `type: Person`, `type: Project`, `type: Tool`). Define the article format in this file (AGENTS.md) and add the new type string to `_KNOWLEDGE_TYPES` in `scripts/utils.py` so the new articles are discoverable by lint, query, and compile. No subdirectories to create — files stay flat at the vault root.

### Flat-file Knowledge Tool Integration

The output is pure markdown with `[[wikilinks]]` and `type:` frontmatter — works natively with any flat-file knowledge tool that honors YAML frontmatter (note-graph apps, Obsidian-style tools, etc.). Set `MEMORY_OUTPUT_DIR` to your vault root and the daily logs and knowledge articles render as native notes alongside whatever else lives in the vault.

### Scaling Beyond Index-Guided Retrieval

At ~2,000+ articles / ~2M+ tokens, the index becomes too large for the context window. At that point, add hybrid RAG (keyword + semantic search) as a retrieval layer before the LLM. See Karpathy's recommendation of `qmd` by Tobi Lutke for search at scale.
