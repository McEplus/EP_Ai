# EPlus · 模型快捷导入

把 Blockbench `.bbmodel` 转成基岩版模型、动画和 PNG 贴图，直接写入指定项目。纯离线网页，无需安装 Python、Node.js、Blockbench 或运行服务，也没有 CDN / 网络依赖。

## 开始使用

1. 双击 **启动工具.cmd**，或用桌面版 **Microsoft Edge / Google Chrome** 打开 **index.html**。
2. 点击 **选择项目文件夹**。页面已经预填你的项目路径；点击旁边的复制按钮，在系统选择窗口按 `Ctrl+L`，粘贴路径并回车，再确认文件夹。
3. 工具会根据 `manifest.json` 自动识别项目根目录下的资源包。也可以直接选中资源包本身。多个资源包时，在下拉框里选择目标资源包。
4. 设置三个输出目录，均相对于**实际授权的项目文件夹**。可以手填新目录，或点击 `…` 选择已有子文件夹。
5. 拖入一个或多个 `.bbmodel`。缺少标识符时，先在卡片里填写，例如 `geometry.ep.lockpick_gun`。也接受 `ep.lockpick_gun`，会自动添加 `geometry.` 前缀。不会替你猜测或默认生成标识符。
6. 查看文件清单，点击 **预检并导入**，核对具体文件后点击 **写入项目**。

浏览器不能仅凭一段 `D:\...` 文本取得文件写入权限，所以第一次必须通过文件夹选择窗口授权。路径文本用于定位；实际写入目标以绿色的“已授权文件夹”及确认清单为准。关闭网页后，再打开需要重新授权目录。

默认资源包路径：

| 内容 | 默认相对目录 | 输出文件 |
| --- | --- | --- |
| 模型 | `resource_pack_EP_JXK_21/models/entity` | `ep.lockpick_gun.geo.json` |
| 动画 | `resource_pack_EP_JXK_21/animations` | `ep.lockpick_gun.animation.json` |
| 贴图 / 材质图像 | `resource_pack_EP_JXK_21/textures/entity` | `ep.lockpick_gun.png` |

输出文件名来自模型标识符。无动画时只输出模型和贴图，不生成空动画文件。

## 换电脑使用

解压 **EPlus模型导入工具-便携版.zip**，双击其中的启动脚本即可。也可以直接复制包含 `index.html`、`styles.css`、四个 `.js` 和启动脚本的整个文件夹。

- 本机浏览器会记住路径配置；“导出路径配置 / 载入配置”可迁移这些设置。
- 另一台电脑需重新选择项目文件夹，路径不同则修改配置。
- 浏览器不支持目录写入时，可以 **导出 ZIP**。ZIP 内的目录结构与页面预览一致，解压到项目根目录即可。ZIP 同时包含导入报告。
- ZIP 是普通资源包文件集合，不是 `.mcpack`，不会自动安装到游戏。
- 文件、贴图、路径均在本机处理，不会上传。

## 当前支持范围

- Blockbench 3–5 的未压缩 JSON `.bbmodel`；包括两个样例使用的 **5.0 groups / outliner 分离结构**，以及旧版本内联骨骼结构。
- 立方体、嵌套骨骼、旋转、pivot、inflate、Box UV、逐面 UV、镜像和定位器。
- 正确处理 Blockbench → Bedrock 的 X 坐标、X/Y 旋转符号、上下表面 UV 方向。PNG 像素尺寸和模型 UV 分辨率分别保留。
- 单张实际使用的内嵌 PNG。源文件中的未使用贴图会提示并略过；PNG 不重新压缩。
- 骨骼 position / rotation / scale 动画、loop / hold、长度、覆盖标志、动画时间表达式、线性 / 阶梯 / Catmull-Rom 插值、pre / post 数据点、效果事件。
- 静态模型预览，可拖动旋转、滚轮缩放。预览用于辨认素材，不是游戏渲染器，不播放动画。
- 批次内重复标识符、输出路径冲突，以及选中资源包 `models` / `animations` 和指定模型 / 动画输出目录内的已有标识符检查。扫描不跨越其他资源包。

为避免静默丢失资源，本版会拦截网格、多贴图混用、旋转 UV、分层贴图、Bezier / 四元数动画、动画控制器、需要更新格式的 bone binding 等不支持的内容。可先在 Blockbench 中整理为单贴图 Bedrock 立方体模型，或烘焙为线性动画，再导入。

“材质图像”在本工具中指模型内嵌的 PNG。bbmodel 不是游戏着色器文件，本工具不生成 `.material` 着色器定义。当前只负责资源转换和落盘，不创建物品、实体、attachable、渲染控制器或动画引用绑定。效果事件里的粒子和声音短名称需要在项目里已有相应绑定。

## 同名文件与备份

默认拒绝覆盖已有文件。确实要更新时，勾选 **允许替换同名文件**：

- 确认窗口逐个列出新建 / 替换的路径。
- 所有旧文件先备份到 `.bb-import-backups/时间戳/原相对路径`，然后才开始写入目标文件。
- 每个写入文件都逐字节回读验证；写入失败时尝试恢复原文件并移除本次新文件，回滚失败会显示具体路径。
- 预检后目标文件若被其他软件改动，会中止写入，要求重新预检。
- 包含其他资源标识符的同名合并 JSON 会阻止替换，避免覆盖同文件内的其他资源。

需要恢复时，将备份目录中的原文件按相对路径复制回项目。`backup-info.json` 记录了本批次哪些是新建文件；新建文件没有旧版本可恢复。浏览器进程被强制结束或突然断电无法自动回滚，可使用备份手动恢复。

## 验证与维护

两个原始样例均缺少标识符且没有动画。测试使用 `geometry.ep.lockpick_gun`、`geometry.ep.lockpick_tools` 作为示例标识符；它们不是对你的正式资源命名的替代。

| 样例 | 立方体 | 骨骼 | PNG 像素 | UV 分辨率 |
| --- | ---: | ---: | --- | --- |
| 开锁枪 | 62 | 2 | 64 × 64 | 32 × 32 |
| 撬锁工具 | 83 | 2 | 128 × 128 | 64 × 64 |

开发用测试（使用 Node.js 20 或更新版本；普通使用无需安装）：

```sh
node tests/run-tests.mjs
```

浏览器集成测试：在本目录运行任意本地静态服务器，然后打开 `tests/browser-check.html`。测试驱动真实页面，使用内存文件系统替身验证选择项目、文件导入、标识符、路径检查、确认清单、写入及备份流程；不会写入你的真实游戏项目。`?preview` 可保留模型预览用于截图。测试不能代替操作系统文件夹授权与游戏内渲染验收。

源码分工：`converter.js` 转换，`project.js` 预检 / 写入 / ZIP，`preview.js` 静态模型预览，`app.js` 页面交互。`tools/package.py` 可重新生成便携 ZIP（仅开发打包时需要 Python 3）。

格式核对参考：

- [Microsoft：Bedrock Geometry 1.12.0](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_geometry_1.12.0?view=minecraft-bedrock-stable)
- [Microsoft：Actor Animation 1.8.0](https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_actor_animation_1.8.0?view=minecraft-bedrock-stable)
- [Blockbench：Bedrock 格式实现](https://github.com/JannisX11/blockbench/blob/master/js/formats/bedrock/bedrock.js)
- [Blockbench：Bedrock 动画实现](https://github.com/JannisX11/blockbench/blob/master/js/formats/bedrock/bedrock_animation.js)

转换器是本项目独立实现，无运行时依赖，也不包含 Blockbench 应用程序。
