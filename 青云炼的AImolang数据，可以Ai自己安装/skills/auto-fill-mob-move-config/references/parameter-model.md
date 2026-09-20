# 招式参数关系模型

## 目录

- [四个时钟](#四个时钟)
- [状态窗口](#状态窗口)
- [攻击体积的真实语义](#攻击体积的真实语义)
- [root_move 到服务器位移](#root_move-到服务器位移)
- [动作语义到判定模板](#动作语义到判定模板)
- [拳风、音爆与地面特效](#拳风音爆与地面特效)
- [自动化置信度](#自动化置信度)
- [每招输出结构](#每招输出结构)

## 四个时钟

必须区分：

| 名称 | 含义 | 常见来源 |
|---|---|---|
| `frame` | Blockbench 帧号 | `snapping`，常为 24fps |
| `source_time` | 动画资源内秒数 | actor animation/BBModel keyframe |
| `state_time` | SWS 状态计时器秒数 | `StateAnim_CreateTimer` |
| `scan_time` | 攻击盒创建后继续查找目标的秒数 | `AttackData.hit_time` |

若 `anim_time_update = query.anim_time + query.delta_time * rate`，则：

```text
source_time = state_time * rate
visual_duration = animation_length / rate
```

若未写 `anim_time_update`，`rate=1`。不要因为 `StateAnimTime` 与资源长度不同，就擅自按长度比换算接触帧；先确认资源是否故意裁切/保持，或速率字段是否在重新导出时丢失。

## 状态窗口

### 字段

- `AttackTime`：SWS 攻击授权的基准时长，不是命中帧。
- `UnControlTime`：最早允许状态衔接/打断的时间。
- `StateKeepTime`：强制状态与收势控制的保持时间。
- `StateAnimTime`：本状态允许视觉与状态计时器存活的总时长。

当前 Mob 控制器在 `onStart` 记录攻击计时器后，使用：

```text
attack_state_close = max(AttackTime, latest_CreateAttack_timer) + 0.05
```

它不会自动把 `hit_time` 加到关闭时间。单个攻击盒实际连续扫描时长近似：

```text
effective_scan = max(0, min(
    create_time + hit_time,
    attack_state_close,
    StateAnimTime
) - create_time)
```

因此自动审计必须同时报告声明 `hit_time` 和有效扫描时长。新配置默认让 `AttackTime` 覆盖 `create_time + hit_time`；若故意用授权窗口截短扫描，必须写明目的。

状态窗口通常按以下锚点产生：

```text
AttackTime     = 最后有效接触结束 + 小余量
UnControlTime  = 主要跟随动作结束
StateKeepTime  = 强制收势结束
StateAnimTime  = 完整视觉结束或明确裁切点
```

## 攻击体积的真实语义

默认 `AttackType="Round"` 是围绕局部前方的扇柱体。服务端运行时会先执行 `high += 1.0`；配置 `high=1.5` 的实际高度参数是 `2.5`。

| 字段 | 判定语义 |
|---|---|
| `range` | 扇形/球形半径；不是实体位移距离 |
| `radians` | 水平扇形张角，中心沿局部前方 |
| `high` | 输入高度，运行时再加 `1.0` |
| `high_type` | `all` 双向、`up` 正向、`down` 负向扩展 |
| `offset` | 判定原点的实体局部偏移，默认随实体 yaw 旋转 |
| `rotate` | 对整个局部判定体积施加 X/Y/Z 旋转 |
| `view_z` | 是否把实体俯仰纳入偏移/体积方向 |
| `hit_time` | 创建后持续扫描时间 |
| `hit` | 命中后击退局部向量，与判定体方向分离 |
| `power` | 击退强度，不是 root motion 功率 |

### 旋转高度轴形成地面长廊

默认高度沿局部 Y。使用约 `rotate=(-90,0,0)` 后，高度轴被旋到局部前后方向。配合：

```text
range = 侧向半宽/近端半径
high = 长廊长度（运行时再 +1）
high_type = "up"
radians = 300～360
```

即可得到前方地面冲击长廊。监守者的 `range=2, high=20, high_type=up, rotate.x=-90` 与 `z=2..20` 烟尘采样是一组设计，而不是两个独立魔法数。

### 旋转与拳风不可直接复制

攻击体积的 `rotate` 作用于查询坐标；拳风 `rotate` 作用于 `arris_round` 特效网格和 shader。两者可以共享挥击平面，但零姿态可能相差 `90°/180°`。必须用已校准特效资产或客户端观察确定偏置。

## root_move 到服务器位移

`root_move.position` 是累计位置，不是速度。对每段：

```text
delta_src = pos(t1) - pos(t0)
delta_state = axis_map(delta_src)
direction = normalize(delta_state)
power = length(delta_state) / (state_t1 - state_t0) * motion_scale
```

监守者/铁傀儡当前分段瞬时速度标定：

```text
mapped_x = delta_src.x
mapped_y = delta_src.y
mapped_z = -delta_src.z
motion_scale = 0.00527
```

验证公式：

```text
sum(direction * power * segment_dt)
≈ axis_map(root_last - root_first) * motion_scale
```

上式只是两只已标定生物的配置对齐量，不是游戏实际格数。网易 `SetMotion` 设置的是瞬时移动向量，后续会受物理阻力影响；不能把 `power * 秒数` 直接报告成实体移动距离，也不能把 `0.00527` 推广到其他生物。

需要严格复现 BB 完整身位时使用逐 tick 根位移模式：

```text
block_delta_tick = axis_map(root(t + 0.05s) - root(t)) / 16
SetMotion(normalize(block_delta_tick) * length(block_delta_tick))
total_blocks = sum(block_delta_tick)
```

状态时间与源动画时间仍先通过 `anim_time_update` 换算；Catmull-Rom 曲线在 20Hz 时间点补样。每个时间片都重新设置瞬时向量，以避免一次性速度被地面阻力提前衰减。静态求和证明的是无碰撞目标位移，客户端仍可能因墙体、台阶、卡位或计时器实际调度出现差异。

要求：

- 方向向量归一化；零功率段允许零向量。
- 普通分段速度中，小于 `0.08s` 的密集段按累计位移合并，随后重新算方向与功率；逐 tick 根位移模式保留 `0.05s` 样本，不做此合并。
- 保留停顿、回退、横移和命中附近爆发。
- `StateAnimTime` 必须有最终 `power=0`。
- `catmullrom` 的关键帧折线只是近似；高速曲线必要时在离线阶段补样，不能宣称线性拟合精确。
- 可见骨架与服务端碰撞体只能有一个 root motion 所有者。

## 动作语义到判定模板

### 单臂或交替横扫

识别证据：某一侧上臂/前臂角速度峰值，躯干跟随旋转，接触后迅速减速或反向。

候选：

- `radians≈180`，`range` 取动画手臂覆盖距离加少量目标碰撞补偿。
- `offset.y` 对准胸/腰高度，`rotate.z` 符号随挥击侧变化。
- 单次 `hit_time=0.05～0.10`；拳风在命中前 `0～0.08s`。

### 持续冲锋/双峰冲刺

识别证据：根位移持续高速推进，并出现一个或多个独立手臂/躯干接触峰。

候选：

- 前方 `180～260°` 扇形。
- 每个接触峰独立创建攻击盒和拳风。
- 长 `hit_time` 只覆盖连续接触段；计算授权窗口截断。
- 在第二次冲击或落地时生成烟尘，不把整段跑动都当砸地。

### 旋转连击

识别证据：root/waist yaw 连续跨越多个整圈，肢体形成稳定外展。

候选：

- `radians≈360`，按每圈/每个节拍创建低伤短盒，通常间隔 `0.1s` 左右。
- 音爆/拳风交替分布在左右偏移，频率与持续接触可读性一致。
- 最终重击单独使用更高伤害、不同击退和更短扫描。

### 下砸/地面冲击

识别证据：双臂同步下落、躯干前俯、垂直速度触底后反弹或停顿。

候选：

- 近身圆形：`radians=300～360`，原点靠近地面。
- 向上击飞：`high_type=up`，`hit.y>0`。
- 地面长廊：旋转高度轴，`high` 决定前伸长度。
- 烟尘在接触前 `0.08s` 到后 `0.20s`；只有落地事件才产生。

## 拳风、音爆与地面特效

### PunchAirFlow

- 绑定实体/骨骼后随实体 yaw 更新。
- `offset` 是特效出生/跟随位置，侧手攻击可用 `x=±0.5`。
- `Time` 是存续时长；`Size` 是识别规模，普通重拳常见 `0.9`，重击可到 `1.2`。
- 触发锚点是肢体速度峰值，而非状态开始。

### PunchSonicBoom

- 只在出生帧锁定世界位置与 yaw，后续不跟随实体位移。
- 适合连续旋转、短促冲击层，不适合需要黏在手上的长跟随拳风。

### DirtSmoke

- 单次 `DirtSmoke` 是世界位置爆发；offset 按实体 yaw 旋转。
- 长廊烟尘可以在很短时间窗内沿长度轴多点采样。
- `DodgeDirtSmoke`/`SprintDirtSmoke` 是持续采样窗口；开始时间加 `Time` 才是自然结束时间，不要把结束时间再写成第二次生成。

## 自动化置信度

| 项目 | 默认置信度 | 原因 |
|---|---|---|
| JSON/状态字段提取 | 高 | 确定性语法证据 |
| root motion 积分 | 高 | 可回归的数学关系 |
| 动画时钟换算 | 高/中 | 取决于 `anim_time_update` 是否明确 |
| 接触候选帧 | 中 | 静态速度峰值不能证明实机碰撞 |
| 判定形状类别 | 中 | 动作语义通常可判，但尺度依赖目标与客户端 |
| 精确 `range/offset/rotate` | 低/中 | 依赖 geometry、碰撞体与实机观感 |
| 特效网格旋转 | 低/中 | 特效资产零姿态与判定坐标不同 |

低/中置信度项目必须列入客户端验收，不得自动写成“已确认”。

## 每招输出结构

```text
state_id / animation_name
source_length / anim_rate / StateAnimTime
phase: windup -> drive -> contact[] -> follow -> recover
motion: axis_map / scale / segment table / integrated delta
hitboxes: create_time / shape / size / rotate / offset / scan / knockback
vfx: airflow / sonic / dirt / dodge trail and nearest contact delta
windows: Attack / UnControl / Keep / Anim / actual attack close
confidence: timing / motion / hitbox / VFX
warnings: clock drift / clipped scan / inherited duplicates / missing terminal zero
```
