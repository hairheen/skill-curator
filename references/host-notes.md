# Host notes and interpretation

## Codex

Codex discovers repository skills in `.agents/skills` along the working directory's path to the repository root and user skills in `~/.agents/skills`. Existing installations may also use `~/.codex/skills`; the scanner labels this a legacy/local root. `agents/openai.yaml` can set `policy.allow_implicit_invocation: false`. Codex can disable a local skill through `[[skills.config]]` in `~/.codex/config.toml`. The scanner reads the skill files and local invocation metadata; it does not fully resolve every running host setting or plugin enablement state.

## Claude Code

Claude Code discovers personal skills at `~/.claude/skills` and project skills at `.claude/skills`. `disable-model-invocation: true` means user-only invocation; `user-invocable: false` means model-only. User settings can override visibility through `skillOverrides`. Same-name priority, nested project skills, synced skills and plugin namespaces have host-specific behavior. This tool surfaces possible name collisions but does not claim one universal winner.

## WorkBuddy

The scanner checks `~/.workbuddy/skills` and `.workbuddy/skills` along the project path. WorkBuddy may also show skills from its market or other configured locations; finding a file does not establish that it is enabled. Use `--host workbuddy` to focus a report on these local files. WorkBuddy's upload package should place `SKILL.md` at the ZIP root with at most one resource directory below it.

## Reading findings

- `same_name`: direct naming ambiguity, especially across scopes.
- `possible_overlap`: similar advertised capability or triggers. Inspect the full body and actual use cases before consolidation.
- `possible_rule_conflict`: opposite imperative wording about the same action category, with file and line evidence. Context and instruction hierarchy decide whether it is a real conflict.
- `security_signal`: a static pattern worth review, not proof of malicious code.
- `cache`: a file found in a plugin cache. Presence does not prove the plugin is active.

`route` compares wording and capabilities; it cannot reproduce Codex or Claude Code's internal model selection. Validation cases test this diagnostic only. The scanner never executes discovered code or sends its content to a service.
