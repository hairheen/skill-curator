# Skill Curator

<img src="assets/logo.png" alt="Skill Curator logo" width="160">

一个离线 Agent Skill，用于盘点本机 Codex、Claude Code 与 WorkBuddy 的 Skills，发现可能重复的能力、触发词重叠和相反的正文指令，并在审阅差异后安全修改 `description`。Python 3.10+，运行时只用标准库。

它提供四个主要能力：

1. **盘点**：按宿主和来源列出本地 Skills，单独标记启用状态未知的插件缓存。
2. **分析**：从名称、描述和正文提取能力、可能重叠及规则冲突，给出原文与行号供复核。
3. **选择**：针对具体任务给出词面匹配结果和可能的 Skill 组合。
4. **安全修改**：先看描述改动的差异，再应用；保留原始字节并支持有条件回滚。

本项目的出发点、五个参考项目的完整代码审阅及设计取舍见[研究报告](docs/research.md)。

## 最简单的用法

安装后，直接在 Codex、Claude Code 或 WorkBuddy 对话里说：

> 帮我检查一下 Skill 的安装，看看有没有重复或冲突。

也可以说“盘点一下我装的 Skills”“这些 Skills 有没有打架”“这个任务该用哪个 Skill”。AI 会运行只读检查并用普通话总结；你不需要记住下面的命令。如果它没有自动选中本 Skill，在 Codex 中说“用 `$skill-curator` 帮我检查”，在 Claude Code 中输入 `/skill-curator`。新安装后若当前对话没发现它，开始一段新对话再试。

## 安装

将整个 `skill-curator` 文件夹复制到以下任一位置，再让对应宿主重新发现 Skills：

| 宿主 | 个人安装 | 项目安装 |
| --- | --- | --- |
| Codex | `~/.agents/skills/skill-curator` | `<project>/.agents/skills/skill-curator` |
| Claude Code | `~/.claude/skills/skill-curator` | `<project>/.claude/skills/skill-curator` |
| WorkBuddy | `~/.workbuddy/skills/skill-curator` | `<project>/.workbuddy/skills/skill-curator` |

WorkBuddy 的上传界面请使用专用的 [skill-curator-workbuddy.zip](dist/skill-curator-workbuddy.zip)。该包的 ZIP 根目录直接放 `SKILL.md`，只包含运行所需的 `scripts/` 与 `references/`，符合其目录层级限制。导入后可直接说“帮我检查一下 Skill 的安装”。修改源码后运行 `python3 build_workbuddy_zip.py` 可重新生成上传包。

从 GitHub 安装到个人目录时，选择与你使用的宿主对应的一条命令：

```bash
git clone https://github.com/hairheen/skill-curator.git ~/.agents/skills/skill-curator
# 或：Claude Code
git clone https://github.com/hairheen/skill-curator.git ~/.claude/skills/skill-curator
```

Codex 中可显式调用 `$skill-curator`；Claude Code 中可调用 `/skill-curator`。也可以直接运行 `scripts/skill_curator.py`。安装本 Skill 不会自动修改其他 Skill 或宿主配置。

## 常用命令

以下命令中的路径都以项目根目录为例；先把 `SC` 设为本 Skill 的脚本绝对路径。

```bash
SC=/path/to/skill-curator/scripts/skill_curator.py
python3 "$SC" inventory --project /path/to/project
python3 "$SC" audit --project /path/to/project
python3 "$SC" check --project /path/to/project
python3 "$SC" route --task "整理销售数据并做图表" --host codex --project /path/to/project
python3 "$SC" validate --skill /path/to/skill-curator/SKILL.md
```

每条只读命令可按需使用 `--json`；`check`、`inventory`、`audit` 和 `route` 支持 `--host codex|claude|workbuddy|both`、`--no-cache`。缓存项默认会列出，但标记为启用状态未知，路由时不作为候选。

## 预览、应用与回滚

```bash
python3 "$SC" plan --project /path/to/project \
  --skill /path/to/project/.agents/skills/example/SKILL.md \
  --description "Create PDF reports. Use when exporting a report to PDF." \
  --out /path/to/proposal.json
python3 "$SC" apply --plan /path/to/proposal.json
python3 "$SC" rollback --id <apply 输出的 ID>
```

`plan` 显示统一差异并保存含原文件哈希的计划，不修改原文件。`apply` 重新核对哈希、保存原始字节和模式，再原子替换文件；默认交易目录是 `~/.skill-curator/transactions`。`rollback` 只有在目标仍等于本次应用结果时才恢复，不覆盖之后的新修改。测试或定制时，`apply` 和 `rollback` 都可传 `--state-dir`。

仅允许修改发现到的本地或项目 `SKILL.md`；插件缓存、符号链接、系统文件会拒绝。改写只涉及顶层 `description`，不运行任何被扫描 Skill 的脚本。

## 路由样例验证

创建一个 JSON 文件：

```json
[
  {"task": "Create a PDF report", "expected": "pdf-maker", "host": "codex"}
]
```

运行 `python3 "$SC" validate --cases /path/to/cases.json --project /path/to/project`。这是离线词面诊断，不能保证实际模型的 Skill 调用结果。

## 范围与限制

- 扫描标准个人和项目目录，以及可选的插件缓存；无法单凭缓存判断插件是否启用，也无法读取宿主内置或云端同步但未落盘的 Skills。
- 分析能力依据 `name` 与 `description`；规则冲突依据正文中的显式命令句，二者都属于待人工复核的线索。
- 内置 frontmatter 读取器覆盖常见顶层标量和折叠描述，不是完整 YAML 解析器。复杂 YAML、宿主设置覆盖与实际模型路由需在宿主中复核。
- 安全提示是静态特征匹配，不能替代代码审计。读取被扫描文件时不执行脚本、不联网。
- 修改同机本地文件时使用哈希检查和原子替换；恶意并发进程在检查与替换之间换目录的极端竞态不能完全由路径级 Python API 排除。

## 测试

```bash
python3 -m unittest discover -s tests -v
python3 scripts/skill_curator.py validate --skill SKILL.md
```

核心格式遵循 [Agent Skills 规范](https://agentskills.io/specification)；各宿主的目录和调用行为以其官方文档为准。[WorkBuddy 开放平台的技能结构说明](https://open.workbuddy.cn/docs/skill)包含上传包的资源目录要求。

## License

MIT。实现为独立编写；参考项目的代码未复制到本仓库。
