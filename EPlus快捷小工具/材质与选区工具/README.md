# EPlus 材质与选区工具

## 快速使用

双击根目录的 **pbr-mask-batch.html**。拖入基础图 `a.png` 和纯色选区图 `a_color_mask.png`，或拖入整个文件夹，再批量生成并导出。HTML 自带依赖，不需要服务器或联网。

完整说明见 [批处理工具说明](tools/mask-batch/README.md)。

## 文件用途

| 位置 | 用途 | 游戏运行是否需要 |
| --- | --- | --- |
| pbr-mask-batch.html | 可独立分发的美术批处理工具 | 否 |
| tools/mask-batch | HTML 源码和开源依赖许可 | 否 |
| tools/*.py | 离线生成、审计、重建、shader 验证 | 否 |
| tests | 材质算法与界面回归测试 | 否 |
| docs/pbr-mask-audit | 历史实验、迁移和验证报告 | 否 |
| assets/environment/eplus_pbr.png | 制作环境贴图的源全景图 | 否 |
| .cache/pbr-tool-deps | 开发测试用 Playwright 依赖，HTML 不使用它 | 否 |
| tool-settings.json | Python 工具定位主包和工作区的配置 | 否 |

真正运行所需的 shader、正式选区图、`eplus_pbr_prefilter.png`、`pbrMaskRender.py` 和 `pbrMaskResources.py` 均保留在 MOD 内。

## 备份清理与重建

前置包及各扩展包的 `tools/pbr-mask-sources` 已按要求清理，历史源图通过 Git 取回。工具不再自动创建备份目录。

离线细节算法只从选区图读取 RGB 的区域身份和 alpha，从基础图计算细节；因此命令行 `--rebuild` 可以用现有生成图的区域身份重建。美术重新绘制时仍可直接制作纯色选区图。

## 开发维护

修改 `tool-settings.json` 的 `mod_root`、`workspace_dir` 可切换项目；也可使用环境变量 `EPLUS_MOD_ROOT`、`EPLUS_WORKSPACE_DIR`。

- Python 3 + Pillow：`python -B tools/build_mask_tool.py` 重新打包 HTML。
- Python 3 + Pillow：`python -B tools/audit_pbr_masks.py` 生成工具目录内的资源报告；加 `--write-index` 才更新 MOD 中的运行时索引。
- Python 3 + Pillow：`python -B tools/rollout_detail_masks.py --apply --rebuild` 批量重建选区图，不创建备份。
- Python 2.7：`python -B tests/test_pbr_mask_material.py` 检查 MOD 配色与材质参数链路。
- Python 3 + Pillow：`python -B tests/test_basp_detail_mask.py` 检查离线算法。
- Windows Python 3 + Pillow：`python -B tools/check_pbr_mask_gl.py` 检查桌面 GLSL，附加 `fast` 或 `balance` 切换模式。
- Python 3 + Playwright：`python -B tests/test_mask_batch_browser.py` 验证本地 HTML。完成后可删除工具目录 `.cache/mask-tool` 中的截图与临时图片。

历史报告中涉及旧备份路径和旧测试贴图的内容仅作历史记录，当前操作以本文件和工具源码为准。迁移清单见 `cleanup-manifest.json`。
