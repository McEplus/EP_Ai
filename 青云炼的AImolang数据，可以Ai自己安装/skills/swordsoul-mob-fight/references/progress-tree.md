# 任务进度树

本文用于让后续 Codex 快速了解 `SwordSoulMobFightScripts` 已完成什么、正在卡什么、下一步该做什么。更新时只记录对后续开发有指导意义的状态，不写流水账。

## 总目标

- 构建实体战斗系统，让每个实体都能像玩家 SWS 一样执行招式。
- 实体拥有原生模式和战斗模式，战斗状态机可被软开关和硬开关调停。
- 招式系统优先复用 `SwordSoulFightScripts`，让玩家招式能大块迁移到实体。
- 实体渲染资源支持按实体类型静态加载、热更、Molang、动画控制器和原版控制器屏蔽。

## 当前阶段

状态：基础框架已初步搭好，正在从“能进状态”推进到“严格复刻 SWS 招式行为”。

优先级：

1. 稳定 SWS 兼容状态机入口。
2. 完成尸壳 demo 的空手前三段普攻可运行验证。
3. 解决攻击时原生移动干扰，但不能冻结动作或 `SetMotion`。
4. 继续完善静态渲染资源和 Molang 触发链。

## 已完成

### 1. 项目结构

- 已创建 `SwordSoulMobFightScripts`，与 `SwordSoulFightScripts` 同级。
- 已按功能拆分目录：`Core`、`Combat`、`Entities`、`Render`、`AI`。
- 已建立实体系统基类：`SwordSoulMobEntity`。
- 已建立具体实体示例：`ZombieMob`，当前同时绑定 `minecraft:zombie` 和 `minecraft:husk`。

### 2. 实体实例与实体类型

- 已明确区分：
  - `entityId`：单个实体实例。
  - `entityType/actorIdentifier`：实体种族/类型，例如 `minecraft:zombie`、`minecraft:husk`。
- 每个实体实例会持有独立的战斗状态实例。
- 静态渲染资源按实体类型注册，不按单个 `entityId` 注册。

### 3. 外层模式与基础状态机

- 已建立 native/fight 外层模式。
- 已建立硬开关和软开关思路。
- 已建立基础状态类型：攻击、蓄力、格挡、闪避、钩锁等框架。
- 子类实体可以删减不需要的能力，例如僵尸当前移除 sneaking 和 hock_rope。

### 4. SWS 风格招式状态系统

- 已建立 `MobFightStateSystem`。
- 已建立 `MobFightState` 基类。
- 已建立 `MobFightController`。
- 已提供 SWS 兼容字段/入口：
  - `self.PlayerRootController`
  - `self.playerId`
  - `self.PlayerId`
  - `StateAnim_CreateTimer`
  - `UnControl_CreateTimer`
  - `StateKeep_CreateTimer`
  - `CreateAttack`
  - `SetMoveMotion`
  - `SetMoveState` 兼容空入口
- 已实现模块全局 `playerId` 同步，方便复制 SWS 中 `"playerId": playerId` 的写法。

### 5. 攻击判定桥接

- `MobFightController.CreateAttack` 已转接到 SWS 服务端 `CreateAttack`。
- `AttackData` 保持 SWS 原 dict 格式。
- `create_attack` 会保留 SWS 扩展字段，只强制把 `playerId` 替换成当前实体 `entityId`。
- 已放弃 `AttackSegments` 这种与 SWS 不兼容的抽象。
- 多段攻击应按 SWS 写法：多次 `StateAnim_CreateTimer(... CreateAttack ... AttackData)`。

### 6. 僵尸系空手前三段普攻

- 已从 SWS `UseEmptyState.py` 搬入前三段空手普攻核心参数。
- 该套状态已同时绑定到僵尸和尸壳；第一个 demo 优先用尸壳，避免白天燃烧干扰测试。
- 已搬入生命周期字段：
  - `AttackTime`
  - `UnControlTime`
  - `StateKeepTime`
  - `StateAnimTime`
  - `CanMoveAfter`
- 已搬入三段 `AttackData`。
- 已搬入三段 `SetMoveMotion` 位移 timer。
- 已搬入三段攻击判定触发时间：
  - 第一段：`0.35`
  - 第二段：`0.21`
  - 第三段：`0.3`
- 没有直接搬玩家专属组件：`CommonSoundSystem`、`CameraSystem`、`TrailSystem`。

### 7. Molang 语义

- `query.mod.fight`：只表示实体正在执行具体招式，不是外层 fight 模式开关。
- `query.mod.mob_fight_mode`：外层 native/fight 模式标记。
- `query.mod.attack_state`：每次开始执行战斗动作时在 `0/1` 间翻转，用于动画控制器重新触发。
- 已实现战斗动作开始时设置 `query.mod.fight = 1.0`，动作结束/reset 时设置 `0.0`。
- 已实现攻击动作开始时翻转 `query.mod.attack_state`。

### 8. 静态渲染资源框架

- 已建立静态资源配置和注册框架：
  - `StaticRenderRegistry.py`
  - `StaticRenderLoader.py`
  - `StaticRenderConfig.py`
  - `MobRenderClient.py`
- 已支持配置字段：
  - model/geometry
  - texture
  - material
  - animation
  - animation_controller
  - script_animate
  - render_controller
  - molang
  - render_params
  - remove_animation_controller
- 已支持重复注册同 actorIdentifier 视为热更。
- 已支持加载后重载实体渲染控制器。
- 已支持 `UiInitFinished` 和 `AddEntityClientEvent` 双时机加载。

### 9. 原版动画控制器屏蔽

- 已加入移除原版动画控制器的思路。
- 已知僵尸抬手动作优先检查：
  - `zombie_attack_bare_hand`
  - `attack`
- 有些原版控制器不是 `script_animate` 注册，必须真的移除。

### 10. 调试入口

- 已有 I 键调试入口，用于让附近尸壳尝试攻击。
- 曾加入 `query.mod.fight` 调试打印：服务端调用前和调用后 1 秒读取。
- `BaseApi.SetMolang` 曾有用户手动打印参数，注意不要随意删用户调试输出。

## 已踩坑和结论

### 1. importlib 禁用

- 不能使用 `importlib`。
- 配置热更应通过类、装饰器、显式加载流程完成。

### 1.1 ServerMod / ClientMod 导入规则

- 服务端业务模块尽可能使用 `from xx.ServerMod import *` 导入核心 API。
- 客户端业务模块尽可能使用 `from xx.ClientMod import *` 导入核心 API。
- 纯配置、纯注册类、封装库内部文件、存在环境冲突或循环导入风险的模块可以例外。

### 2. SetBlockControlAi 不适合招式移动控制

- 该接口会冻结实体动作，且可能冻结 `SetMotion` 效果。
- 不能用于“攻击时不让实体自己走路”的当前方案。
- 目前 `SetMoveState` 已改为开关原版移动/寻路/转向组件，不再调用冻结 AI。

### 3. 移动控制当前方案

- 进入具体招式时删除 `minecraft:movement`、`minecraft:movement.basic`、`minecraft:navigation.walk`、`minecraft:behavior.look_at_player`、`minecraft:behavior.random_look_around`。
- 退出具体招式时按实体子类配置恢复这些组件。
- 不修改或依赖 `component_groups`；默认配置放在 `SwordSoulMobEntity.NativeControlComponentMap`。
- 该方案来自用户实测，理论上不会冻结动画和 `SetMoveMotion`；仍需要进游戏验证恢复是否稳定。

### 4. SWS 复制必须保持原风格

- 不要把 SWS 招式改造成另一套 Mob 专属设计。
- 未来搬招式时应优先让代码长得像 SWS，减少手动修改成本。

### 5. 渲染资源设置后必须重载

- 修改实体资源后必须重载资源和渲染控制器，否则可能不生效。
- Molang 设置无效时先查注册，再查加载时机，再查渲染控制器重载。

## 当前未完成

### P0：攻击期间移动干扰

- 目标：实体执行攻击时不走原生寻路，但招式 `SetMoveMotion` 仍有效。
- 禁止方案：`SetBlockControlAi`。
- 当前方案：`MobFightController` 进入招式时调用 `SetNativeControlState(False)`，退出到空状态时调用 `SetNativeControlState(True)`。
- 待验证：连续切招时是否稳定、组件恢复后尸壳是否重新寻路、特殊招式临时打开转向是否符合预期。

### P0：尸壳前三段普攻实测

- 需要进游戏验证：
  - 是否能进入三段攻击。
  - `query.mod.fight` 是否正确进入/退出。
  - `query.mod.attack_state` 是否每次翻转。
  - SWS 攻击判定是否能打中目标。
  - 原版动画控制器是否仍有冲突。

### P1：实体表现组件兼容桥

- 待接桥：
  - `CommonSoundSystem`
  - `CameraSystem`
  - `TrailSystem`
  - 攻击命中特效
- 原则：不要直接复制玩家客户端组件调用到实体侧。

### P1：更多 SWS 招式迁移

- 当前只搬了空手前三段。
- 后续可继续迁移：
  - 空手后续段数。
  - 刀/匕首/太刀等武器状态。
  - 格挡、闪避、受击状态。

### P1：渲染资源配置优化

- 继续完善僵尸系静态资源配置；`minecraft:husk` 已复用同一套静态渲染配置。
- 补全所需 Molang。
- 明确需要移除的原版动画控制器列表。
- 测试热更重复注册是否稳定。

### P2：AI 仲裁

- 当前 AI 仲裁只是基础骨架。
- 后续需要接入距离、目标状态、冷却、连段、格挡/闪避条件。
- AI 决策不应直接硬切状态，而应写入请求，由状态机统一调停。

## 下一次接手建议

1. 先读本文件和 `references/sws-compat.md`。
2. 不要继续使用 `SetBlockControlAi` 解决移动问题。
3. 先确认 `FightController.py` 当前语法通过。
4. 进游戏测试尸壳前三段普攻，记录：
   - 动画是否触发。
   - 判定是否触发。
   - 原生移动是否干扰。
   - 哪些原版控制器仍在影响动作。
5. 重点测试动态删除/恢复默认五个原版组件的方案；如果恢复失败，优先检查 `AddActorComponent` 的参数格式。

## 文件健康检查

常用检查命令：

```powershell
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Combat\FightController.py
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Combat\FightStateSystem.py
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Entities\ZombieMob.py
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Render\StaticRenderConfig.py
```

## 更新规则

- 完成一个阶段后，把条目从“未完成”移动到“已完成”。
- 遇到实测结论，写入“已踩坑和结论”。
- 只记录能帮助后续开发的事实，不记录聊天过程。
