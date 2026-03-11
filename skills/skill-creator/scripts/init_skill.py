#!/usr/bin/env python3
"""Create a minimal skill scaffold for MiniOpenClaw."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def norm(name: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower())
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:64]


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: init_skill.py <name> [description]")
        return 1
    name = norm(sys.argv[1])
    if not name:
        print("Invalid skill name")
        return 1
    desc = " ".join(sys.argv[2:]).strip() or f"用于 {name} 场景的可复用技能。"

    project_root = Path(__file__).resolve().parents[3]
    skill_dir = project_root / "skills" / name
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)

    (skill_dir / "SKILL.md").write_text(
        (
            f"# {name}\n"
            f"{desc}\n\n"
            "## Trigger\n"
            f"- {name}\n\n"
            "## Goals\n"
            "- 明确输入输出\n"
            "- 输出可执行步骤\n"
        ),
        encoding="utf-8",
    )
    print(f"Created: {skill_dir / 'SKILL.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
