# 五个开源项目的完整代码审阅与新 Skill 设计

审阅日期：2026-10-25（日本时间）。五个给定的 GitHub API 地址均返回 200；调研时均完整克隆，审阅范围包含提交树中的入口、实现、配置、测试与 `SKILL.md`，不限于 README。五份仓库根目录都有 MIT `LICENSE`。下表的“最近代码提交”取本地 `git log -1`，不把 GitHub `updated_at` 当作代码维护日期。未发现许可证不兼容；新项目仍独立实现，没有复制上游代码。

| 仓库 / 固定快照 | 跟踪文件 | 最近代码提交 | 运行时与定位 |
| --- | ---: | --- | --- |
| [skill-audit](https://github.com/scottholdren/skill-audit/tree/2a2a9304bf0608a705b18f393100720c7fe0b265) | 7 | 2026-04-24 | Python 标准库；Claude Code 审计指令 + 清单脚本 |
| [skill-issue](https://github.com/mishanefedov/skill-issue/tree/949282fa8cfa22283806057f0277b01698839836) | 57 | 2026-06-02 | Bun/TypeScript，已提交 Node 可运行构建包；触发质量检测 CLI |
| [skills-mgr](https://github.com/yusing/skills-mgr/tree/521cd4c12e1d0cfa704973b1890f93a279a4f469) | 90 | 2026-10-14 | Go 1.26；跨 Codex/Claude/Grok 的安装与选择管理器 |
| [agentic-skill-router](https://github.com/legendtkl/agentic-skill-router/tree/160b30f0b67c923077f886376fdfae1016a70702) | 585（含大量实验产物） | 2026-06-04 | Node 20+/TypeScript；禁用 Skill 的路由与恢复 |
| [smart-skill-router](https://github.com/chenyueve-alt/smart-skill-router/tree/66594e844c1a9563458b2c6fd75ec265a424e825) | 10 | 2026-08-14 | 纯 `SKILL.md` 决策策略，无执行程序 |

这些日期只能说明仓库提交节奏，不足以断言项目已停更；`skills-mgr` 在本次快照中最近有代码提交，其余四者最近提交较早。仓库均未归档。许可证见各仓库的 [`LICENSE`](https://github.com/scottholdren/skill-audit/blob/2a2a9304bf0608a705b18f393100720c7fe0b265/LICENSE)、[`LICENSE`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/LICENSE)、[`LICENSE`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/LICENSE)、[`LICENSE`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/LICENSE)、[`LICENSE`](https://github.com/chenyueve-alt/smart-skill-router/blob/66594e844c1a9563458b2c6fd75ec265a424e825/LICENSE)。

## 逐仓库审阅

### skill-audit

- **目录与入口：** 根目录 [`SKILL.md`](https://github.com/scottholdren/skill-audit/blob/2a2a9304bf0608a705b18f393100720c7fe0b265/SKILL.md) 调用 [`scripts/scan_skills.py`](https://github.com/scottholdren/skill-audit/blob/2a2a9304bf0608a705b18f393100720c7fe0b265/scripts/scan_skills.py)。没有第三方依赖、配置文件或自动测试。
- **实现：** 扫描 Claude 个人/项目/备用目录及插件缓存；只解析 frontmatter 中的名称和描述，输出清单。触发重叠、正文规则冲突和冗余由模型根据清单继续判断；脚本没有读取正文来自动验证冲突。`classify_invocation()` 靠描述里的 “automatically/proactively” 字样推断自动调用，而 Claude 官方文档说明默认模型可调用，`disable-model-invocation` 才是明确开关。因此它的 `auto/explicit` 分类不能视为宿主真实状态。
- **风险/状态：** 脚本本身只读且离线。插件缓存中的旧版本可能被当作已安装项；内建 Skill 名单为静态表，易随宿主版本变化。最后提交为社交预览素材，缺少测试覆盖。

### skill-issue

- **目录与入口：** [`src/cli.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/cli.ts) 和 [`dist/skill-issue.mjs`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/dist/skill-issue.mjs)；封装 Skill 在 [`skills/skill-issue/SKILL.md`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/skills/skill-issue/SKILL.md)。依赖与脚本见 [`package.json`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/package.json)；`test/` 有多组 Bun 单测。
- **实现：** [`discover.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/discover.ts) 有深度限制并按名称去重，适合简化路由，但会遮蔽同名来源。[`lint.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/lint.ts) 检查描述空缺、重复、模糊及触发短语；[`collisions.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/collisions.ts) 先去高频词，再用特征词 Jaccard 聚类；[`simulate.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/simulate.ts) 用稀有词加权评分。`--llm` 可经本机 `claude`/`codex` CLI 判别。主要分析的是激活元数据，未检测正文规则冲突。
- **风险/状态：** [`fix.ts`](https://github.com/mishanefedov/skill-issue/blob/949282fa8cfa22283806057f0277b01698839836/src/fix.ts) 的 `--fix` 直接覆写描述，未见内建备份、差异预览或文件变化校验；符号链接由 `statSync` 跟随。README 还给出远程脚本管道安装命令；使用前应读安装脚本。最后提交是文档/安装说明，测试存在但本机无 Bun。

### skills-mgr

- **目录与入口：** Go [`main.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/main.go)、[`tui.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/tui.go)；不是单独的 Agent Skill，仓库没有 `SKILL.md`。[`go.mod`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/go.mod) 需要 Go 1.26，并引入 Bubble Tea、go-git、YAML/TOML 和 shell 解析库。
- **实现：** [`skill_discovery.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/skill_discovery.go) 分源发现和排序；[`agent_inspect.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/agent_inspect.go) 展示所有权、启用选择、哈希、正文及 references 健康；[`skill_frontmatter.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/skill_frontmatter.go) 用 YAML AST 做较精确的字段编辑。远程内容与本地补丁分层，见 [`remote_patch.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/remote_patch.go)。`README` 介绍选择文件的全局/项目层、条件启用与 CLI。没有语义路由或跨 Skill 正文冲突检测。
- **风险/状态：** [`README` 的条件表达式说明](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/README.md#conditional-expressions) 明言 `enabled` 字符串会以用户权限运行 Bash；[`skill_context.go`](https://github.com/yusing/skills-mgr/blob/521cd4c12e1d0cfa704973b1890f93a279a4f469/skill_context.go) 的 `run` 也会执行 Skill 脚本，不能对不可信项目直接运行。代码含路径校验、变更回滚与大量回归测试；本机无 Go，未运行其测试。

### agentic-skill-router

- **目录与入口：** [`src/cli.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/cli.ts)、[`bin/agentic-skill-router`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/bin/agentic-skill-router)、[`skills/agentic-skill-router/SKILL.md`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/skills/agentic-skill-router/SKILL.md)；`src/hosts/` 适配 Codex/Claude，`src/commands/` 含 list/suggest/route/status/apply/web。`package.json` 的开发依赖为 TypeScript、tsx、esbuild；`tests/` 和 `experiments/` 很丰富。
- **实现：** [`scan.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/scan.ts) 处理内建、插件及符号链接；[`route.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/route.ts) 明确只路由已禁用的 Skill；[`auto-route.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/auto-route.ts) 先用元数据，证据不足再升级到 [`dci.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/dci.ts) 的正文检索。`suggest` 根据使用记录和规则推荐瘦身。未见跨 Skill 的命令式规则冲突分析。
- **风险/状态：** [`apply.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/apply.ts) 通过重命名 `SKILL.md` 禁用，写入状态日志并校验部分符号链接边界；[`status.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/commands/status.ts) 可重应用缺失的禁用状态，因而不能一概视为纯只读。Web UI 默认绑定回环地址，公开绑定需要显式危险标志、认证和来源检查，见 [`web.ts`](https://github.com/legendtkl/agentic-skill-router/blob/160b30f0b67c923077f886376fdfae1016a70702/src/commands/web.ts)。禁用/恢复是真实文件操作，需留意外部同步或插件升级。

### smart-skill-router

- **目录与入口：** 根目录 [`SKILL.md`](https://github.com/chenyueve-alt/smart-skill-router/blob/66594e844c1a9563458b2c6fd75ec265a424e825/SKILL.md)、[`agents/openai.yaml`](https://github.com/chenyueve-alt/smart-skill-router/blob/66594e844c1a9563458b2c6fd75ec265a424e825/agents/openai.yaml)、例子及 AGENTS.md；无程序、依赖或自动测试。
- **实现：** 让模型按目标、能力、权限与复杂度选用最小 Skill 组合；不维护索引，不提供可复现的检测分数，也不修改安装状态。通用触发描述宽，可能和领域 Skill 争夺初始上下文，但实际加载仍由宿主决定。
- **风险/状态：** 无直接代码执行面；能力和冲突判断全由当前模型推断。跨宿主的实际安装路径、覆盖规则由各宿主决定，不能仅靠“通用原则”确保一致。

## 功能对比与可复用机制

| 能力 | skill-audit | skill-issue | skills-mgr | agentic-skill-router | smart-skill-router | 新 Skill Curator |
| --- | --- | --- | --- | --- | --- | --- |
| 本地盘点 | Claude 路径 | 给定目录 | 多宿主/远程 | Codex + Claude | 模型自行看清单 | Codex + Claude，本地/缓存区分 |
| 触发/路由 | 模型判断 | 词面模拟 | 启用选择 | 已禁用项检索 | 模型策略 | 词面建议与组合提示 |
| 功能重叠 | 模型判断 | 特征词聚类 | 无 | 无 | 模型判断 | 名称/描述证据 |
| 正文规则冲突 | 模型判断，脚本未读正文 | 无 | 无 | 无 | 让模型解决 | 双方原文与行号，标为可能冲突 |
| 修改/回滚 | 无 | 直接改描述 | 选择/远程补丁 | 禁用状态日志恢复 | 无 | 差异预览、哈希、字节备份、回滚 |
| 执行发现的代码 | 否 | 可选本机模型调用 | `run` 可执行 | 本地 CLI/UI 操作 | 由模型决定 | 否 |

值得吸收的是：多来源发现和所有权标记、先去通用词再找重叠、将词面路由声明为启发式、对变更使用状态记录及路径校验。新实现重新编写这些机制，不使用任何上游源码。现有工具的共同缺口是将“描述相似”“真实功能重复”和“有条件的正文规则冲突”严格区分，并在修改前给出可复核证据及可验证回滚。

## 新 Skill 的取舍、格式和验证

[`skill-curator`](../) 是标准 `SKILL.md` 包：Codex 的 `agents/openai.yaml` 是可选 UI 元数据；Claude Code 忽略它但读取同一个 `SKILL.md`。本地技能位置与控制字段依据 [Codex 官方说明](https://learn.chatgpt.com/docs/build-skills)、[Claude Code 官方说明](https://code.claude.com/docs/en/skills) 和 [Agent Skills 规范](https://agentskills.io/specification)。它只修改用户自有目录下单个 Skill 的顶层描述，不自动删除、禁用或执行其它 Skills。`inventory`、`audit`、`route`、`validate` 离线只读；`plan` 写计划文件，`apply` 与 `rollback` 需显式命令。插件缓存只作未知启用状态的观察对象。

Python 标准库实现降低安装门槛，但前置 YAML 读取器只覆盖常见格式；词面检测不等于语义理解，复杂条件和宿主真实调用仍需人工/宿主内验证。相反地，字节备份、哈希校验与原子替换是确定性实现，能实测恢复原文。测试包括多宿主发现/缓存/符号链接、重叠与相反规则、静态不执行、预览不改原文、过期计划拒绝、应用后编辑拒绝回滚、原文恢复、路由与坏引用诊断。完整命令见 [`README.md`](../README.md)。

本机未安装 Bun 或 Go，故未运行 `skill-issue` 和 `skills-mgr` 上游完整测试；`agentic-skill-router` 的 TypeScript 开发依赖也未安装，未把其测试通过作为结论。已抽样运行 `skill-audit` 的 Python 扫描器（输出 53 个条目，却全部归为 `explicit-call`，佐证其启用模式误判风险）以及 `skill-issue` 已提交的 Node 构建包（在仓库 collision fixture 中识别 `code-review`/`pr-audit`）。新 Skill 的 Python 单元测试为 5/5 通过，`skill-creator` 的 `quick_validate.py` 亦通过。作为实际目录冒烟检查，扫描器发现 49 个本地条目和 87 个缓存条目；去除缓存后输出 5 条可能重叠、0 条满足严格静态规则的冲突。5 条重叠来自两对近似描述在 Codex 和 Claude 各出现一次，以及 Codex 目录里同名的 `web-access`；它们只是复核线索，不代表应该删除。
