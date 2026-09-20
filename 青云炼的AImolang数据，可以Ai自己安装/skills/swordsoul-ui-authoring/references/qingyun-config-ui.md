# QingYunModLibs ConfigUI

## Components

- `BaseConfigScreen`: render configuration items, build layout, bind renderers, keep runtime item maps, refresh conditions, and clean up.
- `BaseSettingScreen`: add a pluggable state store and automatic persistence.
- `BaseRenderer`: bind one control type without owning page layout.
- `BaseDataSource`: supply dynamic item configurations.
- `BaseStateStore`: isolate persistence from SWS business.
- `GridLayout`: translate item count and column count into existing `CreateGird` parameters.
- `TemplateRegistry`: map semantic names such as `label`, `button`, `toggle`, `slider`, and `value` to JSON-template suffixes.

## Extension order

1. Express the feature with existing configuration fields.
2. Add a template suffix map when the visual structure already exists.
3. Add a reusable renderer for new interaction semantics.
4. Add `beforeRender`, `afterCreateItem`, `afterRender`, `beforeUnRender`, or `afterUnRender` logic for page-specific integration.
5. Add a layout strategy for reusable placement behavior.
6. Override the complete rendering flow only as the last step.

Use `RefreshValues()` for state-store changes without rebuilding clones. Use `RefreshData()` when the item collection changes. Toggle and Slider instances are disposed during `unRender` so dynamic pages do not retain stale runtime entries.

Use `RefreshItemConditions()` immediately after optimistic Toggle or Slider interaction. It refreshes visibility and enabled state without replacing the displayed value from a possibly stale asynchronous state store; call `RefreshValues()` after the authoritative server value arrives.

## Dependency rule

Pass project behavior through `Services`, `DataSource`, `StateStore`, and callbacks. Generic modules must never import SWS `UISystem`, fight controllers, settings components, or project configuration.

## Compatibility

Keep legacy configuration keys and `addCompToConfig(Id, Label, TouchType, BindFunc, DefaultValue)` usable. Introduce optional fields additively. Migrate existing pages one at a time after an in-game check; do not batch-convert mature screens.
