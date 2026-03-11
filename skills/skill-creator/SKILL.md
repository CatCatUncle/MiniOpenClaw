# skill-creator
用于在 MiniOpenClaw 项目里创建、更新、验证本地技能（SKILL.md）。

## Trigger
- skill-creator
- 创建技能
- 新建 skill
- skill scaffold

## Workflow
1. 明确技能名称、触发场景、输出风格。
2. 使用 `/skills create <name> [description]` 生成脚手架。
3. 补充 `SKILL.md` 的 Trigger / Goals / Output Style。
4. 用 `/skills refresh` 与 `/skills match <text>` 验证触发效果。

## Rules
- 名称使用小写连字符风格（例如 `telegram-integration`）。
- SKILL.md 只写必要规则，不堆无关说明。
- 如需可执行逻辑，放到 `scripts/`，保持幂等和可重复执行。

## Output Style
- 先给结果，再给步骤。
- 给出可直接运行的命令。
