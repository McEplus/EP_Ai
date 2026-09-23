# 军械库特殊换弹 specialReload 配置与动画适配经验

## 适用场景

用于栓动、管式、弹夹式或其它需要“分段装填”的枪械。典型需求包括：

- 一次压入多发子弹，例如 5 发压夹。
- 不足一组时改为逐发装填，例如 1 发装填。
- 空仓和非空仓使用不同的起始动作。
- 每次循环装填后继续判断是否还有弹药，直到弹匣满或玩家中断换弹。
- 复用现有换弹状态机、弹药同步和公共模型控制器。

核心原则是：`specialReload` 只描述枪械的换弹数据，公共代码负责选择阶段和推进状态，动画资源负责表现。不要为每一把枪重新复制一套换弹系统。

## 核心数据结构

推荐使用 `type: "a"`，并使用两组序列：

```json
"specialReload": {
    "name": "枪械名称特殊换弹",
    "type": "a",
    "sequence": [
        [
            5,
            2,
            {
                "reloadEmptyTick": 1.625,
                "reloadEmptyBullet": 5.0,
                "reloadTacticalTick": 2.0,
                "reloadTacticalBullet": 3.5,
                "reloadLoopTick": 2.3542,
                "reloadLoopBullet": 1.5,
                "reloadEndTick": 1.6875,
                "reloadCamera": [
                    "animation.weapon.reload_start",
                    "animation.weapon.reload_start_empty"
                ],
                "reloadLoopCamera": [
                    "animation.weapon.reload_clip",
                    "animation.weapon.reload_clip_empty"
                ],
                "reloadEndCamera": [
                    "animation.weapon.reload_end",
                    "animation.weapon.reload_end"
                ]
            }
        ],
        [
            1,
            1,
            {
                "reloadEmptyTick": 1.625,
                "reloadEmptyBullet": 3.5,
                "reloadTacticalTick": 2.0,
                "reloadTacticalBullet": 3.5,
                "reloadLoopTick": 1.0069,
                "reloadLoopBullet": 0.88,
                "reloadEndTick": 1.6875,
                "reloadCamera": [
                    "animation.weapon.reload_start_1round",
                    "animation.weapon.reload_start_empty"
                ],
                "reloadLoopCamera": [
                    "animation.weapon.reload_loop",
                    "animation.weapon.reload_loop_empty"
                ],
                "reloadEndCamera": [
                    "animation.weapon.reload_end",
                    "animation.weapon.reload_end"
                ]
            }
        ]
    ]
}
```

每一组的格式是：

```text
[本次装填数量, 模型循环状态, 本组换弹数据]
```

### 第一项：本次装填数量

例如第一组为 `5`，第二组为 `1`。选择依据是当前还需要装填的数量：

- 需要装填数量不少于 5 发：选择 5 发组。
- 需要装填数量不足 5 发：选择 1 发组。

因此剩余 8 发时会先使用 5 发组，剩余 3 发时再使用 1 发组；剩余 5 发时使用 5 发组；剩余 1 至 4 发时使用 1 发组。

### 第二项：模型循环状态

当前公共控制器约定：

- `2`：进入 `reload_loop1_empty` / `reload_loop2_empty` 分支，模型播放 `reload_loop_empty`。
- `1`：进入 `reload_loop1` / `reload_loop2` 分支，模型播放 `reload_loop`。

这里的数字是状态机信号，不是装填数量。通常 5 发组使用 `2`，1 发组使用 `1`。

### 第三项：换弹数据

常用字段：

- `reloadTacticalTick`：非空仓起始动作时长，单位为秒。
- `reloadEmptyTick`：空仓起始动作时长，单位为秒。
- `reloadTacticalBullet`：非空仓起始阶段的弹药提交时间。
- `reloadEmptyBullet`：空仓起始阶段的弹药提交时间。
- `reloadLoopTick`：循环装填动作时长，单位为秒。
- `reloadLoopBullet`：循环动作中的弹药提交时间，单位为秒。
- `reloadEndTick`：收尾拉栓或收尾动作时长，单位为秒。
- `reloadCamera`：起始相机动画。
- `reloadLoopCamera`：循环相机动画。
- `reloadEndCamera`：结束相机动画。

所有相机数组统一使用：

```text
[非空仓动画, 空仓动画]
```

不要使用反过来的顺序，否则动画可能看似能播放，但空仓和非空仓会出现明显姿态跳变。

## 换弹运行链

### 1. 开始换弹前锁定空仓状态

必须在第一发子弹提交前记录：

```text
started_empty = (当前弹匣子弹数 == 0)
```

建议保存为本次换弹的临时状态，例如 `_reloadStartedEmpty`。后续不能再通过 `nowBullet` 判断空仓，因为空仓换弹第一次提交子弹后，`nowBullet` 已经不为零，继续推断会错误选择非空仓动画。

### 2. 计算本次特殊换弹组

开始换弹时先检查背包和弹匣缺口，得到本次最多可装填数量。然后根据 `sequence` 选择 5 发组或 1 发组。

特殊组选择后，会将本组的计时字段写入当前枪械运行数据，并设置：

```text
v.tac.is_reload = 2   # 5 发组示例
v.tac.is_reload = 1   # 1 发组示例
```

公共换弹逻辑继续使用原有的 `reloadTick`、`reloadBulletTick`、`ReloadBullet()`、`ReloadLoop()` 和 `EndReload()`。

### 3. 起始动画完成后进入循环

起始阶段结束时：

1. 到达弹药提交点则提交子弹。
2. 起始计时归零后重新检查背包和弹匣缺口。
3. 仍然可以装填时进入 `ReloadLoop()`。
4. 没有可装填弹药时进入 `EndReload()`。

`ReloadLoop()` 再次按照当前剩余缺口选择 5 发组或 1 发组。这样一次 5 发装填完成后，如果只剩 1 至 4 发缺口，会自动切换为逐发装填。

### 4. 循环阶段选择相机动画

循环相机数组不应根据当前 `nowBullet` 选择，而应使用开始换弹时记录的空仓状态：

```text
非空仓：reloadLoopCamera[0]
空仓：reloadLoopCamera[1]
```

这是因为空仓换弹的第一发子弹可能已经在起始阶段提交，但本次动作仍然属于“空仓换弹”。

### 5. 结束换弹

当弹匣满、没有可用弹药或玩家主动中断时：

- 清除 `v.tac.is_reload`。
- 播放 `reloadEndCamera`。
- 执行原有的结束拉栓或收尾动作。
- 保持现有服务端弹药同步协议，不额外创建特殊网络协议。

## 计时字段的实际含义

当前公共代码使用 30Hz 计时，并对配置时间进行如下换算：

```text
内部弹药提交倒计时 = (动作总时长 - 配置中的提交时间) * 30 / ep_use_speed
```

因此配置中的 `reloadLoopBullet` 表示“动画开始后经过多少秒提交子弹”，不是剩余倒计时。

例如：

```text
reloadLoopTick = 2.3542
reloadLoopBullet = 1.5
```

表示动画开始约 1.5 秒时提交子弹。内部倒计时约为：

```text
(2.3542 - 1.5) * 30 = 25.626
```

起始动作中，如果提交时间大于动作时长，例如动作 2 秒、提交时间 3.5 秒，内部提交倒计时会是负数，表示起始阶段不提交子弹，进入循环阶段后再提交。这是可以接受的设计，但必须确认它是有意的。

### 计时填写建议

- 先读取动画实际长度，再填写 `reload*TacticalTick`、`reload*EmptyTick` 和 `reloadLoopTick`。
- `reload*Bullet` 填写动画开始后的实际提交秒数。
- 不要直接把“剩余倒计时”填写到 `reload*Bullet`。
- `ep_use_speed` 会同时影响动画和内部计时，测试时必须使用实际速度倍率。
- 不要为了补偿状态机延迟随意修改动画长度；先确认是动画长度、提交点还是状态切换问题。

## 模型动画与公共控制器适配

使用已有公共栓动换弹控制器时，枪械配置至少应提供以下模型动画别名：

```text
reload_tactical
reload_empty
reload_loop
reload_loop_empty
reload_end
reload_empty_end
```

通常的绑定关系为：

```text
reload_tactical  -> 枪械非空仓起始动画
reload_empty     -> 枪械空仓起始动画
reload_loop      -> 逐发装填模型动画
reload_loop_empty-> 压夹或循环装填模型动画
reload_end       -> 非空仓结束动画
reload_empty_end -> 空仓结束动画
```

相机动画和模型动画不是同一个层级：

- 模型动画由 `v.tac.is_reload` 和 `v.tac.reload_loop` 驱动。
- 相机动画由脚本在起始、循环、结束阶段分别播放。
- 空仓/非空仓的精确差异可以优先放在相机数组中，不必复制公共模型控制器。

如果一把枪使用的公共控制器不是 `state_2_loop_bolt`，先确认它对 `v.tac.reload_loop` 的约定，再决定第二项应该使用 `1` 还是 `2`。

## 动画首尾连续性

“起始动画完成后抽一下，再进入循环动画”通常不是换弹逻辑错误，而是两个动画的边界姿态不一致。

需要分别检查：

### 模型骨骼

起始动画最后一帧与循环动画第一帧至少应对齐：

- `root` 的位置和旋转。
- 右手位置和旋转。
- 左手位置和旋转。
- 枪栓、弹夹、子弹等可见部件。

### 相机骨骼

起始相机动画最后一帧与循环相机动画第一帧必须对齐：

- `camera` 旋转。
- `ep_camera` 旋转。
- 如有位置轨道，也要检查位置。

空仓和非空仓应分别比较：

```text
reload_start       -> reload_clip
reload_start_empty -> reload_clip_empty
```

如果只修正了非空仓链，空仓链仍可能在切换时抽动，反之亦然。

相机动画切换时，公共相机系统会结束前一个动作并以新动作的首帧继续播放，因此首帧偏移会直接表现为瞬间跳动。修复时优先调整枪械自己的动画资源，不要修改公共相机播放器。

## 枪械配置模板检查表

配置一把新枪前，依次确认：

1. `specialReload.type` 是 `a`。
2. `sequence` 至少有“多发组”和“单发组”。
3. 多发组的第一项是实际一次装填数量，例如 `5`。
4. 多发组第二项与公共控制器的压夹状态约定一致。
5. 所有 `reloadCamera`、`reloadLoopCamera`、`reloadEndCamera` 数组都是 `[非空仓, 空仓]`。
6. 每个动画名称在相机配置中都存在。
7. 每个模型动画别名在枪械的 `render.Animations` 中都存在。
8. `ep_state` 指向支持对应 `reload_loop` 信号的控制器。
9. `reloadType` 为 `1`，否则不会进入循环换弹逻辑。
10. 如果空仓也要进入特殊循环，不能让 `reloadEmptyMax` 把空仓分支强制改为普通换弹。
11. 弹匣容量、子弹类型和原有射击参数没有被特殊换弹配置覆盖。
12. 动画实际长度与 Tick 字段一致。

## 常见故障排查

### 空仓开始后直接结束，没有循环装填

优先检查：

- 是否进入了 `reloadType == 1`。
- 是否被 `reloadEmptyMax` 分支改成了普通空仓换弹。
- 特殊组的起始时间是否为负数或没有正确写入。
- `TestItemInBag()` 是否认为背包没有可用弹药。
- 起始阶段是否错误地把子弹提交点写成了一个不会命中的倒计时。

### 起始动画完成后直接进入结束动画

通常是逻辑链没有进入 `ReloadLoop()`：

- `reloadTick` 归零时 `TestItemInBag()` 返回 false。
- 弹匣缺口计算错误。
- `reloadType` 不是 `1`。
- 特殊组只提供了相机字段，但没有正确设置 `reloadLoopTick`。

### 逻辑正常，但起始和循环之间抽动

优先检查动画边界：

- 非空仓是否误用了空仓起始动画。
- `reload_start` 的末帧是否等于 `reload_clip` 首帧。
- 相机 `camera` 或 `ep_camera` 是否存在单轴偏移。
- 模型和相机是否使用了不同的空仓判断。
- 是否在同一时间重复播放了结束相机或其它动作相机。

不要先修改公共控制器或公共相机播放器。特殊枪械优先通过自己的配置和动画边界修复。

### 5 发完成后没有切换为逐发装填

检查第二组是否为：

```text
[1, 1, {...}]
```

同时确认下一轮选择依据是“剩余缺口”，而不是固定沿用上一轮的 5 发组。

### 空仓和非空仓动画反了

检查所有数组顺序。统一规定：

```text
[非空仓动画, 空仓动画]
```

另外确认本次换弹是否在第一发提交前缓存了 `started_empty`。

## 最小改动原则

为新枪接入 `specialReload` 时，推荐只做以下修改：

1. 在枪械配置中增加 `specialReload` 数据。
2. 补齐该枪自己的模型动画别名。
3. 补齐该枪自己的相机动画资源。
4. 复用已有 `GetSpecialReloadMini()`、`Special_A()`、`ReloadLoop()` 和 `EndReload()`。
5. 只有当公共代码不支持数组选择时，才在 `ReloadLoop()` 增加统一的数组选择辅助函数。

不要为单把枪增加专用的服务器协议、全局动画控制器或高频扫描逻辑。特殊枪械的差异应尽量留在配置和专属资源中。

## 最终验证

### 静态检查

- 配置 JSON 可以解析。
- 所有相机动画名称存在。
- 所有模型动画别名存在。
- Python 代码通过目标运行环境的语法检查。
- 5 发、5 发以下和 1 发三种缺口都能选到正确的序列。
- 公共控制器没有被无关改动。

### 游戏内检查

- 非空仓使用非空仓起始动画。
- 空仓使用空仓起始动画。
- 缺口不少于多发组数量时，先执行多发装填。
- 多发装填后能自动切换到逐发装填。
- 弹药只在提交点增加一次，不重复增加。
- 中断换弹不会残留 `is_reload`、循环信号或相机动作。
- 结束拉栓只在正确的换弹路径中出现。
- 起始到循环、循环到结束没有姿态抽动。

