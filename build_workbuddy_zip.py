#!/usr/bin/env python3
"""Build a minimal, root-level ZIP for WorkBuddy's skill importer."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "dist/skill-curator-workbuddy.zip"
MANIFEST = ROOT / "SKILL.md"
EXTRA_METADATA = """display_name: Skill 管家
display_name_en: Skill Curator
description_zh: 帮你盘点本机 Skills，找出同名、功能重复、规则冲突和触发问题；按任务推荐合适的 Skill。优化描述前先预览差异，修改后可验证、可回滚。
description_en: Audit local Agent Skills for duplicate names, overlapping capabilities, conflicting rules, and invocation issues. Recommend skills for a task and preview reversible description edits.
examples_zh:
  - "帮我检查一下已安装的 Skills，有没有重复或冲突？"
  - "我要做一份 PDF 报告，应该用哪个 Skill？"
  - "为什么这个 Skill 没触发？先帮我检查并预览优化建议。"
examples_en:
  - "Check my installed Skills for duplicates and conflicting rules."
  - "Which Skill should I use to create a PDF report?"
  - "Why did this Skill not trigger? Preview a better description."
version: 1.1.1
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
