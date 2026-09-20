# ScreenRenderConfig schema

## Required legacy fields

| Key | Meaning |
| --- | --- |
| `id` | Stable item or setting identifier. SWS persistent setting IDs use PascalCase. |
| `label` | Display label. |
| `touch_type` | Registered renderer name such as `Button`, `Toggle`, `Slider`, or `Label`. |
| `bind_func` | Callable, screen method name, or service action descriptor. |
| `default_value` | Initial value when no persisted value exists. |

## Optional fields

| Key | Default | Meaning |
| --- | --- | --- |
| `auto_save` | `True` | Persist through the attached state store before invoking the action. |
| `template` | `default` | Template suffix-map name. |
| `visible` | `True` | Static or callable visibility. |
| `visible_when` | absent | `(SettingId, ExpectedValue)` or callable condition. |
| `enabled` | `True` | Static or callable interaction state. Disabled items ignore callbacks and use `disabled_alpha`. |
| `enabled_when` | absent | Tuple, condition dictionary, or callable interaction condition. |
| `disabled_alpha` | `0.45` | Root alpha while disabled. |
| `step` | `0.1` | Slider step. |
| `min_value` | `0.0` | Slider business-value minimum. |
| `max_value` | `1.0` | Slider business-value maximum. |
| `precision` | `6` | Slider mapped-value rounding precision. |
| `formatter` | `str` | Callable used for displayed values. |
| `touch_state` | `Up` | Button touch state passed to `AddSuperButtonTouch`. |
| `is_swallow` | `True` | Whether the button swallows touch. |
| `data` | `{}` | Renderer-specific payload. |
| `register_setting_control` | `True` in SWS adapter | Add the runtime control to `ChooseTypeMap` and `LoadingToggleComp`. Disable for non-setting cards. |

## Action descriptors

- Callable: invoke directly.
- String: resolve a method on the page, then a callable service with that key.
- Dictionary: resolve `service` from `Screen.Services` and invoke `method`.

Condition dictionaries support `key` with `equals`, `not_equals`, or `in`. Service action dictionaries may set `pass_context` to receive `(Value, Screen, Config, RuntimeItem)`.

Use explicit callables for complex flows. Use service descriptors for simple project adapters.
