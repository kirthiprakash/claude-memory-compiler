---
name: journal
description: Personal session journal — capture the current conversation as a daily-log entry, recall prior context from the vault, and compile daily logs into knowledge articles. One slash command, three modes selected by the first argument. Use this skill whenever the user invokes `/journal`, `/journal recall`, or `/journal compile`. Works across any coding agent that supports skills (Claude Code, Copilot CLI, etc.) — the same SKILL.md drives all of them. Replaces the older flush-by-hook pipeline.
---

# /journal — Personal Session Journal

You are running the **journal skill**. Three modes:

| Invocation | Mode | What it does |
|---|---|---|
| `/journal` | **save** (default) | Append/update an entry for the current session in today's daily-log file |
| `/journal recall [arg]` | **recall** | Load relevant prior context from the vault |
| `/journal compile [arg]` | **compile** | Extract knowledge articles from uncompiled daily logs |

Dispatch on `$ARGUMENTS`. If `$ARGUMENTS` is empty → save mode. If it starts with `recall` → recall mode (rest of args go to recall). If it starts with `compile` → compile mode.

---

## Vault resolution (used by all modes)

```bash
VAULT="${MEMORY_OUTPUT_DIR:-$HOME/workspace/projects/opensource/claude-memory-compiler}"
DATE="$(date +%Y-%m-%d)"
TODAY_LOG="$VAULT/daily-log-$DATE.md"
INDEX="$VAULT/memory-index.md"
HELPERS_DIR="<repo-root>/skills/journal/_lib"   # discover via the symlink target of the skill, or via a SKILL_DIR env var
```

Resolve the agent's session id:

```bash
# Claude Code:
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-}"
AGENT="claude-code"
RESUME_CMD="claude --resume $SESSION_ID"

# Copilot CLI (fallback):
SESSION_ID="${COPILOT_SESSION_ID:-${CLAUDE_CODE_SESSION_ID:-}}"
[ -z "$SESSION_ID" ] && SESSION_ID="$(sqlite3 ~/.copilot/session-store.db \
  "SELECT id FROM sessions WHERE cwd = '$PWD' ORDER BY updated_at DESC LIMIT 1" 2>/dev/null)"
AGENT="copilot"
RESUME_CMD="copilot --resume $SESSION_ID"
```

If session_id can't be resolved, still proceed but use literal string `unknown` and skip the Resume line.

CWD basename for the index column: `basename "$PWD"`.

---

## Mode 1 — save (default `/journal`)

Build a structured daily-log entry from your active conversation memory and write it to the vault.

### Step 1: Build the entry body

Use **exactly** these section headers, in this order. Skip any section that has nothing meaningful to record (do NOT pad with filler):

```markdown
**Context:** [One-sentence description of what the user is working on this session]

**Key Exchanges:**
- [Important Q&A or non-obvious discussion points]

**Decisions Made:**
- [Decisions with rationale]

**Lessons Learned:**
- [Gotchas, patterns, surprising facts]

**Action Items:**
- [Follow-ups, TODOs, "next time" items]

**References:**
- <URL or owner/repo or identifier> — short note about why it's useful
- (only entries that were actually consulted or mentioned in the conversation; do not invent or pad)
```

Skip routine tool calls, file reads, and trivial back-and-forth. If the conversation is genuinely substanceless, write the entry anyway with whatever you have (don't emit a `FLUSH_OK`-style placeholder — that pattern is gone).

### Step 2: Decide append vs. update

Read `$TODAY_LOG`. Look for an existing `### Session (HH:MM)` block whose `**Resume:**` line contains `--resume $SESSION_ID`.

- **Found and updated < 30 minutes ago** (look for the trailing `<!-- last-journaled: <ISO> -->` marker): **update**. Keep the entry's H3 and Resume line; rewrite the body to incorporate everything new. Refresh the marker.
- **Found but updated ≥ 30 minutes ago, OR not found**: **append** a new entry.

### Step 3: Write to the daily log

If `$TODAY_LOG` doesn't exist, create it with this template:

```markdown
---
type: Daily Log
date: YYYY-MM-DD
---
# Daily Log: YYYY-MM-DD

## Sessions

<!-- MEMORY_MAINTENANCE_BOUNDARY -->
## Memory Maintenance

```

The HTML comment `<!-- MEMORY_MAINTENANCE_BOUNDARY -->` is your insertion anchor. Sessions go BEFORE it; maintenance entries (rare under skill model) go AFTER it.

For an **append**: use the Edit tool with `old_string="<!-- MEMORY_MAINTENANCE_BOUNDARY -->"` and `new_string=<your-new-entry>\n\n<!-- MEMORY_MAINTENANCE_BOUNDARY -->`. This is optimistic-CAS — if a parallel session changed the file between your Read and Edit, Edit fails; **re-read and retry once**. After two failures, tell the user.

Entry format (for both append and update):

```markdown
### Session (HH:MM)

**Resume:** `claude --resume <session-id>`
<!-- last-journaled: 2026-05-07T14:23:01+05:30 -->

**Context:** ...
**Key Exchanges:** ...
[etc.]
```

Use `date +"%Y-%m-%dT%H:%M:%S%z"` for the ISO timestamp; `date +%H:%M` for the H3 time.

### Step 4: Upsert the index row

Read `$INDEX`. Find the `## Sessions` table. Locate any row whose Session cell starts with the first 8 chars of `$SESSION_ID`. If found → **replace** that row. Otherwise → **insert** a new row at the bottom of the Sessions table.

Row format:

```markdown
| YYYY-MM-DD | HH:MM | abc12345 | claude-code | <cwd-basename> | <Topic from **Context:** line, ≤ 80 chars> | `claude --resume <full-session-id>` |
```

If `$INDEX` doesn't exist, create it with the schema shown in `## Index file format` below.

### Step 5: Nudge if backlog

After the write, run:

```bash
python "$HELPERS_DIR/unprocessed.py" --vault "$VAULT" --threshold 3 --quiet
```

If the JSON's `above_threshold` is `true`, append a single line to your response to the user:

> 💡 You have N uncompiled daily logs. Run `/journal compile` to extract them into knowledge articles.

Otherwise: stay silent. No nudge spam.

---

## Mode 2 — recall (`/journal recall [arg]`)

Dispatch on the argument:

| `$ARGUMENTS` | Behavior |
|---|---|
| `recall` (no further args) | Read `$INDEX`'s `## Sessions` table; print it as-is. Then ask: "Which entry/topic do you want to load? Or run `/journal recall yesterday` / `/journal recall today` / `/journal recall cwd` / `/journal recall <topic>`." |
| `recall yesterday` | Compute yesterday's date (`date -v-1d +%Y-%m-%d` on macOS, `date -d 'yesterday' +%Y-%m-%d` on Linux). Read `$VAULT/daily-log-<yesterday>.md` in full. If it doesn't exist, say so. |
| `recall today` | Read `$TODAY_LOG`. Skip the `## Memory Maintenance` section. |
| `recall cwd` or `recall here` | Read `$INDEX`'s Sessions table. Filter rows whose CWD column equals `basename "$PWD"`. For each match, read its daily-log entry (look up the Date column, open `daily-log-<date>.md`, find the entry by Session id prefix). |
| `recall <8-or-more-hex-chars>` | Treated as a session id. Find the matching row in the Sessions table; load that entry. |
| `recall <other-string>` | Topic search. Substring-match against the Topic column (Sessions) AND the Summary column (Knowledge Articles). Load matching daily-log entries and/or knowledge articles. |

Always include the nudge from Mode 1 step 5 at the end if the threshold check trips.

Don't open files outside `$VAULT`. Don't follow `[[wikilinks]]` recursively unless the user asks. Default to the most-recent matching entry first when many match.

---

## Mode 3 — compile (`/journal compile [arg]`)

Run the existing helper to discover unprocessed daily logs, confirm if there are too many, then compile them with the active LLM (you).

### Step 1: Discover

```bash
python "$HELPERS_DIR/unprocessed.py" --vault "$VAULT" --threshold 5
```

Parse the JSON.

- If `count == 0` → "All daily logs are up to date." Stop.
- If `above_threshold == true` → present the list of file names to the user and ask: "There are N uncompiled daily logs. Compile all? Or pick a subset?" Wait for their answer, then proceed with the chosen subset.
- Otherwise → proceed with all of `unprocessed`.

If the user passed an explicit argument (`/journal compile <date>` or `/journal compile <log-file>`), skip the helper and use only that one log.

### Step 2: For each daily log to compile

1. Read the daily log file in full.
2. Read `$INDEX` (specifically the `## Knowledge Articles` table) and existing knowledge articles. Use Glob `$VAULT/*.md`, then Read the first 12 lines of each candidate to filter to those with `type: Knowledge Article` (or `type: Connection` / `type: Q&A`) frontmatter. Skip files matching `daily-log-*.md`, `memory-index.md`, `daily-log.md` (the type definition), and any other file whose `type:` is `Type` or `Daily Log`.
3. Identify 3–7 distinct concepts in the daily log worth their own article. For each:
   - **Existing article** (matching slug or topic) → Read it, merge new content, add the daily-log filename to `sources:` array, refresh `updated:`. Use Edit with the existing content as `old_string`.
   - **New concept** → Write a new file at `$VAULT/<kebab-case-slug>.md` with this frontmatter:
     ```yaml
     ---
     type: Knowledge Article
     tags: [<topic>, <topic>]
     sources:
       - "[[<daily-log-stem>]]"
     updated: YYYY-MM-DD
     ---
     ```
     Body sections: `## Key Points` (3–5 bullets), `## Details` (2+ paragraphs), `## Related Concepts` (2+ `[[wikilinks]]`), `## Sources` (cite the daily log with what specifically came from it).
4. **Update the `## Knowledge Articles` table in `$INDEX`**. Upsert one row per article you created or updated:
   ```
   | [[<slug>]] | <one-line summary> | <daily-log-stem> | YYYY-MM-DD |
   ```
   Do NOT touch the `## Sessions` table here — that's owned by the save mode.
5. Mark the log compiled:
   ```bash
   python "$HELPERS_DIR/compile_state.py" record "<daily-log-name>.md" "<sha256-first-16-hex>"
   ```
   Compute the hash with `shasum -a 256 "$LOG_PATH" | awk '{print substr($1,1,16)}'` (or any equivalent).

### Step 3: Final summary

Print: "Compiled N daily log(s); created M articles; updated K articles."

Concurrency: `compile_state.py record` is atomic per call (single-file rewrite). Two parallel `/journal compile` runs would step on each other's article writes; ask the user not to run two at once. (If this becomes a real problem, future work: file lock around the helper.)

---

## Index file format (`memory-index.md`)

```markdown
---
type: Memory Index
tags: [index]
updated: YYYY-MM-DD
_organized: true
---

# Memory Index

## Knowledge Articles

| Article | Summary | Compiled From | Updated |
|---------|---------|---------------|---------|
| [[some-slug]] | One-line summary | daily-log-2026-05-06 | 2026-05-06 |

## Sessions

| Date | Time | Session | Agent | CWD | Topic | Resume |
|------|------|---------|-------|-----|-------|--------|
| 2026-05-07 | 07:45 | abc12345 | claude-code | qlik-sde | Qlik SDE API key mgmt | `claude --resume abc12345-…` |
```

`_organized: true` is host-app-managed — leave it alone if present, omit if creating fresh.

---

## Helper script invocations (cheat sheet)

These are the only Python calls this skill should make. Resolve `$HELPERS_DIR` from the SKILL.md's directory (the skill is installed as a symlink; `readlink "$0"` or `dirname` of the SKILL.md location works).

```bash
# List unprocessed daily logs (always returns JSON on stdout)
python "$HELPERS_DIR/unprocessed.py" --vault "$VAULT" --threshold 5 [--quiet]

# Record a successful compile
python "$HELPERS_DIR/compile_state.py" record <log-file> <sha256-first-16-hex>

# Query a single log's compile state
python "$HELPERS_DIR/compile_state.py" query <log-file>

# List all recorded compile states
python "$HELPERS_DIR/compile_state.py" list
```

---

## Error handling

- If `$MEMORY_OUTPUT_DIR` is not set, fall back to the repo root and warn the user once: "MEMORY_OUTPUT_DIR is not set; writing to <repo-root>. Set it to point at your knowledge vault."
- If a Read fails on the index or a daily log, attempt to create the file with a fresh template before giving up.
- If `$SESSION_ID` cannot be resolved, append the entry without a Resume line and tell the user.
- If you need to ask the user something (compile-threshold confirmation, recall-disambiguation), use AskUserQuestion when available, otherwise a plain prompt.

---

## What this skill replaces

This skill replaces the older hook-based pipeline (`hooks/session-end.py` → `scripts/flush.py` → daily log + compile). The hooks are kept in the repo as opt-in but their config is removed. The old pipeline had hardcoded transcript truncation (last 30 turns), duplicate-fire bugs, and a separate Claude Agent SDK round-trip per flush; the skill avoids all of that by working directly from the active session's context.
