# 静态渲染资源

## 核心概念

- 静态资源按实体类型注册，不按单个 `entityId` 注册。
- 配置入口优先使用类和装饰器，避免直接 import 字典变量导致热更困难。
- 重复注册同一个 actorIdentifier 视为热更：应重新加载资源并重载渲染控制器。

## 常见资源字段

- `geometry`
- `texture`
- `material`
- `animation`
- `animation_controller`
- `script_animate`
- `render_controller`
- `molang`
- `remove_animation_controller`
- `render_params`

## 加载时机

- `UiInitFinished` 触发一次加载。
- `AddEntityClientEvent` 第一次遇到实体时再触发一次加载。
- 修改实体静态资源后，需要重载实体资源和渲染控制器，否则可能不生效。

## 原版控制器处理

- 有些原版动画控制器不是 `script_animate` 注册的，必须真的移除。
- 僵尸抬手优先检查 `zombie_attack_bare_hand` 和 `attack` 控制器。
- 不确定控制器作用时，先小范围移除并测试，不要一次删掉全部人形控制器。

## Molang

- 所有要 `SetMolang` 的 query 都必须先注册。
- 如果设置无效，优先检查：是否注册、是否加载两次、是否重载渲染控制器、是否 actorIdentifier 写错。
