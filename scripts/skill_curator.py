#!/usr/bin/env python3
"""Offline inventory and reversible description edits for local Agent Skills."""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import uuid
from pathlib import Path

MAX_SKILL_BYTES = 2_000_000
MAX_SCRIPT_BYTES = 500_000
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}
STOP = {"skill", "skills", "agent", "agents", "use", "when", "with", "from", "this", "that", "your", "for", "and", "the", "are", "can", "will", "user", "task", "file", "files", "using", "通过", "可以", "使用", "进行", "相关", "用户", "文件", "技能", "用于", "支持"}
CAPABILITIES = {
    "documents": r"\b(docx|word|document|pdf)\b|文档|文稿|排版",
    "spreadsheets": r"\b(xlsx|excel|spreadsheet|sheets?)\b|表格|电子表",
    "presentations": r"\b(pptx|powerpoint|slides?)\b|幻灯片|演示文稿",
    "web": r"\b(browser|web|website|frontend|site)\b|网页|网站|浏览器|前端",
    "images": r"\b(image|photo|visual|poster|graphic)\b|图片|图像|海报|视觉",
    "video": r"\b(video|film|animation)\b|视频|动画|影片",
    "code": r"\b(code|coding|repository|git|pull request|pr)\b|代码|仓库|编程",
    "security": r"\b(security|audit|vulnerability|permission)\b|安全|审计|权限|漏洞",
    "skills": r"\b(?:skills? (?:audit|inventory|management|manager|router|routing|conflict|selection)|(?:audit|inventory|manage|route) (?:installed )?skills?|skill collection|installed (?:\w+ ){0,6}skills?)\b|技能盘点|技能冲突|技能选择|技能路由|触发冲突|技能管理|已安装.{0,8}(?:技能|skills?)|(?:skills?).{0,8}(?:冲突|盘点|选择)",
    "research": r"\b(search|research|browse|lookup)\b|搜索|检索|调研|查找",
}
RULE_ACTIONS = {
    "approval": r"\b(?:ask (?:the )?user|ask for (?:approval|permission|confirmation)|confirm with (?:the )?user|approval|permission)\b|向用户确认|征求.{0,8}同意|询问用户|用户确认",
    "commit": r"\b(?:git commit|commit (?:changes|code|the branch)|push (?:changes|commits|to (?:remote|origin))|merge (?:the )?(?:pr|pull request|branch))\b|提交代码|推送(?:代码|提交)|合并(?:分支|PR|拉取请求)",
    "test": r"\b(test|tests|testing|validate)\b|测试|验证",
    "network": r"\b(browse|internet|network|web search)\b|联网|浏览网页|网络搜索",
    "install": r"\b(install|dependency|dependencies)\b|安装|依赖",
    "subagent": r"\b(subagent|sub-agent|delegate)\b|子代理|子agent|委派",
    "execute": r"\b(execute|run script|shell command)\b|执行脚本|运行命令",
}
NEGATIVE = re.compile(r"\b(never|do not|don't|must not|prohibit)\b|不得|禁止|不要|绝不", re.I)
POSITIVE = re.compile(r"\b(always|must|shall|required|ensure|should)\b|必须|总是|应当|务必", re.I)
COMMAND_POSITIVE = re.compile(r"^(?:[-*]\s*)?(?:\*\*)?(?:run|test|ask|install|browse|execute|commit|push|merge)\b|^(?:[-*]\s*)?(?:运行|测试|执行|安装|提交|推送)", re.I)
SECURITY_PATTERNS = {
    "download_and_execute": r"(?:curl|wget)\b.{0,150}\|\s*(?:sh|bash|zsh)\b",
    "destructive_command": r"\brm\s+-[A-Za-z]*r[A-Za-z]*f\b|\brm\s+-[A-Za-z]*f[A-Za-z]*r\b",
    "broad_permissions": r"\bchmod\s+(?:-R\s+)?777\b",
    "credential_exfil_hint": r"\b(?:curl|wget|fetch|requests\.post|upload)\b.{0,120}\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|AWS_SECRET_ACCESS_KEY|\.env)\b",
}


@dataclasses.dataclass
class Skill:
    name: str
    description: str
    body: str
    path: str
    host: str
    scope: str
    root: str
    mutable: bool
    invocation: str
    sha256: str
    capabilities: list[str]
    problems: list[str]

    def public(self) -> dict:
        data = dataclasses.asdict(self)
        data.pop("body")
        return data


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_limited(path: Path, limit: int) -> bytes:
    if path.stat().st_size > limit:
        raise ValueError(f"file exceeds {limit} bytes")
    return path.read_bytes()


def scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value.split(" #", 1)[0].strip()


def frontmatter(text: str) -> tuple[dict[str, str], str, tuple[int, int] | None]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text, None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return {}, text, None
    fields: dict[str, str] = {}
    i = 1
    while i < end:
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", lines[i].rstrip("\r\n"))
        if not match:
            i += 1
            continue
        key, value = match.group(1), match.group(2)
        start = i
        i += 1
        while i < end and not re.match(r"^[A-Za-z][A-Za-z0-9_-]*:\s*", lines[i]):
            i += 1
        if value.startswith((">", "|")):
            parts = [line.strip() for line in lines[start + 1:i] if line.strip() and not line.lstrip().startswith("#")]
            fields[key] = (" ".join(parts) if value.startswith(">") else "\n".join(parts)).strip()
        else:
            fields[key] = scalar(value)
    return fields, "".join(lines[end + 1:]), (1, end)


def replace_description(text: str, description: str) -> str:
    fields, _, bounds = frontmatter(text)
    if bounds is None:
        raise ValueError("missing valid YAML frontmatter")
    lines = text.splitlines(keepends=True)
    end = bounds[1]
    start = next((i for i in range(1, end) if re.match(r"^description:\s*", lines[i])), None)
    if start is None:
        raise ValueError("description field is missing")
    stop = start + 1
    while stop < end and not re.match(r"^[A-Za-z][A-Za-z0-9_-]*:\s*", lines[stop]):
        stop += 1
    newline = "\r\n" if "\r\n" in text[:100] else "\n"
    lines[start:stop] = ["description: " + json.dumps(description, ensure_ascii=False) + newline]
    result = "".join(lines)
    parsed, _, _ = frontmatter(result)
    if parsed.get("description") != description:
        raise ValueError("description did not round-trip")
    return result


def tokens(text: str) -> set[str]:
    english = {x.lower() for x in re.findall(r"[A-Za-z][A-Za-z0-9+#.-]{1,}", text)}
    english = {x.strip(".+-") for x in english if x.strip(".+-") not in STOP}
    han = set()
    for segment in re.findall(r"[\u3400-\u9fff]+", text):
        if len(segment) == 2 and segment not in STOP:
            han.add(segment)
        for i in range(max(0, len(segment) - 1)):
            gram = segment[i:i + 2]
            if gram not in STOP:
                han.add(gram)
    return english | han


def infer_capabilities(text: str) -> list[str]:
    return [name for name, pattern in CAPABILITIES.items() if re.search(pattern, text, re.I)]


def project_dirs(project: Path) -> list[Path]:
    project = project.expanduser().resolve()
    ancestors = [project, *project.parents]
    git_root = next((p for p in ancestors if (p / ".git").exists()), None)
    if git_root is None:
        return [project]
    return ancestors[:ancestors.index(git_root) + 1]


def roots(project: Path, include_cache: bool) -> list[tuple[Path, str, str, bool, bool]]:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", str(home / ".codex"))).expanduser()
    result = [
        (home / ".agents/skills", "codex", "user", True, False),
        (codex_home / "skills", "codex", "legacy-user", True, False),
        (home / ".claude/skills", "claude", "user", True, False),
        (home / ".workbuddy/skills", "workbuddy", "user", True, False),
    ]
    for directory in project_dirs(project):
        result.extend([
            (directory / ".agents/skills", "codex", "project", True, False),
            (directory / ".claude/skills", "claude", "project", True, False),
            (directory / ".workbuddy/skills", "workbuddy", "project", True, False),
        ])
    if include_cache:
        result.extend([
            (codex_home / "plugins/cache", "codex", "cache", False, True),
            (home / ".claude/plugins/cache", "claude", "cache", False, True),
        ])
    return result


def scan_root(root: Path, recursive: bool) -> list[Path]:
    if not root.is_dir():
        return []
    if not recursive:
        return sorted(p / "SKILL.md" for p in root.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    found: list[Path] = []
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not (Path(current) / d).is_symlink()]
        if "SKILL.md" in files:
            found.append(Path(current) / "SKILL.md")
    return sorted(found)


def has_symlink(path: Path, root: Path) -> bool:
    current = path
    while True:
        if current.is_symlink():
            return True
        if current == root or current == current.parent:
            break
        current = current.parent
    return False


def load_skill(path: Path, root: Path, host: str, scope: str, mutable: bool) -> Skill:
    raw = read_limited(path, MAX_SKILL_BYTES)
    text = raw.decode("utf-8")
    meta, body, bounds = frontmatter(text)
    name = meta.get("name", "") or path.parent.name
    description = meta.get("description", "")
    problems = []
    if bounds is None:
        problems.append("missing_frontmatter")
    if not meta.get("name"):
        problems.append("missing_name")
    if not description:
        problems.append("missing_description")
    if name != path.parent.name:
        problems.append("name_directory_mismatch")
    if len(description) > 1024:
        problems.append("description_over_1024_chars")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        problems.append("nonstandard_name")
    linked = has_symlink(path, root)
    if linked:
        problems.append("symlink_read_only")
    invocation = "implicit"
    if host == "claude" and meta.get("disable-model-invocation", "").lower() == "true":
        invocation = "user-only"
    if host == "claude" and meta.get("user-invocable", "").lower() == "false":
        invocation = "model-only"
    if host == "codex":
        ui = path.parent / "agents/openai.yaml"
        try:
            if re.search(r"^\s*allow_implicit_invocation:\s*false\b", read_limited(ui, 50_000).decode("utf-8"), re.M):
                invocation = "explicit-only"
        except (OSError, ValueError, UnicodeError):
            pass
    return Skill(name, description, body, str(path.absolute()), host, scope, str(root.absolute()), mutable and not linked and scope != "cache", invocation, digest(raw), infer_capabilities(name + " " + description), problems)


def discover(project: Path, include_cache: bool = True, host: str = "both") -> tuple[list[Skill], list[str]]:
    found: list[Skill] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    for root, product, scope, mutable, recursive in roots(project, include_cache):
        if host not in ("both", "all", product):
            continue
        try:
            paths = scan_root(root, recursive)
        except OSError as exc:
            warnings.append(f"{root}: {exc}")
            continue
        for path in paths:
            key = (product, str(path.absolute()))
            if key in seen:
                continue
            seen.add(key)
            try:
                found.append(load_skill(path, root, product, scope, mutable))
            except (OSError, ValueError, UnicodeError) as exc:
                warnings.append(f"{path}: {exc}")
    found.sort(key=lambda s: (s.host, s.name, s.scope, s.path))
    return found, warnings


def comparable(a: Skill, b: Skill) -> bool:
    return a.host == b.host and a.path != b.path


def overlap(a: Skill, b: Skill, common: set[str]) -> dict | None:
    if not comparable(a, b):
        return None
    if a.name == b.name:
        return {"type": "same_name", "skills": [a.path, b.path], "names": [a.name, b.name], "evidence": "identical declared name"}
    if a.description.strip().casefold() == b.description.strip().casefold() and a.description.strip():
        return {"type": "possible_overlap", "skills": [a.path, b.path], "names": [a.name, b.name], "score": 1.0, "evidence": "identical descriptions"}
    at = tokens(a.name + " " + a.description) - common
    bt = tokens(b.name + " " + b.description) - common
    shared = at & bt
    union = at | bt
    score = len(shared) / len(union) if union else 0
    cap = sorted(set(a.capabilities) & set(b.capabilities))
    if len(shared) < 2 or score < 0.34 or not cap:
        return None
    return {"type": "possible_overlap", "skills": [a.path, b.path], "names": [a.name, b.name], "score": round(score, 3), "shared_terms": sorted(shared)[:12], "shared_capabilities": cap}


def rules(skill: Skill) -> list[dict]:
    result = []
    text = Path(skill.path).read_text(encoding="utf-8")
    _, body, bounds = frontmatter(text)
    offset = bounds[1] + 1 if bounds else 0
    for line_no, line in enumerate(body.splitlines(), offset + 1):
        for clause in re.split(r"[.;!?。；]", line):
            stripped = clause.strip()
            if not stripped or len(stripped) > 500:
                continue
            if re.search(r"\b(if|when|unless|except|only if)\b|如果|仅当|除非|例外", stripped, re.I):
                continue
            positive_match = POSITIVE.search(stripped)
            command_match = COMMAND_POSITIVE.search(stripped)
            negative_match = NEGATIVE.search(stripped)
            positive = bool(positive_match or command_match)
            negative = bool(negative_match)
            if positive == negative:
                continue
            polarity = "negative" if negative else "positive"
            tail = stripped[negative_match.end():] if negative_match else stripped[positive_match.end():] if positive_match else stripped
            action_phrase = " ".join(tail.split()[:6])
            for action, pattern in RULE_ACTIONS.items():
                if re.search(pattern, action_phrase, re.I):
                    result.append({"action": action, "polarity": polarity, "path": skill.path, "line": line_no, "quote": stripped[:240]})
    return result


def security_signals(skill: Skill) -> list[dict]:
    files = [Path(skill.path)]
    script_dir = Path(skill.path).parent / "scripts"
    if script_dir.is_dir() and not script_dir.is_symlink():
        files += [p for p in script_dir.rglob("*") if p.is_file() and not p.is_symlink() and p.suffix in {".py", ".sh", ".js", ".mjs", ".ts"}][:30]
    signals = []
    for path in files:
        try:
            content = read_limited(path, MAX_SCRIPT_BYTES).decode("utf-8")
        except (OSError, ValueError, UnicodeError):
            continue
        for line_no, line in enumerate(content.splitlines(), 1):
            for kind, pattern in SECURITY_PATTERNS.items():
                if re.search(pattern, line, re.I):
                    signals.append({"type": kind, "path": str(path), "line": line_no, "quote": line.strip()[:220]})
    return signals[:30]


def audit(skills: list[Skill]) -> dict:
    active = [s for s in skills if s.scope != "cache"]
    df: dict[str, int] = {}
    for skill in active:
        for term in tokens(skill.name + " " + skill.description):
            df[term] = df.get(term, 0) + 1
    common = {term for term, count in df.items() if len(active) >= 6 and count >= max(4, int(len(active) * 0.35))}
    overlaps = []
    conflicts = []
    rule_map = {s.path: rules(s) for s in active}
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            match = overlap(a, b, common)
            if match:
                overlaps.append(match)
            if not comparable(a, b) or a.sha256 == b.sha256:
                continue
            for action in RULE_ACTIONS:
                left_rules = [r for r in rule_map[a.path] if r["action"] == action]
                right_rules = [r for r in rule_map[b.path] if r["action"] == action]
                pair = next(((left, right) for left in left_rules for right in right_rules if left["polarity"] != right["polarity"]), None)
                if pair and len(conflicts) < 100:
                    conflicts.append({"type": "possible_rule_conflict", "action": action, "evidence": list(pair)})
    return {"skills": len(skills), "local_files_found": len(active), "cached_unverified": len(skills) - len(active), "overlaps": overlaps, "rule_conflicts": conflicts, "security_signals": [dict(skill=s.name, **signal) for s in skills for signal in security_signals(s)]}


def check_report(skills: list[Skill], warnings: list[str]) -> dict:
    """One read-only summary for a broad 'check my installed skills' request."""
    analysis = audit(skills)
    local = [skill for skill in skills if skill.scope != "cache"]
    installation_findings = [
        {"host": skill.host, "name": skill.name, "path": skill.path, "problems": [p for p in skill.problems if p != "symlink_read_only"]}
        for skill in local
        if any(p != "symlink_read_only" for p in skill.problems)
    ]
    same_name = [item for item in analysis["overlaps"] if item["type"] == "same_name"]
    return {
        "summary": {
            "local_files_found": len(local),
            "by_host": {host: sum(skill.host == host for skill in local) for host in ("codex", "claude", "workbuddy")},
            "cached_unverified": analysis["cached_unverified"],
            "installation_findings": len(installation_findings),
            "same_name": len(same_name),
            "possible_overlaps": len(analysis["overlaps"]) - len(same_name),
            "possible_rule_conflicts": len(analysis["rule_conflicts"]),
        },
        "installation_findings": installation_findings,
        "overlaps": analysis["overlaps"],
        "rule_conflicts": analysis["rule_conflicts"],
        "security_signals": analysis["security_signals"],
        "warnings": warnings,
        "note": "Files found do not prove host activation. Cache entries may be inactive. Review overlap and conflict evidence before changing a skill.",
    }


def route(skills: list[Skill], task: str, host: str) -> dict:
    candidates = [s for s in skills if s.scope != "cache" and (host in ("both", "all") or s.host == host)]
    query = tokens(task)
    wanted = set(infer_capabilities(task))
    scored = []
    for skill in candidates:
        terms = tokens(skill.name + " " + skill.description)
        matched = query & terms
        lexical = len(matched) / max(1, len(query))
        cap = wanted & set(skill.capabilities)
        if "skills" in wanted and "skills" not in cap:
            continue
        score = min(1.0, lexical * 0.8 + (0.2 if cap else 0))
        if score > 0:
            scored.append({"name": skill.name, "host": skill.host, "path": skill.path, "score": round(score, 3), "matched_terms": sorted(matched), "matched_capabilities": sorted(cap), "invocation": skill.invocation})
    scored.sort(key=lambda x: (-x["score"], x["name"], x["path"]))
    combo = []
    if len(scored) >= 2 and scored[1]["score"] >= 0.2:
        first, second = scored[:2]
        if set(first["matched_capabilities"]) != set(second["matched_capabilities"]):
            combo = [first["name"], second["name"]]
    return {"task": task, "host": host, "matches": scored[:8], "possible_combination": combo, "note": "Lexical diagnostic only; host model selection may differ."}


def eligible(path: Path, project: Path) -> Skill:
    skills, _ = discover(project, include_cache=False)
    target = str(path.absolute())
    skill = next((s for s in skills if s.path == target), None)
    if skill is None or not skill.mutable:
        raise ValueError("target is not a mutable local/project skill discovered for this project")
    if has_symlink(path, Path(skill.root)):
        raise ValueError("symlink-backed target is read-only")
    return skill


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".skill-curator-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, stat.S_IMODE(mode))
        os.replace(temp, path)
        try:
            dir_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode(), 0o600)


def default_state() -> Path:
    return Path.home() / ".skill-curator/transactions"


def plan(args: argparse.Namespace) -> int:
    project = Path(args.project).expanduser().resolve()
    path = Path(args.skill).expanduser().absolute()
    skill = eligible(path, project)
    description = args.description.strip()
    if not description or len(description) > 1024:
        raise ValueError("description must contain 1–1024 characters")
    before = read_limited(path, MAX_SKILL_BYTES)
    after = replace_description(before.decode("utf-8"), description).encode("utf-8")
    if before == after:
        raise ValueError("description is unchanged")
    payload = {"schema": 1, "project": str(project), "path": skill.path, "before_sha256": digest(before), "after_sha256": digest(after), "description": description}
    out = Path(args.out).expanduser().absolute()
    if out.exists():
        raise ValueError(f"plan already exists: {out}")
    write_json(out, payload)
    diff = difflib.unified_diff(before.decode("utf-8").splitlines(keepends=True), after.decode("utf-8").splitlines(keepends=True), fromfile=skill.path, tofile=skill.path + " (proposed)")
    print("".join(diff), end="")
    print(f"Plan: {out}")
    return 0


def apply(args: argparse.Namespace) -> int:
    payload = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if payload.get("schema") != 1:
        raise ValueError("unsupported plan schema")
    project = Path(payload["project"])
    path = Path(payload["path"])
    eligible(path, project)
    before = read_limited(path, MAX_SKILL_BYTES)
    if digest(before) != payload["before_sha256"]:
        raise ValueError("source changed after preview; create a new plan")
    after = replace_description(before.decode("utf-8"), payload["description"]).encode("utf-8")
    if digest(after) != payload["after_sha256"]:
        raise ValueError("plan content mismatch")
    state = Path(args.state_dir).expanduser().absolute()
    txid = uuid.uuid4().hex
    tx = state / txid
    tx.mkdir(parents=True, mode=0o700, exist_ok=False)
    backup = tx / "SKILL.md.before"
    with backup.open("xb") as stream:
        stream.write(before)
        stream.flush()
        os.fsync(stream.fileno())
    mode = path.stat().st_mode
    manifest = {"id": txid, "status": "prepared", "project": str(project), "path": str(path), "before_sha256": digest(before), "after_sha256": digest(after), "mode": stat.S_IMODE(mode)}
    write_json(tx / "manifest.json", manifest)
    eligible(path, project)
    if digest(read_limited(path, MAX_SKILL_BYTES)) != manifest["before_sha256"]:
        raise ValueError("source changed during apply; backup kept")
    atomic_write(path, after, mode)
    manifest["status"] = "applied"
    write_json(tx / "manifest.json", manifest)
    print(f"Applied: {path}\nRollback ID: {txid}\nState directory: {state}")
    return 0


def rollback(args: argparse.Namespace) -> int:
    if not re.fullmatch(r"[0-9a-f]{32}", args.id):
        raise ValueError("invalid rollback ID")
    tx = Path(args.state_dir).expanduser().absolute() / args.id
    manifest_path = tx / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("id") != args.id or manifest.get("status") not in {"prepared", "applied"}:
        raise ValueError("transaction cannot be rolled back")
    project = Path(manifest["project"])
    path = Path(manifest["path"])
    eligible(path, project)
    backup = read_limited(tx / "SKILL.md.before", MAX_SKILL_BYTES)
    if digest(backup) != manifest["before_sha256"]:
        raise ValueError("backup hash mismatch")
    current = read_limited(path, MAX_SKILL_BYTES)
    if digest(current) == manifest["before_sha256"] and manifest["status"] == "prepared":
        manifest["status"] = "rolled-back"
        write_json(manifest_path, manifest)
        print("No file change had occurred; transaction closed.")
        return 0
    if digest(current) != manifest["after_sha256"]:
        raise ValueError("target changed after apply; refusing to overwrite later edits")
    atomic_write(path, backup, manifest["mode"])
    manifest["status"] = "rolled-back"
    write_json(manifest_path, manifest)
    print(f"Restored: {path}")
    return 0


def validate_skill(path: Path) -> list[str]:
    path = path.expanduser().resolve()
    issues = []
    try:
        raw = read_limited(path, MAX_SKILL_BYTES)
        meta, body, bounds = frontmatter(raw.decode("utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        return [str(exc)]
    if bounds is None:
        issues.append("missing YAML frontmatter")
    name = meta.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64 or name != path.parent.name:
        issues.append("invalid name or folder mismatch")
    if not meta.get("description") or len(meta.get("description", "")) > 1024:
        issues.append("description must contain 1–1024 characters")
    for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", body):
        if "://" not in target and not target.startswith(("#", "/")) and not (path.parent / target).exists():
            issues.append(f"missing local reference: {target}")
    return issues


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("check", "inventory", "audit", "route", "plan", "apply", "rollback", "validate"):
        c = sub.add_parser(name)
        if name in {"check", "inventory", "audit", "route", "plan", "validate"}:
            c.add_argument("--project", default=".")
        if name in {"check", "inventory", "audit", "route"}:
            c.add_argument("--host", choices=["both", "all", "codex", "claude", "workbuddy"], default="both")
            c.add_argument("--no-cache", action="store_true")
            c.add_argument("--json", action="store_true")
        if name == "route":
            c.add_argument("--task", required=True)
        if name == "plan":
            c.add_argument("--skill", required=True)
            c.add_argument("--description", required=True)
            c.add_argument("--out", required=True)
        if name == "apply":
            c.add_argument("--plan", required=True)
        if name == "rollback":
            c.add_argument("--id", required=True)
        if name in {"apply", "rollback"}:
            c.add_argument("--state-dir", default=str(default_state()))
        if name == "validate":
            c.add_argument("--skill")
            c.add_argument("--cases")
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "plan":
        return plan(args)
    if args.command == "apply":
        return apply(args)
    if args.command == "rollback":
        return rollback(args)
    if args.command == "validate":
        if not args.skill and not args.cases:
            raise ValueError("validate needs --skill and/or --cases")
        errors = []
        if args.skill:
            errors += validate_skill(Path(args.skill).expanduser())
        if args.cases:
            cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
            if not isinstance(cases, list):
                raise ValueError("cases must be a JSON list")
            skills, _ = discover(Path(args.project), include_cache=False)
            for index, case in enumerate(cases, 1):
                result = route(skills, case["task"], case.get("host", "both"))
                top = result["matches"][0]["name"] if result["matches"] else None
                if top != case["expected"]:
                    errors.append(f"case {index}: expected {case['expected']!r}, got {top!r}")
        print("Validation passed" if not errors else "Validation failed:\n" + "\n".join(errors))
        return 1 if errors else 0
    skills, warnings = discover(Path(args.project), include_cache=not args.no_cache, host=args.host)
    if args.command == "check":
        result = check_report(skills, warnings)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            summary = result["summary"]
            print(f"Local skill files: {summary['local_files_found']} (Codex {summary['by_host']['codex']}, Claude Code {summary['by_host']['claude']}, WorkBuddy {summary['by_host']['workbuddy']})")
            print(f"Plugin cache entries: {summary['cached_unverified']} (enabled state unverified)")
            print(f"Installation findings: {summary['installation_findings']}; same names: {summary['same_name']}")
            print(f"Possible overlaps: {summary['possible_overlaps']}; possible rule conflicts: {summary['possible_rule_conflicts']}")
            for item in result["installation_findings"][:10]:
                print("  installation: " + json.dumps(item, ensure_ascii=False))
            for item in result["overlaps"][:10]:
                print("  overlap: " + json.dumps(item, ensure_ascii=False))
            for item in result["rule_conflicts"][:10]:
                print("  conflict: " + json.dumps(item, ensure_ascii=False))
            for warning in warnings:
                print("  warning:", warning)
            print(result["note"])
    elif args.command == "inventory":
        result = {"skills": [s.public() for s in skills], "warnings": warnings}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Found {len(skills)} skills ({sum(s.scope == 'cache' for s in skills)} cache, enabled state unknown)")
            for s in skills:
                print(f"{s.host:6} {s.scope:12} {s.invocation:13} {s.name:28} {s.path}")
            for warning in warnings:
                print("Warning:", warning)
    elif args.command == "audit":
        result = audit(skills)
        result["warnings"] = warnings
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"{result['local_files_found']} local skill files; {result['cached_unverified']} cache entries (activation unverified)")
            for kind, key in (("Overlap", "overlaps"), ("Rule conflict", "rule_conflicts"), ("Security signal", "security_signals")):
                print(f"{kind}: {len(result[key])}")
                for item in result[key][:30]:
                    print("  " + json.dumps(item, ensure_ascii=False))
            for warning in warnings:
                print("Warning:", warning)
    else:
        result = route(skills, args.task, args.host)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(result["note"])
            for match in result["matches"]:
                print(f"{match['score']:.3f} {match['host']}:{match['name']} — {match['path']}")
            if result["possible_combination"]:
                print("Possible combination: " + " + ".join(result["possible_combination"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"skill-curator: {exc}", file=sys.stderr)
        sys.exit(2)
