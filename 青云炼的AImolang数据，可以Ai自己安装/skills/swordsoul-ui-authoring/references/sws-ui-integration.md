# SWS UI integration

## Settings

Use `ChooseSettingStateStore` to connect a generic `BaseSettingScreen` to `ChooseSettingSystem`. A new persistent setting still requires its SWS default field, `SetLocalConfig` registration, apply callback when applicable, and actual business consumer.

## HUD and input

Treat `Control.py` as input translation and HUD presentation. Preserve existing Down/Up/Cancel symmetry, keyboard release bindings, gamepad pairs, touch swallowing, and `CheckCanUse` conventions.

## Runtime loading

- Use `CreateUI` for persistent HUD screens.
- Use `PushUI` for stack screens.
- Keep `UiInitFinished`, `@AddCreateFunc`, close guards, and native screen proxies consistent with the analogous existing screen.

## Migration

`MainSetting.BaseScreenRenderCls` is now a compatibility shell over `BaseSWSSettingScreen`; existing five-field setting pages use the generic renderer without changing their class names. `SkinScreen`, `CapeScreen`, and `EmojiScreen` are the reference migrations for `SelectionCard` plus a three-column layout. `TrailScreen.py` no longer contains its unused duplicate base class.

For future migration, preserve the existing class and business callbacks, replace copied Grid/render code with `LayoutConfig`, select an SWS template, and move item-specific work into `afterCreateItem`, `beforeRender`, or `afterRender`.
