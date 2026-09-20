# Minecraft 开发 Skill / Agent 分享包

本包汇总当前项目与当前 Windows 用户下直接面向 Minecraft Bedrock / 网易版开发的 Codex skills 和 AGENTS 规则，适合分享给其他开发者使用。

## 内容

- `skills/auto-fill-mob-move-config`：从动画、状态类、位移曲线、命中盒与 VFX 时序生成或审计生物招式配置。
- `skills/bedrock-animation-authoring`：编写和审查 Bedrock/网易版 geometry、actor animation、动画控制器、骨骼、locator 与时间轴。
- `skills/molang-animation-authoring`：编写和审查动画、控制器、渲染资源及自定义查询中的 Molang。
- `skills/swordsoul-mob-fight`：SwordSoul 战斗脚本、生物状态机、渲染、特效、材质及网易 ModAPI 集成工作流。
- `skills/swordsoul-ui-authoring`：SwordSoul/QingYunModLibs UI JSON、Python UI、生命周期、布局、动画、滚动与跨平台适配。
- `skills/recover-netease-mc-resources`：仅对自有或获授权的网易本地资源/行为包进行安全检查、恢复与整理。
- `agents/global-minecraft.AGENTS.md`：适用于所有项目的 Minecraft API 文档核验规则（同时保留原文件中的全局安全规则）。
- `agents/swordsoul-project.AGENTS.md`：本项目的生物战斗部署、UI、生命周期与验证基线。

每个 skill 均按原目录完整打包，包含其 `SKILL.md` 及原有的 scripts、references、assets、agents 等配套内容。

## 安装

1. 将需要的技能目录复制到目标用户的 `~/.codex/skills/`；也可以复制到某个项目的 `.codex/skills/`，作为项目专用技能。
2. 将 `agents/global-minecraft.AGENTS.md` 中适合团队的规则合并进目标用户的 `~/.codex/AGENTS.md`。不要直接覆盖对方已有全局规则。
3. 将 `agents/swordsoul-project.AGENTS.md` 放到 SwordSoul 项目根目录并命名为 `AGENTS.md`；用于其他项目时，应先删改其中仅适用于 SwordSoul 的路径和约束。
4. 重启或重新打开 Codex 会话，使技能目录与 AGENTS 规则重新载入。

## 使用边界

- `recover-netease-mc-resources` 只允许处理本人拥有或明确获授权的资源，不得用于获取账号凭据、令牌或第三方市场内容。
- 项目技能包含 SwordSoul 专用路径、命名及运行时约束；移植到其他工程前应按实际目录和框架调整。
- 本包不包含项目源码、游戏资源、账户信息、Codex 缓存或临时插件。

## 完整性

根目录的 `SHA256SUMS.txt` 记录包内所有分发文件的 SHA-256，可用于解压后的完整性核验。

