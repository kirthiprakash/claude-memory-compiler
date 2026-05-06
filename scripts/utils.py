"""Shared utilities for the personal knowledge base."""

import hashlib
import json
import re
from pathlib import Path

from config import (
    INDEX_FILE,
    STATE_FILE,
    VAULT_DIR,
)


# ── State management ──────────────────────────────────────────────────

def load_state() -> dict:
    """Load persistent state from state.json."""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"ingested": {}, "query_count": 0, "last_lint": None, "total_cost": 0.0}


def save_state(state: dict) -> None:
    """Save state to state.json."""
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ── File hashing ──────────────────────────────────────────────────────

def file_hash(path: Path) -> str:
    """SHA-256 hash of a file (first 16 hex chars)."""
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Slug / naming ─────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


# ── Wikilink helpers ──────────────────────────────────────────────────

def extract_wikilinks(content: str) -> list[str]:
    """Extract all [[wikilinks]] from markdown content."""
    return re.findall(r"\[\[([^\]]+)\]\]", content)


def wiki_article_exists(link: str) -> bool:
    """Check if a wikilinked article exists on disk."""
    return (VAULT_DIR / f"{link}.md").exists()


def _frontmatter_type(path: Path) -> str:
    """Extract the type: field from YAML frontmatter, or empty string."""
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return ""
    end = content.find("---", 3)
    if end == -1:
        return ""
    for line in content[3:end].splitlines():
        if line.startswith("type:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


_KNOWLEDGE_TYPES = {"Knowledge Article", "Connection", "Q&A"}


# ── Wiki content helpers ──────────────────────────────────────────────

def read_wiki_index() -> str:
    """Read the knowledge base index file."""
    if INDEX_FILE.exists():
        return INDEX_FILE.read_text(encoding="utf-8")
    return "# Claude Memory Index\n\n| Article | Summary | Compiled From | Updated |\n|---------|---------|---------------|---------|"


def read_all_wiki_content() -> str:
    """Read index + all wiki articles into a single string for context."""
    parts = [f"## INDEX\n\n{read_wiki_index()}"]
    for article_path in list_wiki_articles():
        content = article_path.read_text(encoding="utf-8")
        parts.append(f"## {article_path.name}\n\n{content}")
    return "\n\n---\n\n".join(parts)


def list_wiki_articles() -> list[Path]:
    """List knowledge articles in the vault (identified by type: frontmatter)."""
    if not VAULT_DIR.exists():
        return []
    return [f for f in sorted(VAULT_DIR.glob("*.md")) if _frontmatter_type(f) in _KNOWLEDGE_TYPES]


def list_raw_files() -> list[Path]:
    """List all daily log files (named daily-YYYY-MM-DD.md at vault root)."""
    if not VAULT_DIR.exists():
        return []
    return sorted(VAULT_DIR.glob("daily-*.md"))


# ── Index helpers ─────────────────────────────────────────────────────

def count_inbound_links(target: str, exclude_file: Path | None = None) -> int:
    """Count how many wiki articles link to a given target."""
    count = 0
    for article in list_wiki_articles():
        if article == exclude_file:
            continue
        if f"[[{target}]]" in article.read_text(encoding="utf-8"):
            count += 1
    return count


def get_article_word_count(path: Path) -> int:
    """Count words in an article, excluding YAML frontmatter."""
    content = path.read_text(encoding="utf-8")
    # Strip frontmatter
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            content = content[end + 3:]
    return len(content.split())


def build_index_entry(rel_path: str, summary: str, sources: str, updated: str) -> str:
    """Build a single index table row."""
    link = rel_path.replace(".md", "")
    return f"| [[{link}]] | {summary} | {sources} | {updated} |"
