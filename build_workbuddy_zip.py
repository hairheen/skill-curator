#!/usr/bin/env python3
"""Build a minimal, root-level ZIP for WorkBuddy's skill importer."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist/skill-curator-workbuddy.zip"
MANIFEST = ROOT / "SKILL.md"
EXTRA_METADATA = """display_name: Skill 管家
display_name_en: Skill Curator
description_zh: 盘点已安装技能，检查重复、冲突与触发场景，并预览可回滚的调整。
description_en: Audit installed skills, find overlaps and conflicts, and preview reversible improvements.
version: 1.1.0
author: hairheen
"""


def workbuddy_manifest() -> str:
    source = MANIFEST.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md needs YAML frontmatter")
    end = next((index for index, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError("SKILL.md frontmatter is not closed")
    result = "".join(lines[:end]) + EXTRA_METADATA + "".join(lines[end:])
    return result.replace("[references/host-notes.md](references/host-notes.md)", "@references/host-notes.md")


def main() -> None:
    resources = ("scripts/skill_curator.py", "references/host-notes.md")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        archive.writestr("SKILL.md", workbuddy_manifest())
        for relative in resources:
            archive.write(ROOT / relative, arcname=relative)
    with ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
        assert "SKILL.md" in names
        assert all(len(Path(name).parts) <= 2 for name in names)
    print(OUTPUT)


if __name__ == "__main__":
    main()
