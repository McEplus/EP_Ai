# Task recipes

## Add a setting option

1. Find the analogous page and template.
2. Add the default field and `SetLocalConfig` entry in `ChooseSettingSystem` when persistent.
3. Add a `ScreenRenderConfig` item.
4. Reuse a service action descriptor or add the smallest callback needed.
5. Confirm the business consumer reads or applies the value.
6. Run `trace_setting.py` and `check_screen_config.py`.

## Add a dynamic list

1. Choose an existing template or author one reusable JSON template.
2. Implement `BaseDataSource.GetItems()` or build configuration entries before render.
3. Select a layout and renderer.
4. Add only page-specific behavior through lifecycle hooks.
5. Verify render, refresh, selection, scroll bounds, and unRender cleanup in game.

Use `SelectionCard` with `LayoutConfig` and `afterCreateItem` as shown by SWS skin, cape, and emoji screens when the JSON template provides `NameLabel`, `Icon`, `TouchButton`, and highlight controls.

## Add a renderer

1. Define the required template suffixes.
2. Implement render, refresh, and destroy behavior without owning page layout.
3. Register the renderer on the page or shared registry.
4. Add a configuration example and update `config-schema.md` only for reusable fields.
