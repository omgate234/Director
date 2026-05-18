"""Skill resolver for the Director reasoning engine.

A *skill* is a self-contained, task-specific instruction package. The
reasoning engine is told each skill's name, description, and absolute path at
startup; it reads the full SKILL.md on-demand via ``bash_executor`` (e.g.
``cat <location>``) and then follows its instructions — a progressive
disclosure pattern borrowed from the Agent Skills standard
(https://agentskills.io/specification).

Discovery is intentionally flat:

    director/skills/<skill-name>/SKILL.md

No recursion, no nested skills, no ignore files. One directory per skill.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.expanduser("~/.agents/skills")

SKILL_FILENAME = "SKILL.md"
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Skill:
    """A discovered skill.

    ``file_path`` and ``base_dir`` are always absolute so the model can use
    them verbatim in bash commands regardless of the process CWD.
    """

    name: str
    description: str
    file_path: str
    base_dir: str
    disable_model_invocation: bool = False


# --- Tiny YAML frontmatter parser -------------------------------------------
#
# Skills only carry a handful of scalar keys (``name``, ``description``,
# ``disable-model-invocation``). A 30-line hand parser covers the real-world
# surface area without pulling in PyYAML.

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^([A-Za-z][\w-]*)\s*:\s*(.*?)\s*$")


def _coerce(value: str):
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_frontmatter(text: str) -> Dict[str, object]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    data: Dict[str, object] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kv = _KEY_VALUE_RE.match(line)
        if kv:
            data[kv.group(1)] = _coerce(kv.group(2))
    return data


def _validate(name: str, parent_dir_name: str, description: str) -> List[str]:
    errs: List[str] = []
    if name != parent_dir_name:
        errs.append(f"name {name!r} does not match directory {parent_dir_name!r}")
    if not _NAME_RE.match(name) or len(name) > MAX_NAME_LENGTH:
        errs.append(
            f"name {name!r} is invalid "
            f"(lowercase a-z, 0-9, hyphens, ≤{MAX_NAME_LENGTH} chars, no leading/trailing/double hyphens)"
        )
    if len(description) > MAX_DESCRIPTION_LENGTH:
        errs.append(f"description exceeds {MAX_DESCRIPTION_LENGTH} characters")
    return errs


def _load_one(skill_dir: str) -> Optional[Skill]:
    file_path = os.path.join(skill_dir, SKILL_FILENAME)
    if not os.path.isfile(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        logger.warning("Failed to read skill %s: %s", file_path, e)
        return None

    fm = _parse_frontmatter(raw)
    parent = os.path.basename(skill_dir)
    name = str(fm.get("name") or parent)
    description = str(fm.get("description") or "").strip()

    if not description:
        logger.warning("Skill %s: missing required 'description' — skipping", file_path)
        return None

    for err in _validate(name, parent, description):
        logger.warning("Skill %s: %s", file_path, err)

    return Skill(
        name=name,
        description=description,
        file_path=file_path,
        base_dir=skill_dir,
        disable_model_invocation=bool(fm.get("disable-model-invocation", False)),
    )


def load_skills(skills_dir: str = SKILLS_DIR) -> List[Skill]:
    """Discover skills in ``<skills_dir>/<name>/SKILL.md``.

    Flat discovery: only immediate subdirectories containing ``SKILL.md`` are
    loaded. No recursion. Duplicate names are skipped with a warning (first
    one wins, sorted alphabetically).
    """
    if not os.path.isdir(skills_dir):
        return []

    skills: List[Skill] = []
    seen: set = set()

    for entry in sorted(os.listdir(skills_dir)):
        if entry.startswith(".") or entry == "__pycache__":
            continue

        candidate = os.path.join(skills_dir, entry)
        if not os.path.isdir(candidate):
            continue

        skill = _load_one(candidate)
        if skill is None:
            continue
        if skill.name in seen:
            logger.warning("Skill name collision for %r — skipping %s", skill.name, candidate)
            continue

        seen.add(skill.name)
        skills.append(skill)

    return skills


def _escape_xml(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def format_skills_for_prompt(skills: List[Skill]) -> str:
    """Render the system-prompt block describing available skills.

    Returns an empty string when no skills are visible (e.g. all of them opt
    out via ``disable-model-invocation``), so callers can always concatenate
    unconditionally.
    """
    visible = [s for s in skills if not s.disable_model_invocation]
    if not visible:
        return ""

    lines = [
        "",
        "## Skills",
        "",
        "The following skills provide specialized, task-specific instructions.",
        "Each `<location>` is an absolute path to a `SKILL.md` file.",
        "",
        "**When a user's task matches a skill's `<description>`:**",
        "1. Read the full SKILL.md first via `bash_executor` with `cat <location>`.",
        "2. Follow the instructions inside, then complete the task as usual.",
        "",
        "Any relative paths referenced inside a SKILL.md (helper scripts, data files, etc.) "
        "are rooted at its `<base_dir>`. When running a helper script, either set "
        "`bash_executor`'s `working_directory` to `<base_dir>`, or prefix the path with `<base_dir>`.",
        "",
        "<available_skills>",
    ]
    for s in visible:
        lines.append("  <skill>")
        lines.append(f"    <name>{_escape_xml(s.name)}</name>")
        lines.append(f"    <description>{_escape_xml(s.description)}</description>")
        lines.append(f"    <location>{_escape_xml(s.file_path)}</location>")
        lines.append(f"    <base_dir>{_escape_xml(s.base_dir)}</base_dir>")
        lines.append("  </skill>")
    lines.append("</available_skills>")
    return "\n".join(lines)
