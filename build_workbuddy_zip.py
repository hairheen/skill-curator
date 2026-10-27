#!/usr/bin/env python3
"""Build and verify a minimal WorkBuddy upload archive using standard Python."""

import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent
VERSION = "1.2.0"
OUTPUT = ROOT / "dist/skill-curator-workbuddy.zip"
MANIFEST = ROOT / "SKILL.md"
METADATA = {
    "display_name": "Skill 管家",
    "display_name_en": "Skill Curator",
    "description_zh": "一句话盘点本机 Skills，检查安装格式、同名技能、能力重复和规则冲突，按任务推荐合适的 Skill。优化触发描述前先预览差异，应用时保留备份，支持验证和回滚。",
    "description_en": "Audit local Skills for installation issues, duplicate names, overlaps and conflicting rules. Recommend suitable Skills and preview reversible description edits.",
    "examples_zh": [
        "帮我检查一下已安装的 Skills，有没有重复或冲突？",
        "我要做一份 PDF 报告，应该用哪个 Skill？",
        "为什么这个 Skill 没触发？先帮我检查并预览优化建议。",
    ],
    "examples_en": [
        "Check my installed Skills for duplicates and conflicting rules.",
        "Which Skill should I use to create a PDF report?",
        "Why did this Skill not trigger? Preview a better description.",
    ],
    "version": VERSION,
    "author": "hairheen",
}


def validate_metadata(metadata: dict) -> None:
    for key in ("display_name", "display_name_en", "description_zh", "description_en", "version", "author"):
        if not isinstance(metadata.get(key), str) or not metadata[key].strip():
            raise ValueError(f"missing or invalid WorkBuddy field: {key}")
    for key in ("examples_zh", "examples_en"):
        values = metadata.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values):
            raise ValueError(f"invalid WorkBuddy examples: {key}")
    if len(metadata["examples_zh"]) != len(metadata["examples_en"]):
        raise ValueError("WorkBuddy Chinese and English example counts must match")


def workbuddy_manifest() -> str:
    validate_metadata(METADATA)
    source = MANIFEST.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md needs YAML frontmatter")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError("SKILL.md frontmatter is not closed")
    name = re.search(r"^name:\s*([a-z0-9-]+)\s*$", "".join(lines[:end]), re.M)
    if not name or name.group(1) != "skill-curator":
        raise ValueError("preserve the existing skill-curator identifier for updates")
    fields = []
    for key, value in METADATA.items():
        if isinstance(value, list):
            fields.append(f"{key}:\n")
            fields.extend(f"  - {json.dumps(item, ensure_ascii=False)}\n" for item in value)
        else:
            fields.append(f"{key}: {json.dumps(value, ensure_ascii=False)}\n")
    result = "".join(lines[:end] + fields + lines[end:])
    result = result.replace("[references/host-notes.md](references/host-notes.md)", "@references/host-notes.md")
    return result + "\n## WorkBuddy default\n\nFor a general installation check in WorkBuddy, run `check --host workbuddy --no-cache --project <path> --json`. Scan other hosts only when requested. If no files are found, report the searched directories and distinguish an empty local directory from a host permission limitation; do not conclude that the user has no Skills installed.\n"


def main() -> None:
    resources = ("scripts/skill_curator.py", "references/host-notes.md")
    manifest = workbuddy_manifest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", ZIP_DEFLATED) as archive:
        archive.writestr("SKILL.md", manifest)
        for relative in resources:
            archive.write(ROOT / relative, arcname=relative)
    with ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or set(names) != {"SKILL.md", *resources}:
            raise ValueError("invalid WorkBuddy archive contents")
        for name in names:
            if len(Path(name).parts) > 2:
                raise ValueError(f"nested resource: {name}")
            archive.read(name).decode("utf-8")
    versioned = OUTPUT.with_name(f"skill-curator-workbuddy-v{VERSION}.zip")
    versioned.write_bytes(OUTPUT.read_bytes())
    print(versioned)


if __name__ == "__main__":
    main()
