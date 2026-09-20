# 项目结构

## 主要目录

- `src/SwordSoul_NewERA_B/SwordSoulFightScripts`：玩家 SWS 战斗系统，是 Mob 战斗复用源。
- `src/SwordSoul_NewERA_B/SwordSoulMobFightScripts`：实体战斗系统，新增代码优先放这里。
- `src/SwordSoul_NewERA_R`：资源包内容，包含模型、动画、动画控制器等渲染资源。

## Mob Fight 目录职责

- `Core/`：实体访问、常量、注册、武器类型解析等底层能力。
- `Combat/`：战斗状态机、招式控制器、条件判断、SWS 服务端桥接。
- `Entities/`：具体实体类型，例如僵尸；这里注册实体特有状态。
- `Render/`：实体静态资源加载、热更、Molang 和渲染状态同步。
- `AI/`：后续实体战斗 AI/仲裁逻辑。
- `QingYunModLibs/`：项目封装库，优先复用，不随意重构。

## 初始化关系

- 每个实体实例都有自己的 `entityId` 和状态实例。
- `entityType/actorIdentifier` 用于同一种族的静态资源、状态覆盖和注册。
- `fight_controller` 需要早于 `fight_state_system` 绑定到状态上，因为状态里的 `PlayerRootController` 指向它。

## 编辑边界

- 尽量只改与当前需求直接相关的文件。
- 不整理无关格式，不重排大段旧代码。
- 非必要少写 `try/except`；不要用裸 `except` 掩盖 ModAPI、状态机或渲染加载的真实错误。
- `.build/dist`、IDE 文件、用户调试输出等若非任务要求，不主动清理。
