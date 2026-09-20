# 选区材质工坊

直接打开工具包根目录的 **pbr-mask-batch.html**。这是可独立分发的单文件，不需要 Python、服务器或网络，推荐使用当前版本的 Chrome / Edge。

## 美术工作流程

1. 继续绘制纯色选区图：红、绿、蓝、黄、品红表示五区，alpha 表示金属度；不要在美术源图上手工绘制细节系数。
2. 基础图命名为 `a.png`，选区源图为 `a_color_mask.png`，放在同一目录。
3. 将两张图或整个文件夹拖入 HTML，也可以选择“添加文件”或“添加文件夹”。
4. 点击“批量生成”。选择文件后可查看选区、纯白、中灰、红色预览，以及单个选区的结果。
5. 下载单张结果或导出 ZIP。生成图仍叫 `a_color_mask.png`，用它替换对应资源包中的运行时选区图；基础图不变。

纯色源图由美术自行维护，也可以从 Git 历史取回。各项目曾经自动创建的 `tools/pbr-mask-sources` 已按要求清理，工具不再创建此类备份目录。

## 文件处理规则

- 先按相对目录及文件名配对，不将不同子目录的同名贴图混在一起。
- 缺基础图、同名冲突和损坏 PNG 会显示在队列中，不猜测配对对象。
- 两张图尺寸不同时，按归一化 UV 的像素中心采样基础图。保留选区尺寸并显示提示，不拉伸/重画选区图；这不修复本来就错位的 UV。
- 输出为无损 RGBA8 PNG。五区身份、alpha 及未选区像素保持不变；透明像素中的 RGB 不经过 Canvas 读回。
- 输出包含 `EplusMaskVersion=detail-v1` 标记，重新导入已处理图时保留原字节，不重复生成。
- 支持普通灰度、RGB、调色板、RGBA PNG；拒绝动画 PNG、16 位 PNG和超过 4,194,304 像素的单张图。
- 预览只表示无光照基础颜色，不包含游戏 PBR、反射、阴影。
- 大批量计算在 Worker 中运行，可停止并保留已完成结果。ZIP 默认保留目录；取消后如存在同名文件，会阻止覆盖式导出。

## 算法与维护

算法与已经验证的 basp_tf 版本一致：离线提取对数亮度残差，RGB 强度存放细节，RGB 比例保留选区身份，alpha 保留金属度。游戏只需 `目标颜色 × 细节系数`，无新增采样或 pass。

- `core.js`：浏览器算法和无损 PNG 输出；PNG 解码采用固定版本 UPNG。
- `app.js` / `template.html`：界面与队列。
- `../pbr_mask_core.py`：Python 批量算法。
- `../build_mask_tool.py`：将源码、固定版本依赖和许可证打包到单个 HTML。
- `../rollout_detail_masks.py --apply`：从 EP 工作区批量转换，不自动创建备份；`--apply --rebuild` 使用当前基础图和现有选区身份重建，不依赖备份目录。

命令行工具通过根目录的 `tool-settings.json` 定位主 MOD 和 EP 工作区。迁移、换机器后修改这两个路径即可；HTML 独立使用时不读取此配置。审计默认只写工具目录报告，只有显式指定 `audit_pbr_masks.py --write-index` 才更新 MOD 内运行时索引。

验证脚本：`tests/test_mask_batch_browser.py`、`tests/test_basp_detail_mask.py`、`tools/verify_detail_rollout.py`。浏览器测试依赖 Playwright，工具使用者不需要安装它。

第三方库版本及许可：UPNG 2.1.0（MIT）、pako 1.0.11（MIT / Zlib）、JSZip 3.10.1（MIT 可选）、Lucide 0.468.0（ISC）。完整许可证保存在 vendor 目录，并嵌入单文件 HTML。
