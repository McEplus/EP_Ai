---
name: swordsoul-mob-fight
description: Use when working in SwordSoul_NewERA_Fight on SwordSoulFightScripts (player combat system scripts, SWS), SwordSoulMobFightScripts, mob combat state machines, SWS combat state reuse, entity static render resources, forward skill VFX, skeletal lightning, shaders/materials, Molang, or NetEase Minecraft ModAPI behavior/render integration.
---

# SwordSoul Mob Fight

## Global Context

- Before editing any code in this project, read this `SKILL.md` completely in the current turn. Do not rely on memory from a previous turn.
- Communication language rule: 与用户的所有对话回复必须使用中文。
- Codex planning rule: before writing any feature code, first make a plan and summarize it for user review. If the user gives a full ordered task queue in one request, plan the queue, then execute it directly; after completion, summarize both the original plan and the real changes for later review.
- Tool failure recovery rule: do not switch tools or approaches after the first decode, stream, parser, response-format, or similar recoverable error. Preserve the exact error, reduce and isolate the failing input, inspect encoding/format/parameters/environment, retry the original path, and exhaust its supported endpoints or variants. Use a fallback only after all reasonable repair and retry options for the original approach have failed; report the attempts, remaining cause, and fallback explicitly.
- Codex annotation rule: mark changed or newly added business logic with short comments so the user can quickly identify what Codex touched and why.
- FunctionSystem rule: when working on SWS `SwordSoulFightScripts/FunctionSystem`, use `.codex/agents/sws/function-system/sws-function-system-agent.md` as the local agent rule. Without explicit user permission, do not edit sibling files outside the requested FunctionSystem business file; only `FunctionSystem/Server.py` may be touched when necessary.
- In this project, `SwordSoulFightScripts` means the player combat system scripts and is abbreviated as `SWS` in all future work.
- Directional skeletal lightning rule: for mesh/shader lightning, time-stop lightning, glass-refraction overlap, stencil masking, or `CreateSuperEffect` lightning tasks, read [lightning-vfx.md](references/lightning-vfx.md) before planning and route implementation through `.codex/agents/project/render/lightning-effect-agent.md`.
- SWS-first rule: Mob combat must reuse SWS existing attack hitbox, movement, effects, super-armor clash, defense/dodge/attack-clash/step judgment, and other combat mechanisms whenever possible. Mob-side code should only provide per-entity runtime ownership, command translation, rendering bridge, and the minimum server adapter needed where SWS player/client callbacks cannot directly target mobs.
- Mob state authoring must keep SWS naming and parameter order by default. `MobFightStateSystem.BindState(stateId, weaponType="", StateCls=None)` follows SWS; Mob-specific `entityType` is an explicit extension, not the normal second positional argument.
- Downward aerial attack landing rule: any move that drives an entity downward from air toward the ground, including aerial charged attacks, dive attacks, and slam/down-split states, must reset or neutralize residual motion at the exact landing event moment, not before the scripted downward motion. This must be guarded by a per-state landing window that opens only during the move's intended downward/slam phase; after landing, any later scheduled move timers for the same slam must be skipped so they do not create ground sliding. For slam vectors with both vertical and horizontal components, such as `(0, -1, 0.5)`, preserve the local vector ratio when adapting SWS motion to mobs; do not treat the horizontal component as full `power`. The landing hook should re-check `query.is_on_ground`; motion reset happens immediately, while visual landing effects may use a tiny one-shot delay to avoid server/client visual mismatch. If delayed, landing effects must use an independent one-shot `CreateTimer`, not `StateAnim_CreateTimer`, because state timers may be cleared before the effect fires. Do not let the whole state duration consume landing, and do not add Tick polling for this. Use the existing landing event hook (`OnGroundServerEvent` / state `CheckFall`).
- SWS-style landing authoring rule: mob downward/slam states must define their own `CheckFall(args)` body and register/unregister it in that state, mirroring SWS state classes. The server event is `OnGroundServerEvent`; use `ListenServerEvents(ServerEvents.EntityEvents.OnGroundServerEvent, self.CheckFall)` in the state's `onStart`, and `UnListenServer(...)` in `CheckFall` success and `onEnd`. Do not route attack landing through a controller-level `RunningStateObj.CheckFall` dispatcher, and do not hide landing behavior in shared handlers such as `CheckDownAttackFall` or `onDownAttackFall`; the state itself should contain the id guard, per-state window guard, motion reset, effects, sounds, and any block/camera side effects so data authors can customize each move in place.
- Do not sync changes into `.build/dist`. Only edit source under `src/`; never copy edited `.py`/`.json` into `.build/dist`, and do not manage (delete/regenerate) `.pyc` there. The user owns build/dist synchronization (MC Studio rebuild / in-game hot-reload handles src->dist copy and Netease `.pyc` compilation). Only touch `.build/dist` when the user explicitly requests it.
- Game reload safety rule: do not call game reload/restart tools such as `reload_game` unless the user explicitly asks for reload, restart, or hot reload in the current request. Code edits, resource edits, or successful verification are not permission to reload the game. If a reload would be useful, mention it in the final response instead of doing it.
- Encoding safety rule: many project Python files contain UTF-8 Chinese comments/strings. Do not round-trip them through PowerShell `Get-Content`/`Set-Content` default encoding, `[Text.Encoding]::Default`, ANSI, GBK, or BOM-writing UTF-8. This causes mojibake such as `鎴樻枟`, `鐢熺墿`, or a `﻿# coding=utf-8` header. For manual edits use `apply_patch`; for bulk ASCII-only rewrites use byte-preserving replacement or explicitly UTF-8 without BOM, then inspect `git diff` to verify that only intended code changed and no Chinese comments/strings or file headers changed.
- File reading rule: All project `.py`/`.md` files are UTF-8 (no BOM). To inspect Chinese, read via a UTF-8 path — Python `open(p, encoding="utf-8")` with `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")`, or a UTF-8 editor. Never use PowerShell `Get-Content`/`cat`/`type` to read Chinese: the cp936 console renders valid UTF-8 Chinese as mojibake (e.g. `核心规则` shows as `鏍稿績瑙勫垯`), which is a DISPLAY artifact, not file corruption. Do not "fix" display-only mojibake by re-saving — that is what permanently corrupts files. To test for real corruption, decode bytes strictly as UTF-8 and search for mojibake marker chars `閹閻鏋锘縛鎴樻枟鐘舵€佹満`; a clean file has none (this SKILL.md is the only intentional exception, where such chars appear as examples).
- Mojibake recovery rule: If a file is genuinely corrupted (UTF-8 misread as cp936 then re-saved), do not guess the text. It may be a double round-trip with .NET cp936 PUA mappings that Python `gbk`/`gb18030` cannot reverse; recover with the SAME codec that caused it — .NET `[Text.Encoding]::GetEncoding(936)`: read bytes as UTF-8 -> mojibake string -> `cp936.GetBytes()` -> UTF-8 decode, repeated until readable (usually 2x). Bytes lost to `?`/`U+FFFD` during the original decode are irrecoverable; re-author those few chars from code context. Always verify only the intended comment lines changed (code byte-identical) and `python -m py_compile` passes.


## SWS Move Config Migration To Mob

- Treat SWS as the source of truth for move parameters. When the user asks to copy SWS move config, copy the exact per-state values from the correct SWS source class; do not merge four directions into one `direction`/`motionList` abstraction, do not introduce conditional shortcuts such as `direction[2]`, and do not normalize timing/power values unless the user explicitly asks for adaptation.
- Identify the correct SWS source file before copying. Empty weapon attacks and defenses are in `SwordSoulFightScripts/FightSystem/UseEmptyState.py`; shared dodge, budge, second jump, hit, step, and hock-rope states are in `SwordSoulFightScripts/FightSystem/CommonState.py`; other weapons use their own `UseXxxState.py`.
- Mob-side state libraries such as `SwordSoulMobFightScripts/Entities/FightState/UseEmptyState.py` must contain plain reusable classes such as `EmptyAttackFirst` or `EmptyBudgeBack`. Never copy SWS decorators into these libraries: remove `@FightStateSystem.BindState`, `@FightStateSystem.BindSkillState`, `@Screen...`, and any other SWS/client registration decorators. Entity binding belongs in entity modules via `@BindMobState`.
- Keep Mob class names and base init correct: convert SWS class names to the local Mob wrapper names (`AttackFirst` -> `EmptyAttackFirst`, `BudgeBack` -> `EmptyBudgeBack`) and every `BaseFightState` subclass must call `BaseFightState.__init__(self)` before setting fields.
- Do not copy SWS client-only globals or post-process registration blocks into server Mob state files. Red flags include `Screen`, `PostProcessComp`, `ClientApi`, `ListenClientEvents`, `UnListenClient`, and standalone SWS skill classes without the `Empty` prefix.
- Convert only the minimum runtime adapter points. For landing states, replace player client event hooks with the existing Mob server landing mechanism (`SetCheckFall(True/False)` or the project-approved `OnGroundServerEvent` pattern), while preserving SWS timing, attack data, and motion values.
- For SWS visual methods already reached through a Mob `CallAllClient` bridge, execute the same SWS public method instead of copying its `CreateSuperEffect`, expression, material, or post-process arguments into Mob code. Add an optional local-only switch to the SWS method with the original all-client behavior as its default, pass local-only from the Mob client, temporarily enable SWS foreign-entity effect creation, and restore that global flag in `finally`; this prevents both visual drift and client-count-squared rebroadcast. For empty-hand punch effects, run `scripts/test_mob_punch_effect_sync.py` after changes.
- Module-level Mob state helpers invoked later by `StateAnim_CreateTimer` must use their explicit state argument (`StateObj.GetComponent`, `StateObj.playerId`) for entity-bound work. Never read module-global `GetComponent` or `playerId` there: `_sync_sws_globals` is shared by all instances from that state module, so another Mob can overwrite those globals before the timer fires. For entity-bound render events, normalize the server payload to the current state entity and let the client event envelope's `entityId` override any nested stale entity argument.
- For world-space movement trails sampled from bones, treat an exact `(0, 0, 0)` engine result as an unready sentinel rather than a valid sample. Try the entity foot position as fallback; if that is also all-zero, skip emission for that tick and do not update the previous valid position. This prevents Sprint/Dodge dirt-smoke interpolation from drawing a path between the entity and world origin. Run `scripts/test_dirt_smoke_zero_position_guard.py` after changing this trail path.
- When syncing a recent SWS effect change across several weapons, inventory both the shared effect implementation and every current SWS state call; client support alone is incomplete. Keep exact per-weapon/per-state timings and arguments in `Combat/SWSRecentEffectSchedule.py`, merge the `common` group with the active Mob weapon at state start, inject the current Mob id at runtime, and stop persistent emitters on state exit. Do not invent entries for an SWS weapon that has no Mob state library/binding. Run `scripts/test_recent_sws_effect_sync.py`, which must compare the schedule directly with current SWS AST and reject duplicate calls in Mob state files.
- Do not duplicate states. Before and after migration, search for both raw SWS names and Mob wrapper names, for example `class AcutePerception` versus `class EmptyAcutePerception`, and remove any copied raw SWS class/decorator block that would coexist with the Mob wrapper.
- After migration, verify with targeted searches: `rg "FightStateSystem\.Bind|@Screen|ListenClientEvents|UnListenClient|direction\[2\]|restDirection" <mob_state_file>` should return no unintended matches, then run `python -m py_compile` on the edited Mob state files and entity modules.

## 根位移到实体位移硬门

- 把 `root_move.position` 视为累计模型空间动画数据，不是实体物理位移，也不是 `SetMotion` 的 `power`。先确认目标模型/导出器的单位比例、轴映射、`anim_time_update` 与 root 所有权；标准 Bedrock/Blockbench 模型通常按 `16 模型单位 = 1 格`，但不得跳过目标资源核验。
- 网易 `SetMotion` 设置的是瞬时移动向量，后续会受摩擦、碰撞、台阶和计时器调度影响。禁止把 `power * 秒数` 报告成游戏实际格数；这只能作为明确标注的配置对齐量。
- `motion_scale≈0.00527` 只属于监守者/铁傀儡已经实机标定的分段瞬时速度，禁止复制给其他生物，也禁止用它解释 BB 中移动了多少格。
- 用户指定现有生物作为位移写法基线时，把该生物当前源码结构视为格式权威；语义等价不代表格式合格，禁止自行替换成 helper、运动表、循环、Mixin 或运行时播放器。
- 用户指定铁傀儡格式时，严格使用 `SetMoveMotion = self.PlayerRootController.SetMoveMotion`、首段直接 `SetMoveMotion(...)`、后续逐条 `StateAnim_CreateTimer(...)`、每段功率乘 `self.State_MotionPower`、状态末尾显式清零；目标实体内禁止 `ScheduleRootMotionTicks`。20Hz 补样只能产生待展开的数据行，不能改变这套代码结构。
- 静态验收必须分别报告：BB/actor 净模型位移、换算目标格数、服务器时间片求和、轴方向、终止清零和位移模式。只有空旷平地网易客户端测试才能确认实际身位；墙体或实体碰撞导致的缩短不算换算误差。
- 出现“BB 移动很多、游戏只走一点”时，依次检查单位比例、时钟映射、一次性 `SetMotion` 的阻力衰减、`State_MotionPower`、原生 AI/碰撞和终止计时器；禁止先盲乘倍率。详细数学与检查项见 [招式参数关系模型](../auto-fill-mob-move-config/references/parameter-model.md)。

## Vanilla Mob Combat Deployment Standard

When the user asks to deploy any vanilla/NetEase mob into `SwordSoulMobFightScripts`, this workflow is mandatory even when the new mob shares another mob's SWS move configuration:

1. Locate and read the active game-version originals before editing: behavior entity JSON/JSONC, client entity, geometry, actor animations, animation controllers, and render controllers. Prefer the user's installed NetEase game files for exact runtime data; use Mojang samples only as supporting evidence. If the active originals cannot be found, report the missing source instead of guessing components, controller keys, or conditions.
2. Resolve the complete vanilla chain: component groups/events and mutually exclusive modes; client `geometry`/texture/material/render controller; every registered animation/controller short name; every active `scripts.animate` entry and its original Molang condition; controller states and the short names they consume. Distinguish the active client entity variant from legacy version files.
3. Give every deployed mob its own entity Python module and its own static render config class/registry alias, even when it inherits another mob's combat states. Shared SWS state reuse must not imply shared vanilla components, geometry, animation-controller inventory, or render conditions.
   Entity-state bindings must follow the Husk module pattern: reuse an existing registered state chain, or import the shared `UseXxxState` library and bind thin subclasses in the entity module when the mob needs its own state whitelist. Do not create a mob-named state library, per-mob timer-scaling mixin, or copied state implementation. Declare numeric species differences through the common entity configuration fields (`BaseKeepArmor`, `StateArmorProfileMap`, `StateArmorOverrideMap`); when an authored actor animation has a different source duration, normalize it resource-side with `anim_time_update` against the shared state duration.
4. Define `query.mod.fight` for the entire `MobCombatMode.FIGHT` lifetime. It must remain `1` through `fight_none` gaps and return to `0` only after the soft combat mode exits. Do not let individual move completion restore vanilla rendering or behavior.
5. Re-register vanilla animations/controllers under their exact client-entity short names. Proxy every controller as `c_<original short name>` in both `animation_controller` and `script_animate`, while direct actor animations keep the original short name; determine the resource type from the active client binding target, not from the `scripts.animate` key text. Remove only the exact original controller runtime keys as `controller__<original short name>` without `c_`, then overwrite every active original `scripts.animate` entry with its original condition combined with `!query.mod.fight`. Direct actor animations, riding subentries, item-use, swimming, baby scaling, and attack controllers must all be inventoried; gating only controller JSON files is incomplete. Register the Mob-owned core combat controller under a `c_` alias and unconditionally in `scripts.animate` (use the project's empty-condition value `""` in `script_animate`); never bind that entry to `query.mod.fight` or any other Molang condition. The core controller must remain active continuously, including combat entry, `fight_none`, and combat exit; place mode/state branching inside the controller instead of gating the controller itself.
6. Build mob-specific native component maps from the active behavior JSON, including movement/navigation goals, target-acquired/escape event components, melee damage, ranged attacks/projectiles, shooters, and mode switch sensors. Disable them on combat-mode entry. Before removal, snapshot the active component-group/form profile with a documented state source and restore only that profile on combat-mode exit so mutually exclusive vanilla forms are not cross-added. Never infer component presence from `RemoveActorComponent`'s bool return: it reports only whether the command was issued. Preserve adult/baby and land/water restoration values.
7. Keep target selectors when SWS needs the vanilla target, but remove any event component that can re-add navigation or attack groups during combat. Add a server `DamageEvent` safety gate for native melee/projectile damage when component removal alone can race; allow SWS-authored damage only through a verified SWS attack-window signal and set blocked damage/knockback/ignite fields defensively. Do not rely on `ignite = false` as a complete fire cancel because NetEase documents that it may not undo ignition; component suppression remains primary.
8. Use a mob-specific SWS-compatible geometry when the vanilla skeleton lacks `root`, segmented torso/limbs, item bones, or required locators. Preserve the mob's texture layout and visual overlay bones while matching the proven humanoid combat bone/locator contract. Never point a visually distinct mob at another mob's geometry merely because their combat states are shared.
9. Verify the deployment with UTF-8 JSON parsing, Python compilation, registry uniqueness, exact short-name/script-animate coverage, unconditional activation of the Mob-owned core combat controller, geometry parent/identifier/locator integrity, and animation-bone resolution. When changing the iron golem, warden, ravager, enderman, or spider proxy chain, also run `scripts/test_vanilla_controller_proxy_prefix.py`. Add focused checks for adult/baby, land/water, melee/ranged, combat entry, `fight_none`, combat exit, native-hit rejection, SWS-hit allowance, and exact component restoration. Resource behavior still requires an appropriate NetEase client test; do not claim static checks prove in-game visuals.
10. Edit only `src/`, project-local skills, tests, and agent rules. Do not sync `.build/dist` or reload the game unless the user explicitly requests it.

### Iron Golem Route

- 铁傀儡部署在规划或编辑前必须完整读取 `.codex/agents/project/mob/iron-golem-combat-deployment-agent.md`。该 agent 记录当前原版资源链、创建来源配置、兼容骨骼、根位移归属、动作白名单和专项验收项；游戏版本变化时必须重新审计原版文件，不能把其中的 3.9.0 清单当作跨版本常量。

### Warden Route

- 坚守者部署或动作调参在规划、编辑前必须完整读取 `.codex/agents/project/mob/warden-combat-deployment-agent.md`。该 agent 记录当前原版涌出/挖掘组件组、声波伤害门、完整客户端动画链、兼容骨骼、七个已确认攻击时序、四向闪避与烟尘窗口、`root_move -> SetMoveMotion` 映射和资源速率换算；版本变化后必须重新审计原版文件。静态视觉分析只能提出候选命中帧，未经用户确认或网易客户端验证不得改写已确认的专属攻击盒。

## SWS 特效画质分级

- 先把招式拆成识别核心、伴生装饰、全屏后处理和持续采样四层。低档必须保留攻击方向、命中反馈、蓄力提示、刀光主体等识别核心，优先降低重复数量、发射密度、采样率和过绘。
- 在接收客户端、本地资源创建前执行画质判定；骨骼/位置查询、模型/粒子创建和计时器注册也应放在判定之后。跨客户端效果通过 `QualityCategory`、`RequiredQuality`、稳定 `EffectKey`、`DensityStride` 与发射倍率传递意图，不让发送方替接收方决定档位。
- 生物 `_MobSWSComponentProxy` 只转发位置参数；公共 SWS 方法新增画质元数据后，Mob 调用必须显式补齐完整位置参数，并运行 `scripts/test_katana_mob_effect_sync.py` 等对应桥接回归。
- 后处理所有权必须按“后处理名 -> 来源实体 -> 实例 token”分别记账，并把“其他玩家特效”作为来源过滤条件；同一实体的多个特效实例不得折叠成布尔值。QyEngine 必须使用模块限定的实例 token 成对注册/释放，并在 `destroy()` 开始时释放，不得等待尾粒子池清空；显式 token 保持幂等，旧三参数调用只能作为单一幂等兼容所有者，禁止累计引用。需要交叠的调用必须显式传入不同 token；任一允许的 token 存活时都不得关闭共享 pass。
- 刀光低/中/高建议按 30/60/120Hz 采样。低档关闭附带粒子但保留主网格，中档限制粒子数，高档才恢复完整密度。
- 快速预设先完整写入全部字段，再统一刷新运行时；细项修改才标记自定义。官方没有设备型号/GPU/内存接口时，不建立猜测机型表，只可用官方 `GetFps()` 保守采样给出当前场景建议并保留手动调整。
- 静态审计运行 `python tools/audit_sws_effects.py` 与 `python .codex/skills/swordsoul-mob-fight/scripts/test_effect_quality_system.py`；文本搜索命中可能包含注释，运行时创建点数量以 AST 回归为准。

## 核心规则

- 优先复用 `SwordSoulFightScripts` 的 SWS 写法；不要重新发明与 SWS 不兼容的状态机、`AttackData` 或计时器结构。
- 修改 Mob 战斗前，先读 SWS 对应实现，尤其是 `FightSystem/Controllers.py`、`FightSystem/FightClient.py` 和对应 `UseXxxState.py`。
- `SwordSoulMobFightScripts` 里的注释用中文，注释简短说明用途即可。
- 禁止使用 `importlib`；热更/注册流程要用显式类、装饰器或项目内已有加载机制。
- 服务端/客户端业务模块尽可能导入 `ServerMod` / `ClientMod` 的核心 API，格式使用 `from xx import *`；只有模块环境冲突、循环导入或纯配置文件才例外。
- 区分 `entityId` 和实体类型：`entityId` 是单个实体实例，`entityType/actorIdentifier` 是实体种族/类型。
- 不要用会冻结动作或 `SetMotion` 的方式处理招式移动控制；`SetBlockControlAi` 在战斗状态内禁用，除非用户重新确认方案。
- 任何网易 ModAPI 行为不确定时，查官方文档或项目内 `QingYunModLibs` 封装，不凭记忆硬写。
- 非必要少写 `try/except`，尤其不要用裸 `except` 吞掉 ModAPI 报错；接口语义明确时直接调用，让真实错误暴露出来。
- 不要回滚用户改动；修改前读文件，修改后做最小验证。
- 命名风格：SWS 持久化逐实体战斗状态字段用 PascalCase（`FightModel`、`SuperArmor`、`MaxHealth`）；单次攻击瞬时参数键用 snake_case（`no_damage`、`cancel_treat`、`cancel_treat_time`）；方法与局部变量用 PascalCase（`getEntityFightState`、`AttackFightState`）。新增字段/函数必须沿用此风格，禁止用 snake_case 命名持久状态字段。
- 注释规范：项目内任何由 Codex 改动或新增的业务逻辑，都必须打中文注释，简述改动内容，并明确标记为 Codex 所改、附改动日期，格式 `# Codex YYYY-MM-DD: <改动说明>`。

## 工作流

1. 用 `rg` 查找 SWS 原实现和 Mob 当前实现。
2. 先确定要复用的是玩家状态、渲染资源、Molang、还是服务端判定。
3. 保持 SWS 风格入口：`self.PlayerRootController`、`StateAnim_CreateTimer`、`AttackData`、`CreateAttack`；用户指定铁傀儡位移格式时，先逐项对照 `IronGolemMob.py`，再以 AST 与 `rg` 拒绝 helper、运动表和循环注册。
4. 实体侧只做必要适配：`playerId` 映射为当前实体 `entityId`，玩家专属组件先接桥，不直接搬。
5. 渲染资源改动后确认是否需要重载资源和渲染控制器。
6. 修改后至少运行相关文件的 `python -m py_compile`。
7. 未经用户明确要求，不要为了验证或方便观察而重启/重载游戏；需要时只提示用户可手动热更或重载。

## 常读文件

- SWS 状态控制：`src/SwordSoul_NewERA_B/SwordSoulFightScripts/FightSystem/Controllers.py`
- SWS 空手状态：`src/SwordSoul_NewERA_B/SwordSoulFightScripts/FightSystem/UseEmptyState.py`
- Mob 控制器：`src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Combat/FightController.py`
- Mob 状态基类：`src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Combat/FightStateSystem.py`
- 僵尸/尸壳实体状态：`src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/ZombieMob.py`
- 静态渲染配置：`src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Render/StaticRenderConfig.py`

## 参考资料

- 项目结构：`references/architecture.md`
- SWS 复用规则：`references/sws-compat.md`
- 静态渲染资源：`references/render-static-resource.md`
- 网易 ModAPI 注意事项：`references/modapi-notes.md`
- 骨骼闪电特效：`references/lightning-vfx.md`
- 原版生物部署：本文件 `Vanilla Mob Combat Deployment Standard`
- 坚守者专项部署：`.codex/agents/project/mob/warden-combat-deployment-agent.md`
- 调试记录：`references/debug-notes.md`
- 任务进度树：`references/progress-tree.md`

## 维护规则

当用户说“整合进 skill”或“写进规则”时，优先更新本 Skill 或对应 reference。规则要短、可执行、能指导未来修改；不要写流水账。

## Completion Audio Notification

- After completing a SwordSoul task and before the final response, run the local completion chime when available:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME/.codex/skills/task-completion-chime/scripts/play_completion_chime.ps1"
```

- Treat this as a courtesy notification only. If playback fails because audio is unavailable or the script cannot run, mention it briefly in the final response and do not treat the main task as failed.
