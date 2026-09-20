# UI JSON and templates

- Keep resource UI JSON under `src/SwordSoul_NewERA_R/ui/` and textures under `textures/ui/`.
- Prefer a small template vocabulary over repeated full item trees: setting option, selection card, image card, editable card, section title, text input row, and vector edit row.
- A ConfigUI template is a Python suffix map over one JSON template root. Renderers depend on suffix names such as `label`, `button`, `toggle`, `slider`, and `value`.
- Update `_ui_defs.json` when adding a new UI definition file that the resource pack must load.
- Keep Python `UIConfig` paths synchronized with static JSON paths. Runtime clone paths and native screen paths are exceptions and should be documented rather than forced into static validation.
- Do not edit JSON merely to add another identical row; add a configuration item when the existing template already expresses the visual form.

## Adaptive texture rules

- Ordinary UI textures are stretchable unless they contain a complex authored composition. Use `keep_ratio: false` for solid-color/full-panel images, simple gradients, masks, rules, dividers, progress fills, and selection strips.
- Preserve ratio for complex semantic artwork such as icons, character images, book illustrations, and decorative emblems; fit those through layout instead of distortion.
- Follow a verified `MainSetting.json` example when a stretchable texture has corners, borders, or button-frame details that require legacy nine-slice (`is_new_nine_slice: false` / `$is_new_nine_slice: false`). Do not infer that every stretchable texture needs nine-slice.
- Inspect inherited template variables as well as explicit `type: image` nodes. A button may contain no local image node while still selecting its scaling behavior through `$is_new_nine_slice`.
- A rectangular `common.button` can still show a square background because its inherited `default`, `hover`, and `pressed` images preserve ratio independently. Override `keep_ratio: false` on every stretchable state image, not only on the button root or one state.
- UI editor selection borders and resize handles are diagnostic overlays, not runtime textures. Identify the selected control before attributing those lines to a neighboring image or composite.
- Before handoff, check wide and narrow window ratios in game for stretched corners, letterboxing, uncovered panel edges, and displaced selection strips.
