# SWS 复用规则

## 基本原则

- 迁移招式时优先保持 SWS 源码结构，而不是抽象成 Mob 专属新结构。
- `AttackData` 保持普通 dict，不设计成类属性驱动的单段攻击系统。
- 多段攻击按 SWS 写法：多次 `StateAnim_CreateTimer(..., self.PlayerRootController.CreateAttack, False, AttackData)`。
- `self.PlayerRootController` 在 Mob 侧指向 `MobFightController`，用于兼容 `CreateAttack`、`SetMoveMotion` 等入口。
- SWS 代码里的 `playerId` 在 Mob 侧语义是当前实体 `entityId`。

## 迁移检查表

1. 读取 SWS 原状态类的 `__init__` 和 `onStart/onEnd`。
2. 复制生命周期字段：`AttackTime`、`UnControlTime`、`StateKeepTime`、`StateAnimTime`、`CanMoveAfter`。
3. 复制 `AnimationMolang`，并确认该 Molang 已在渲染配置注册。
4. 复制 `AttackData` 字段，保留 SWS 原字段名。
5. 复制 `StateAnim_CreateTimer` 节奏。
6. 玩家专属组件先不直接搬：`CameraSystem`、`TrailSystem`、`CommonSoundSystem`、UI、玩家输入组件。
7. 修改后跑相关 Mob 文件的语法检查。

## SWS 招式配置迁移到 Mob 的硬性避坑

- 先找对源文件：空手攻击/防御在 `FightSystem/UseEmptyState.py`；通用闪避、让步、二段跳、受击、step、钩锁在 `FightSystem/CommonState.py`；武器招式在对应 `UseXxxState.py`。
- 迁移参数必须逐状态复制，不要把四个方向合并成一个 `direction` 变量和一套分支参数；禁止为了省代码引入 `direction[2]`、`restDirection` 这类 SWS 源码没有的抽象。
- Mob 状态库只保留普通类定义，例如 `EmptyAttackFirst`、`EmptyBudgeBack`、`KatanaAttackFirst`。不要复制 SWS 的 `@FightStateSystem.BindState`、`@FightStateSystem.BindSkillState`、`@Screen...` 等装饰器；实体绑定放在 `QingYunMob.py` 等实体模块的 `@BindMobState`。
- 不要把 SWS 客户端专属全局对象和注册块搬进 Mob 服务端状态文件，尤其是 `Screen`、`PostProcessComp`、`ClientApi`、`ListenClientEvents`、`UnListenClient`。
- SWS 落地检测要做最小适配：保留 SWS 的下落位移、攻击框和时间点，但把玩家客户端事件换成 Mob 侧已有的服务端落地机制，如 `SetCheckFall(True/False)` 或 `OnGroundServerEvent` 写法。
- 每个 `BaseFightState` 子类都必须先调用 `BaseFightState.__init__(self)`，否则 `BaseApi`、组件缓存、SWS 全局同步会缺字段。
- 不要留下重复状态块。迁移后必须搜索 raw SWS 类名和 Mob wrapper 类名，例如同时存在 `class AcutePerception` 和 `class EmptyAcutePerception` 就是错误。
- 迁移后必须跑清理检查：`rg "FightStateSystem\\.Bind|@Screen|ListenClientEvents|UnListenClient|direction\\[2\\]|restDirection" <mob_state_file>`，然后执行 `python -m py_compile`。

## 已知语义

- `query.mod.fight`：实体正在执行具体招式时为 `1.0`，招式退出后为 `0.0`；它不是外层战斗模式开关。
- `query.mod.mob_fight_mode`：外层 native/fight 模式标记。
- `query.mod.attack_state`：每次开始执行战斗动作时在 `0/1` 之间翻转，用于触发动画控制器重新进入。

## 移动控制

- 暂不要在招式里使用 `SetBlockControlAi` 禁止实体移动，它会影响动作和 `SetMotion`。
- `SetMoveState` 在 Mob 侧作为 SWS 兼容入口，语义是开关原版移动/寻路/转向组件：`True` 恢复，`False` 删除。
- 进入具体招式时 `MobFightController` 默认 `SetMoveState(False)`；退出到空状态时默认 `SetMoveState(True)`。
- 特殊招式需要自动索敌转向时，可以在招式生命周期里临时 `self.PlayerRootController.SetMoveState(True)`，结束前或不需要时再关回 `False`。
- `SetMoveMotion` 用于招式自身位移，必须保持可用。
