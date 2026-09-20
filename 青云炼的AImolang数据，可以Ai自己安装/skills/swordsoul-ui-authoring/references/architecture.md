# UI architecture

## Layers

1. Resource UI: `src/SwordSoul_NewERA_R/ui/*.json` and `textures/ui/**` provide namespaces, containers, reusable templates, fixed compositions, and sprites.
2. SWS business UI: `SwordSoulFightScripts/UISystem/*.py` owns settings, HUD, editors, announcements, skins, accessories, and native proxy integration.
3. QingYunModLibs UI runtime: `QingYunModLibs/UIScreen.py` supplies control access, cloning, grids, scrolling, buttons, toggles, sliders, and screen registration.
4. ConfigUI runtime: `QingYunModLibs/ConfigUI/` composes those primitives into configuration-driven pages without importing SWS business.
5. SWS adapters: `UISystem/ConfigUI/` connects generic state stores and services to `ChooseSettingSystem` and other SWS components.
6. Development layer: `.codex/skills/swordsoul-ui-authoring/scripts/` performs read-only discovery and change checks outside game packages.

## Default decision

- Use ConfigUI when a page contains repeated entries based on one or a small number of templates.
- Use static JSON for unique composition, animation-heavy presentation, native UI injection, or layouts whose children are not data-driven.
- Use a custom renderer when an item has a reusable structure but non-standard binding.
- Use lifecycle hooks when only a small part of page behavior is special.
- Override the full render flow only when layout or interaction cannot be represented by the existing strategies.

## Existing SWS anchors

- `UISystem/MainSetting.py`: compatibility `BaseScreenRenderCls` over ConfigUI and main setting lifecycle.
- `UISystem/GeneralScreen.py`: five-field setting configurations.
- `UISystem/SettingData.py`: `ChooseSettingSystem` defaults, persistence, and apply callbacks.
- `UISystem/Control.py`: combat HUD and input translation.
- `UISystem/UIConfig.py`: Python control-path constants.
- `QingYunModLibs/UIScreen.py`: runtime primitives used by ConfigUI.
- `UISystem/SkinUI.py`, `CapeUI.py`, `EmoteUI.py`: configuration-driven multi-column card examples.
