---
name: auto-fill-mob-move-config
description: Analyze and auto-draft aligned SwordSoul mob move configs from Bedrock/Blockbench actor animations, SWS state classes, root_move curves, AttackData hitboxes, PunchAirFlow/PunchSonicBoom/DirtSmoke/DodgeDirtSmoke schedules, and state timing windows. Use when adding or tuning a mob attack, transferring an authored move to a new entity, generating SetMoveMotion from root_move, or auditing animation-hitbox-VFX alignment in SwordSoul_NewERA_Fight.
---

# Auto Fill Mob Move Config

## 目标

从动画证据自动生成生物招式配置草案，并把“动画时钟、实体位移、命中体积、拳风/音爆、地面烟尘、受控与收势窗口”放到同一条时间轴上验证。自动结果是高质量候选，不得把静态推断冒充网易客户端实机确认。

## 开工前

1. 完整读取项目 `swordsoul-mob-fight`、`bedrock-animation-authoring` 和 `molang-animation-authoring` 技能。
2. 读取目标生物专项 agent；部署新原版生物时，先审计当前安装游戏版本的行为实体、客户端实体、geometry、actor animation、animation controller 和 render controller。
3. 读取目标 SWS/Mob 基类状态及目标实体包装类。SWS 仍是公共状态、攻击系统和特效入口的来源。
4. 处理时钟、判定盒或 VFX 前读取 [parameter-model.md](references/parameter-model.md)。以监守者/铁傀儡作标定或回归时读取 [calibrated-samples.md](references/calibrated-samples.md)。
5. 只处理 `src/`、项目本地 `.codex/` 和测试；不触碰 `.build/dist`，不主动重载游戏。
6. 用户指定某个现有生物作为位移写法基线时，先读取该生物当前实体源码；把它的代码结构视为格式权威，不得用“语义等价”的 helper、表驱动、循环或新抽象替代。

## 证据优先级

按以下顺序解决冲突：

1. 用户明确确认的网易客户端表现与命中帧。
2. 当前工作树实际运行的实体 Python、导出动画 JSON、BBModel 和控制器绑定。
3. 当前专项回归测试与 mob agent 基线。
4. 相似生物、旧版本、其他武器或记忆中的经验值。

测试或 agent 与当前运行源不一致时，报告漂移，不要静默把当前配置改回旧基线。

## 快速审计

新生物还没有状态配置时，先从动画提出接触候选：

```powershell
python .codex/skills/auto-fill-mob-move-config/scripts/suggest_contact_frames.py `
  --animation-json <actor.animation.json> `
  --animation <animation.full.name>
```

它按手臂/躯干局部角速度、接触前减速、root 旋转跨度和根净位移输出候选 `source_time/state_time`、主导骨骼与动作类型。`catmullrom` 只作线性近似，候选必须再与 BBModel 和客户端表现核对。

先对已经存在的招式运行：

```powershell
python .codex/skills/auto-fill-mob-move-config/scripts/analyze_move_alignment.py `
  --entity-python src/SwordSoul_NewERA_B/SwordSoulMobFightScripts/Entities/WardenMob.py `
  --animation-json src/SwordSoul_NewERA_R/animations/mob/wraden/warden.animation.json `
  --bbmodel-name fight_warden.bbmodel
```

铁傀儡替换为 `IronGolemMob.py`、`fight_iron_golem.animation.json` 和 `fight_iron_golem.bbmodel`。脚本只离线读取，输出：

- 状态四窗口与动画有效播放时长。
- `CreateAttack`、拳风/音爆、烟尘及其最近命中时间差。
- 位移模式（`piecewise_velocity` 或 `tick_delta`）、动画根位移、隐含比例和误差；分段瞬时速度只输出明确标注的配置对齐量，逐 tick 根位移才按样本求和输出目标格数。
- 实际攻击授权关闭时间、被截短的 `hit_time`、继承 `onStart` 和重复表现风险。

脚本只支持 Python 3 可解析的实体包装模块；遇到 SWS Python 2 源码时直接读原文，不要把解析器失败误报为源码错误。

## 自动填参流程

### 1. 建立唯一时间轴

记录 `source_time`、动画 `anim_time_update`、`state_time` 和 24fps 帧号。优先使用实际 `anim_time_update`；只有资源未覆盖速率且明确采用整段归一时，才用 `state_time = source_time * StateAnimTime / SourceLength`。若动画有效时长与 `StateAnimTime` 不同，先标记时钟漂移，再继续生成候选。

### 2. 切分动作语义

把动作分成蓄力、推进、有效接触、跟随、收势五段。用手/前臂/躯干角速度峰值、突然减速或反向、双臂同步下砸、根骨旋转和根位移爆发提出接触候选；多峰动作必须保留多个独立接触点。

### 3. 生成状态窗口

- `AttackTime` 覆盖需要授权的最后命中扫描。
- `UnControlTime` 落在主要跟随动作结束、允许切招的位置。
- `StateKeepTime` 覆盖强制收势与控制保持。
- `StateAnimTime` 覆盖需要显示的完整动作或明确裁切点。

默认保持 `AttackTime <= UnControlTime <= StateKeepTime <= StateAnimTime`。同时计算控制器真实关闭公式与 `hit_time` 是否被截短，不只比较字段大小。

### 4. 生成服务器位移

从累计 `root_move.position` 求相邻增量，显式确认每个轴的映射。监守者与铁傀儡当前标定为 `anim X -> local X`、`anim Y -> local Y`、`anim -Z -> local +Z`，不能推广成所有武器/生物的全局常量。

#### 用户指定铁傀儡格式时的硬门槛

严格复用 `IronGolemMob.py` 当前 `onStart` 结构；格式本身属于验收目标，不能只保证运行语义相同：

```python
StateMotion = self.State_Motion
SetMoveMotion = self.PlayerRootController.SetMoveMotion
if StateMotion:
    SetMoveMotion((x0, y0, z0), power0*self.State_MotionPower)
    self.StateAnim_CreateTimer(time1, SetMoveMotion, False, (x1, y1, z1), power1*self.State_MotionPower)
    self.StateAnim_CreateTimer(1.50, SetMoveMotion, False, (0, 0, 0), 0.0*self.State_MotionPower)
```

- 把首个 `0` 秒位移段写成一次直接 `SetMoveMotion`；把其余每个时间点写成显式 `StateAnim_CreateTimer`；每个功率都直接乘 `self.State_MotionPower`；结尾显式清零。
- 禁止在目标状态中使用 `ScheduleRootMotionTicks`、运动表播放器、模块级曲线表、循环/推导式批量注册、运行时 JSON 采样、位移 Mixin 或新包装 helper。除非用户明确授权另一种格式，否则不得自行发明写法。
- 先保留已经确认的时间、方向和功率，再做纯格式迁移；“改成铁傀儡格式”本身不授权重新标定倍率、合并时间点或改变总位移。
- 用 AST 验证每个目标 `onStart` 恰有一个首段直接调用，后续仅由显式状态计时器调度；再用 `rg` 确认目标实体源码不含上述禁止结构。

只有目标生物已经通过网易客户端标定为分段瞬时速度时才使用：

```text
direction = normalize(mapped_delta)
power = length(mapped_delta) / state_dt * motion_scale
```

监守者与铁傀儡当前共同标定 `motion_scale≈0.00527`，它只适用于两者已实机标定的分段瞬时速度，不能解释成“实际移动格数”，也不能直接套给其他生物。若用户要求服务器实体严格复现 BB 的完整身位，按 20Hz 对曲线补样，把相邻样本差从模型单位换成格（通常 `delta/16`），并按样本位移求和验证总格数；20Hz 只是位移数据的采样密度，不得凌驾于用户指定的代码格式。用户指定铁傀儡格式时，仍把每个样本展开为首段直接 `SetMoveMotion` 与后续显式 `StateAnim_CreateTimer`，不得改用 `ScheduleRootMotionTicks`。不要把 `SetMotion` 瞬时向量乘以秒数冒充真实位移。普通分段速度仍可合并短于 `0.08s` 的过密段；逐 tick 根位移重放明确豁免这条合并规则。两种模式都要保留爆发、停顿、回退、横移，最后在 `StateAnimTime` 清零。可见骨架不得再继承同一 `root_move` 平移。

遇到“BB 显示移动很多身位、游戏只移动一点”时按顺序诊断：

1. 从当前 BBModel/actor 读取首尾累计位置，核对模型单位比例与轴，不从屏幕像素长度猜距离。
2. 用 `anim_time_update` 把源关键帧换到状态时间，保留 Catmull-Rom；不要把 source 秒直接当 state 秒。
3. 检查服务端是在关键帧处只调用几次 `SetMotion`，还是以 20Hz 重放相邻位置差。前者会受阻力衰减，不能用 `power * seconds` 证明总格数。
4. 检查 `State_MotionPower`、原生 AI/导航、碰撞、台阶、落地与终止清零是否再次改变运动。
5. 分别报告“模型净位移”“换算目标格数”“服务器样本和”“客户端实测格数”；四者不得混写。禁止靠盲乘倍率把某一次观感修到差不多。

### 5. 生成攻击体积

先选语义模板，再按目标 geometry、骨架尺度和招式覆盖面调整：

- 单臂/交替横扫：前方扇形，通常 `180°` 左右，旋转符号跟随主挥击侧。
- 大范围扫击/旋转：`260°～360°`；连续旋转用低伤、多次短扫描，不用一个超长扫描代替所有接触。
- 下砸：宽扇形或径向体积，原点靠近地面，命中向量反映击飞/压制方向。
- 地面长廊冲击：用 `high_type=up` 与约 `rotate.x=-90°` 把高度轴旋到地面前方；横向宽度由 `range` 控制，长度由 `high` 控制。

不要把 `hit` 当判定盒方向：它是命中后的击退向量。不要把 `hit_time` 当命中帧：它是创建判定后继续扫描目标的时长。

### 6. 生成视觉事件

- 拳风放在肢体速度峰值到命中前 `0～0.08s`，重击可与命中同帧；旋转必须按特效网格自身坐标校准，不能机械复制 AttackData `rotate`。
- `DirtSmoke` 只放在落地、踏地或冲击波接地事件，常位于命中前 `0.08s` 到命中后 `0.20s`。
- 长廊冲击的烟尘空间采样应覆盖旋转后判定盒的长度轴；装饰范围可以大于伤害半径，但必须明确二者语义。
- 连续旋转用 `PunchSonicBoom` 或重复拳风表现持续接触，频率与多段攻击盒一致或有清楚的视觉节拍关系。
- 闪避烟尘覆盖高速根位移段，朝向与移动方向一致；持续时间是一次发射窗口，不是第二个生成时间点。

### 7. 落地到代码

优先保持共享状态薄包装。只有当前生物已由用户/实机确认专属命中、位移或窗口时，才在实体模块内最小覆写 `__init__`/`onStart`。若调用共享 `BaseState.onStart(self)`，先列出哪些攻击、位移、声音、镜头和特效会被继承；关闭 `State_Attack/State_Motion` 不会自动关闭无条件视觉事件。

所有攻击、位移和特效分别受 `State_Attack`、`State_Motion`、`State_Effect` 控制。不要让同一事件从共享基类和实体覆写各生成一次。

## 验证

1. 运行本技能分析脚本，解决高风险警告或明确记录为何保留。
2. 运行 `python .codex/skills/auto-fill-mob-move-config/scripts/test_analyze_move_alignment.py`。
3. 运行 `python .codex/skills/auto-fill-mob-move-config/scripts/test_suggest_contact_frames.py`。
4. 对编辑的 Python 运行 `python -m py_compile`，对 JSON/BBModel 做 UTF-8 严格解析。
5. 运行目标生物专项部署测试；若其基线已漂移，报告差异并先确认新的权威值，不盲改生产配置或测试。
6. 静态验收至少检查：动作时钟、最终清零、分段速度的标定积分或逐 tick 根位移的格数求和、攻击授权、扫描截断、拳风时间差、砸地烟尘范围、继承表现、动画骨骼/locator 解析。报告必须标明位移模式，不能把瞬时速度的名义积分写成游戏实际格数。
7. 网易客户端最终观察：接触帧、攻击盒位置、总推进、是否越过目标、冲击方向、烟尘接地、状态结束滑步。静态分析不得宣称完成这些实机项。
8. 用户指定铁傀儡格式时，专项回归必须拒绝目标实体中的 `ScheduleRootMotionTicks`、运动表 helper、循环注册和运行时采样，并验证首段直接调用、逐条显式计时器、`State_MotionPower` 乘法和状态末尾清零全部存在。

## 交付格式

每招输出一行摘要：动作/状态时长、接触候选及置信度、位移净积分、攻击体积、拳风/音爆、地面特效、窗口、警告。随后给出可直接落地的状态代码或明确说明因哪项缺少实机确认而只生成候选。
