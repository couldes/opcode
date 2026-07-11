from __future__ import annotations

import json
import logging
from pathlib import Path

from datetime import datetime

from opcode_cli.memory.types import MemoryNote, MemoryType
from opcode_cli.provider.base import BaseProvider, Message

logger = logging.getLogger(__name__)

_SELECT_PROMPT = """\
You are a memory retrieval system for an AI coding assistant. Select relevant memories for the current user query.

## Available Memories (name — description)
{candidates}

## Current User Query
{query}

## Recent Tools Used
{recent_tools}

## Instructions
Select up to 5 memories relevant to the user's query. Consider:
- Topics directly related to the query
- User preferences or past feedback that apply
- Project decisions or constraints relevant to the task
- Recent tool usage context

Skip API documentation memories if the tools being used already handle them.

Output a JSON array of selected memory names (just the "name" field). Empty array if none are relevant.
Output ONLY the JSON array, no other text.
"""


def scan_memory_files(base_dir: Path, mem_type: MemoryType) -> list[MemoryNote]:
    """Read headers of all memory files of a given type from a directory."""
    notes: list[MemoryNote] = []
    type_dir = base_dir / mem_type.value
    if not type_dir.exists():
        return notes
    for file_path in sorted(type_dir.glob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8")
            meta, _ = _parse_frontmatter(content)
            notes.append(MemoryNote(
                name=meta.get("name", file_path.stem),
                description=meta.get("description", ""),
                type=mem_type,
                content="",  # not loaded yet
                file_path=file_path,
                updated_at=datetime.fromtimestamp(file_path.stat().st_mtime),
            ))
        except Exception as e:
            logger.warning("failed to scan memory %s: %s", file_path, e)
    return notes


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    """Parse YAML frontmatter, return (meta, body)."""
    if not content.startswith("---\n"):
        return {}, content
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}, content
    import yaml
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    return meta, parts[2].strip()


async def find_relevant_memories(
    query: str,
    project_dir: Path,
    user_dir: Path,
    provider: BaseProvider,
    recent_tools: list[str] | None = None,
    max_results: int = 5,
) -> list[MemoryNote]:
    """Full pipeline: scan dual-path memories, LLM-select, load full content."""
    # Step 1: scan all memory files (headers only)
    candidates: list[MemoryNote] = []
    for base_dir in (project_dir, user_dir):
        for mem_type in MemoryType:
            candidates.extend(scan_memory_files(base_dir, mem_type))

    if not candidates:
        return []

    # Step 2: build candidate index
    candidate_lines = [
        f"- {c.name} — {c.description}" for c in candidates
    ]

    tool_list = ", ".join(recent_tools) if recent_tools else "none"

    prompt = _SELECT_PROMPT.replace("{query}", query)
    prompt = prompt.replace("{candidates}", "\n".join(candidate_lines))
    prompt = prompt.replace("{recent_tools}", tool_list)

    # Step 3: LLM selection
    selected_names = await _query_selector(prompt, provider)
    if not selected_names:
        return []

    # Step 4: load full content for selected memories
    name_to_note = {c.name: c for c in candidates}
    result: list[MemoryNote] = []
    for name in selected_names[:max_results]:
        note = name_to_note.get(name)
        if note is None:
            continue
        try:
            full = note.file_path.read_text(encoding="utf-8")
            _, body = _parse_frontmatter(full)
            result.append(MemoryNote(
                name=note.name,
                description=note.description,
                type=note.type,
                content=body,
                file_path=note.file_path,
                updated_at=note.updated_at,
            ))
        except Exception as e:
            logger.warning("failed to load memory '%s': %s", name, e)

    return result


async def _query_selector(prompt: str, provider: BaseProvider) -> list[str]:
    """Call LLM to select relevant memory names."""
    try:
        content_parts: list[str] = []
        async for chunk in provider.achat(
            [Message(role="user", content=prompt)]
        ):
            if chunk.content:
                content_parts.append(chunk.content)
        content = "".join(content_parts)

        # Parse JSON array
        data = json.loads(content)
        if isinstance(data, list):
            return [str(item) for item in data if item]
    except (json.JSONDecodeError, Exception) as e:
        logger.debug("memory selector parse failed: %s", e)

    # Fallback: try to extract from text
    import re
    m = re.search(r'\[.*?\]', content, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return [str(item) for item in data if item]
        except (json.JSONDecodeError, Exception):
            pass

    return []
