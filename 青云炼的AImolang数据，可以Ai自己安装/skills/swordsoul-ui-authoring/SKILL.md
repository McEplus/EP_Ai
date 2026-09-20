---
name: swordsoul-ui-authoring
description: Author, extend, analyze, harden, and review SwordSoul_NewERA_Fight and QingYunModLibs UI. Use for SWS UISystem Python, Bedrock/NetEase UI JSON, BaseScreenRenderCls or ConfigUI pages, administrator panels, settings persistence, HUD/input binding, dynamic or nested scrolling lists, modal layering, animations, cross-platform images, UI templates, renderers, layouts, native screen proxies, and UI development tools.
---

# SwordSoul UI Authoring

## Core direction

- Treat the existing SWS UI architecture as a proven runtime baseline. Extend its conventions; do not refactor merely to resemble another framework.
- Prefer configuration-driven UI through QingYunModLibs `ConfigUI` and SWS `BaseScreenRenderCls` patterns. Keep JSON responsible for containers, reusable visual templates, animations, and genuinely fixed layouts.
- Keep QingYunModLibs generic. Inject SWS settings, combat, skin, accessory, animation, and trail behavior through state stores, services, data sources, renderers, or lifecycle hooks.
- Keep development scripts under this skill. Never place analyzers, generators, caches, or reports in `src/` or `.build/`.
- Edit runtime source only under `src/`. Never synchronize `.build/dist` or reload the game unless the user explicitly asks.

## Workflow

1. Classify the task as a setting page, generic data list, HUD/input UI, editor screen, native proxy, or fixed JSON layout.
2. Read [architecture.md](references/architecture.md), then load only the relevant reference below.
3. Inspect existing setting, pause/native proxy, HUD, and UI-stack entries before adding a new entry. Reuse the user-designated entry.
4. Locate the Python module, `UIConfig` paths, UI JSON namespace/template, textures, registration entry, state store, business consumer, permission gate, scroll registrations, and persistence API.
5. Reuse `BaseConfigScreen` or `BaseSettingScreen` when repeated items share a template. Add a renderer or lifecycle hook before copying an entire `render()` implementation.
6. Preserve legacy five-field `ScreenRenderConfig` entries. Add optional schema fields only when the feature needs them.
7. For multi-page panels, modals, nested scroll views, platform images, runtime animation, or any UI touched by Tick/timers/events/RPC callbacks, read [runtime-ui-hardening.md](references/runtime-ui-hardening.md) and apply its verification matrix.
8. Run the relevant scripts from `scripts/`; treat their output as development guidance, not as a substitute for in-game verification.
9. Compile edited runtime Python where Python 3 parsing is applicable, validate JSON, inspect `git diff`, and report the manual hot-reload checks without performing reload.

## Reference routing

- Read [qingyun-config-ui.md](references/qingyun-config-ui.md) for base classes, renderers, layouts, data sources, state stores, services, and lifecycle hooks.
- Read [config-schema.md](references/config-schema.md) when authoring or validating `ScreenRenderConfig`.
- Read [sws-ui-integration.md](references/sws-ui-integration.md) for `ChooseSettingSystem`, `FightUISystem`, input, settings, and project boundaries.
- Read [ui-json.md](references/ui-json.md) when editing UI JSON, namespaces, template controls, or textures.
- Read [task-recipes.md](references/task-recipes.md) for ordered recipes such as adding a Toggle, Slider, list page, renderer, or template.
- Read [editor-and-native.md](references/editor-and-native.md) for complex editors, drag workflows, import/export, and native ScreenProxy tasks.
- Read [runtime-ui-hardening.md](references/runtime-ui-hardening.md) for composite administrator screens, visual proportions, modal layer bands, nested scroll isolation, persistence value types, platform-image fallbacks, helper namespaces, and end-to-end verification.
- Read [ui-animation-agent.md](../../agents/common/ui/ui-animation-agent.md) before adding or changing entrance, exit, content-transition, alpha, hover, press, or runtime-cloned control animations.

## Tool routing

- Run `python .codex/skills/swordsoul-ui-authoring/scripts/ui_inventory.py` to list UI Python/JSON assets and configuration-driven screens.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/trace_setting.py <SettingId>` to trace a setting across defaults, persistence, screen config, callback, and consumers.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/trace_ui_path.py <PathOrName>` to find Python and JSON occurrences of a control path or constant.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/check_screen_config.py [file]` to check configuration dictionaries and registered control types.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/check_ui_change.py` to summarize UI-related files in the current Git diff and their related surfaces.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/list_ui_templates.py` to find reusable JSON template candidates and explicit template registrations.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/generate_config_screen.py <ClassName>` to print a draft without writing into the game source tree.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/validate_ui_json.py` and `validate_ui_paths.py` to check resource definitions and UIConfig contracts.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/trace_input.py <Action>` or `audit_input_bindings.py` for HUD/input work.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/audit_ui.py --strict` for the complete offline gate, then `test_config_ui.py` for runtime composition tests.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/test_scroll_physics.py` after changing QingYunModLibs scrolling, inertia, or boundary rebound behavior.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/test_tutorial_animation.py` after changing tutorial entrance, exit, content-transition, or button-feedback animations.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/test_main_setting_animation.py` after changing MainSetting interaction animation observers, centered button feedback, or callback-preservation behavior.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/test_announcement_animation.py` after changing announcement entrance, exit, version selection, read-lock, or return-to-setting behavior.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/test_team_system_animation.py` after changing the team administrator UI entrance, exit, tabs, dynamic lists, modals, or button feedback.
- Run `python .codex/skills/swordsoul-ui-authoring/scripts/delivery_check.py` before handoff to verify the complete source/knowledge deliverable.

## Composite UI hardening checkpoints

- Separate visual layering from input routing. A high modal layer does not automatically stop a Python-registered background scroll view.
- Suspend overlapping background scroll registration while a foreground modal scroll is active, then restore exactly one registration after close.
- Keep ordinary list content top-aligned and judge button/content proportions at the user's real GUI scale.
- Treat vertical centering as optical alignment, not equal coordinates: compare the visible glyph center with the companion value, icon, or toggle center in an actual-scale runtime screenshot, then compensate the label Y offset after finalizing font scale.
- Use only officially documented engine/UI APIs. Provide deterministic fallbacks for platform-limited image features and never expose an empty dynamic image layer.
- Verify engine persistence value types before saving complex UI state; serialize containers when the documented API requires a scalar.
- Qualify UI runtime helpers through their defining module. Syntax compilation alone does not catch runtime `NameError` from an unresolved global.
- Treat ScreenNode existence and control-tree readiness as separate states. Tick, timer, event, RPC, combat/AI, and delayed animation paths must pass an explicit create-complete gate before any control lookup or UI write.
- Guard readiness at both the high-frequency business entry and the lowest-level visual helper; re-check inside asynchronous callbacks, close the gate before destroy/rebuild, and never cache a missing control returned before creation completes.

## Runtime boundaries

- Put generic runtime capabilities in `SwordSoulFightScripts/QingYunModLibs/ConfigUI/`.
- Put SWS adapters in `SwordSoulFightScripts/UISystem/ConfigUI/`.
- Do not make generic QingYunModLibs modules import `ChooseSettingSystem`, `FightUISystem`, or other SWS business modules.
- Keep client UI registration and `@Screen`-style behavior out of Mob server state libraries.
- Preserve Python 2-compatible syntax in NetEase runtime modules; do not use dataclasses, annotations, f-strings, or Python 3-only collection syntax.

## Resource image scaling compatibility

- Treat `MainSetting.json` as the compatibility baseline for adaptive NetEase UI images in this project.
- Treat ordinary UI textures as stretchable by default. Full-bleed backgrounds, solid or simple gradients, masks, dividers, progress fills, and selection bars should set `keep_ratio: false` so they follow the control size.
- Preserve aspect ratio only for complex authored artwork whose composition must not distort, such as icons, illustrations, portraits, book art, and decorative emblems.
- Use the legacy nine-slice path (`is_new_nine_slice: false` or `$is_new_nine_slice: false`) for stretchable textures that have corners, borders, or button-frame details that must be protected. Retain the matching legacy variables and follow a verified `MainSetting.json` example of the same control/template type.
- For `common.button`, remember that the button size and its inherited `default`, `hover`, and `pressed` image sizes are separate. When those state textures are ordinary stretchable images, override all three inherited image controls with `keep_ratio: false`; otherwise a rectangular button may render a centered square texture.
- Do not diagnose editor selection outlines as runtime textures. Establish the selected control path before changing nearby panels or progress bars.
- When creating or reviewing a resource UI, audit every image-bearing control and inherited texture template at more than one aspect ratio; do not assume percentage `size` alone makes the texture adaptive.

## Runtime UI animation compatibility

- `SetCompScaleAnimation` changes control size around its `anchor_from`; it does not guarantee visual-center scaling. For buttons whose anchor is not `center`, animate local position together with size using half-size-difference compensation, or animate a verified center-anchored visual child.
- Measure runtime-cloned controls only after their size is assigned and `UpdateScreen()` has completed. Never cache near-zero pre-layout dimensions as animation baselines.
- Reject invalid animation baselines, cancel superseded per-control timers, and clean repeating animation timers when dynamic controls or their screen are destroyed.
- Alpha animation propagation is recursive. Set `propagate_alpha: true` on the animated control and every descendant or intermediate control with children down to the visible labels, images, inherited button states, scroll content, and progress controls. Treat any undocumented node with `controls` that breaks this chain as an animation defect.
- Cache size and position immediately before the animation that consumes them. A parent entrance, move, scale, grid rebuild, scroll registration, or `UpdateScreen()` invalidates previously cached descendant metrics.
- Do not enable descendant hover/press animation while a parent entrance animation is still moving. Finish the parent animation, update layout, then lazily capture the descendant baseline on the first real interaction event.
- Do not animate a dynamic grid or scroll child's absolute position while an ancestor is moving. Its global target will become stale and be converted into an incorrect local offset. Prefer parent motion plus alpha-only child staggering unless local-coordinate motion is explicitly verified.
- For runtime-cloned buttons, validate final dimensions, retry briefly when layout is unresolved, animate visual children instead of the root hitbox, and ignore unmatched initialization events such as `HoverOut` without `HoverIn`.

## Runtime scroll compatibility

- `CreateScroll_View` now resolves collision bounds in the scrolling content's local coordinate space. Do not compensate for a viewport's parent-space position by giving a grid a negative `point_y`, giving the scroll view a negative `BoxOffset`, or moving the content root after registration.
- A vertical scroll view should normally start with its first item at local `point_y: 0` and use the default `BoxOffset=(0, 0)`. Use a positive `point_y` only when the design intentionally needs inner top padding.
- Keep viewport placement separate from content placement. Percentage or pixel offsets on the scroll-view control can position the viewport, but must not be copied into the content grid or collision range.
- After migrating an old custom scroll view, run `test_scroll_physics.py`; its source checks cover the historical MainSetting, AnimateScreen, TrailScreen, and Announcement compensations.
