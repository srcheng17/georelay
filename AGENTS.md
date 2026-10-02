<!-- TRELLIS:START -->
# Trellis Instructions

These instructions are for AI assistants working in this project.

This project is managed by Trellis. The working knowledge you need lives under `.trellis/`:

- `.trellis/workflow.md` — development phases, when to create tasks, skill routing
- `.trellis/spec/` — package- and layer-scoped coding guidelines (read before writing code in a given layer)
- `.trellis/workspace/` — per-developer journals and session traces
- `.trellis/tasks/` — active and archived tasks (PRDs, research, jsonl context)

If a Trellis command is available on your platform (e.g. `/trellis:finish-work`, `/trellis:continue`), prefer it over manual steps. Not every platform exposes every command.

If you're using Codex or another agent-capable tool, additional project-scoped helpers may live in:
- `.agents/skills/` — reusable Trellis skills
- `.codex/agents/` — optional custom subagents

Managed by Trellis. Edits outside this block are preserved; edits inside may be overwritten by a future `trellis update`.

<!-- TRELLIS:END -->

## Git 与 Pull Request 规则

- 默认在独立任务分支开发；push 或创建、更新 PR 后，报告分支、PR 和验证结果，等待用户审阅。
- 只有用户明确要求合并当前 PR 或分支时，才能将任务改动合入 `main`。未经授权，不得执行 PR merge、启用 auto-merge，或通过 squash、rebase、cherry-pick、直接 push `main` 绕过这一要求。
- “继续”“push”“提交”“完成任务”和 CI 通过均不构成合并授权；之前对其他改动的合并授权不延用于当前改动。
