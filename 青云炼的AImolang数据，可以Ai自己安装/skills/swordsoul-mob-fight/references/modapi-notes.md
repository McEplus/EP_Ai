# 网易 ModAPI 注意事项

## 查询原则

- 不确定的 API 必须查网易官方文档或项目内封装。
- 官方文档链接优先使用 `https://mc.163.com/dev/mcmanual/...`。
- 项目内封装优先查 `QingYunModLibs/ServerApi`、`ClientApi`、`RenderSystem`。

## 禁忌

- 禁止使用 `importlib`。
- 服务端业务模块优先使用 `from ..QingYunModLibs.ServerMod import *` 或对应相对路径导入核心 API。
- 客户端业务模块优先使用 `from ..QingYunModLibs.ClientMod import *` 或对应相对路径导入核心 API。
- 例外：纯配置/纯注册类、封装库内部文件、会触发循环导入或服务端/客户端环境冲突的模块。
- 不要把 `SetBlockControlAi` 当作招式期间的移动锁。它可能冻结动作和 `SetMotion`，不适合当前战斗状态机。
- 不要把 `entityId` 和实体类型混用。

## SetBlockControlAi 记录

- 该接口可以屏蔽生物原生 AI，但副作用很强。
- 战斗状态里暂不使用它；需要新方案时必须重新设计并测试动作、重力、`SetMotion`、碰撞和寻路行为。

## SetMotion 瞬时向量

- 网易官方接口把服务端 `SetMotion` 定义为生物的“瞬时移动方向向量”；服务端 `GetMotion` 会体现摩擦等物理因素，不能把设置值理解为匀速保持到下一次计时器。
- 禁止用 `power * 持续秒数` 推断游戏实际格数。一次设置后会继续受阻力、碰撞和台阶影响；需要复现动画完整根位移时，应按状态时钟以 20Hz 写入相邻样本的单 tick 格位移。
- BB/actor 的 `root_move.position` 是累计模型空间位置。标准模型常用 `16 模型单位 = 1 格`，仍需先核验目标几何和导出链，不能把模型单位直接传给 `SetMotion`。
- 监守者/铁傀儡的 `0.00527` 是物种与招式已标定配置，不是 ModAPI 单位换算常量。新生物必须重新建立位移证据。
- 高频修改本地玩家瞬时向量还涉及官方提示的客户端/服务端同步与反作弊风险；当前 Mob 服务端逐 tick 根位移方案不得无审计地复制到玩家移动。

## 原版移动/转向组件开关

- 当前用于“招式期间不让实体自己走路和转头”的方案是动态删除/恢复实体 json 组件。
- 已验证需要优先处理的组件：
  - `minecraft:movement`
  - `minecraft:movement.basic`
  - `minecraft:navigation.walk`
  - `minecraft:behavior.look_at_player`
  - `minecraft:behavior.random_look_around`
- 进入具体招式时删除这些组件，退出招式时按实体子类提供的原始配置加回。
- 不要修改或依赖 `component_groups` 来恢复这套原版控制组件。
- `AddActorComponent` 恢复组件时第二参需要传 json 字符串，不能直接传 Python dict。
- 特殊招式如果需要自动索敌转向，可以临时调用 `self.PlayerRootController.SetMoveState(True)` 或 `SetNativeControlState(True)` 打开；不需要时再传 `False`。

## 文档验证

- 涉及渲染资源、Molang、实体行为、服务端组件时，优先查官方文档。
- 如果文档语义与实测冲突，以实测记录为准，并把结论写入本 reference。
