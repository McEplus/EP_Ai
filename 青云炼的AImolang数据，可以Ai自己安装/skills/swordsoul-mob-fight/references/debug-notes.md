# 调试记录

## I 键调试

- 客户端按 I 后会向服务端发送尸壳攻击调试指令；尸壳不会白天燃烧，作为第一个 demo 目标更稳定。
- 曾用于打印 `query.mod.fight` 调用前和调用后 1 秒的值。
- 若再次调试 Molang，先确认 `BaseApi.SetMolang/GetMolang` 的参数和实体 ID。

## 常见问题

- `SetMolang` 没有效果：先查 Molang 是否注册，再查资源是否加载，最后查渲染控制器是否重载。
- 招式状态进入但动画不动：查 `query.mod.fight`、`query.mod.attack_state`、动画控制器条件和原版控制器冲突。
- 实体初始化报 `fight_controller` 不存在：检查 `BaseMob` 初始化顺序，`fight_controller` 要早于状态绑定。
- 状态复制后报 `playerId` 不存在：检查 Mob 状态绑定是否同步了 SWS 全局 `playerId`。

## 验证命令

```powershell
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Combat\FightController.py
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Combat\FightStateSystem.py
python -m py_compile src\SwordSoul_NewERA_B\SwordSoulMobFightScripts\Entities\ZombieMob.py
```

## 移动端渲染优化经验

- Bloom 不必优先删 Pass，但“总能量相等”不能单独证明视觉等价：中心加四个纯对角 tap 容易产生菱形薄光晕；中心加六方向环形 tap 在 7 次采样下能获得更均匀的扩散，同时比原 9 次采样低 22.2%。
- 手机端高光提取缓冲对细线效果很敏感；0.75～0.8 倍可能过度损失刀光连续性，优先使用 0.9 倍作为保真折中。
- 评估 Bloom 性能不能只数 Shader 源码里的 `texture()`：应按每个 Pass 的 Render Target 面积乘采样次数计算全分辨率等效预算，并单独计入读写带宽、Pass 切换和移动 GPU 缓存局部性。
- 后处理的深度重建、矩阵求逆、色散和额外采样应放进 uniform/遮罩分支。对应功能关闭或像素不在标记区时，不能继续用 branchless `step/mix` 让昂贵路径照常执行。
- `// __multiversion__` Shader 要兼顾旧 GLSL ES：避免 C 式数值 `f` 后缀和 `int(gl_FragCoord) & 1`，像素奇偶改用 `mod(floor(gl_FragCoord), 2.0)`。
- 玩家残影不能复制当前高面数皮肤 geometry；使用固定低模 geometry，并在移动端同时限制透明残影数量，才能控制三角形和 overdraw 两个维度。
