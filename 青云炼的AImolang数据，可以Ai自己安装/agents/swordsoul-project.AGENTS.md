# SwordSoul_NewERA_Fight agent rules

## Project PYC deletion authorization

- The user permanently authorizes deletion of all `*.pyc` files located strictly within this project root, including files under `src`, `.build/dist`, and tool directories.
- Before deleting, resolve and verify every target remains under this project root. This authorization never applies to files outside the project.

## Vanilla mob combat deployment baseline

- Every vanilla/NetEase mob deployment must begin by reading the active installed game version's behavior entity, client entity, geometry, actor animations, animation controllers, and render controllers. Inventory component groups/events, mutually exclusive melee/ranged or land/water forms, exact animation/controller short names, active `scripts.animate` entries, and their original Molang conditions. Do not infer one mob's vanilla chain from another mob, and do not treat legacy entity variants or Mojang samples as the active NetEase source.
- Every deployed mob must have its own entity Python module and static render config class/registry alias even when it inherits another mob's SWS combat states. Shared combat data does not authorize sharing mob-specific native components, geometry, original controller removal keys, or render conditions.
- For a deployed mob, `query.mod.fight` must cover the entire `MobCombatMode.FIGHT` lifetime, remain enabled across `fight_none` gaps, and disable only after combat mode exits. Re-register originals under exact client short names, remove only exact original controller runtime keys, and combine every active original `scripts.animate` condition with `!query.mod.fight`; direct animations and controller entries must both be covered.
- When proxying vanilla animation resources, every `animation_controller` alias must use `c_<original short name>` and every matching `script_animate` reference must use that same `c_` alias; direct actor-animation aliases keep their original short names. Classify each entry from the active client entity binding target instead of its `scripts.animate` spelling, and keep `remove_animation_controller` on the exact original runtime key `controller__<original short name>` without the proxy `c_` prefix.
- Build native control/damage maps from that mob's active behavior JSON. On combat entry disable movement/navigation goals, event components that can re-add native groups, melee damage, ranged/projectile/shooter components, and mode-switch sensors as applicable. Snapshot the active component-group/form profile through a documented state source before removal and restore only that profile on combat exit, preserving adult/baby, land/water, and mutually exclusive attack modes. `RemoveActorComponent` only reports command dispatch and must never be treated as proof that a component existed. Keep target selectors only when SWS needs their target data.
- Where native attacks can race component switching, add a mob-scoped `DamageEvent` safety gate that rejects native melee/projectile damage outside a verified SWS attack window and defensively sets knockback/ignite false. NetEase documents that `ignite = false` may not undo ignition, so this gate is secondary to component suppression and must not block SWS-authored hits.
- If the vanilla geometry lacks the proven SWS humanoid bone/locator contract, deploy a mob-specific compatible geometry that preserves the mob's texture layout and visual overlays while adding the required root, segmented torso/limbs, item bones, and locators. Never substitute another visually distinct mob's geometry solely because combat states are shared.
- Validate Python compilation, UTF-8 JSON parsing, registry uniqueness, exact short-name and `scripts.animate` coverage, geometry identifier/parent/locator integrity, animation-bone resolution, component restoration, and native-hit/SWS-hit behavior. Include adult/baby, land/water, melee/ranged, combat entry, `fight_none`, and combat exit cases. Do not sync `.build/dist` or reload the game unless explicitly requested.

## NetEase UI texture scaling

- Use `src/SwordSoul_NewERA_R/ui/MainSetting.json` as the project baseline for adaptive resource UI.
- Ordinary UI textures may be stretched. Full-panel backgrounds, solid/simple-gradient images, masks, dividers, progress fills, and selection bars must set `keep_ratio: false` so they fill their controls at different resolutions and aspect ratios.
- Preserve aspect ratio only for complex authored artwork such as icons, portraits, illustrations, book art, and decorative emblems.
- Stretchable textures with protected corners, borders, or button-frame details should use the legacy nine-slice path (`is_new_nine_slice: false` / `$is_new_nine_slice: false`) by following a verified `MainSetting.json` example of the same template type.
- On `common.button`, set `keep_ratio: false` on all inherited stretchable state images (`default`, `hover`, and `pressed`), not only on the button root; otherwise a rectangular button can display a square background.
- Treat UI editor selection borders and resize handles as diagnostic overlays. Identify the selected control path before modifying nearby runtime images.
- Audit both explicit `type: image` controls and inherited template texture variables whenever creating or changing UI JSON.

## NetEase UI alpha animation propagation

- Before applying an alpha or fade animation to a control, set `propagate_alpha: true` on the animated control and on every descendant or intermediate container that must visually inherit that alpha.
- Treat propagation as a complete control-chain requirement: parent panels, nested panels, scroll content roots, buttons, button state containers, labels, images, and progress subcontrols must not break the chain to the final visible controls.
- Audit inherited templates and runtime-cloned controls as well as explicit JSON children. A parent fading correctly while its text, texture, or button states remain opaque is a propagation defect.
- For an animated JSON subtree, recursively verify that every node containing `controls` declares `propagate_alpha: true` unless that node is an explicitly documented alpha-isolation boundary.

## NetEase UI animation baseline binding

- Cache the control's current size and position immediately before the animation that consumes them. Do not reuse a baseline captured before a parent entrance, move, scale, grid rebuild, scroll registration, or layout update.
- Moving or scaling a parent invalidates cached descendant positions. Finish the parent animation, call `UpdateScreen()`, then enable descendant interaction animations or refresh their baselines.
- Never run absolute-position animations on a dynamic grid or scroll child while an ancestor is moving. The child's global target becomes stale as the ancestor moves and the final local offset will be wrong or clipped. Let the ancestor provide motion and use alpha-only staggering for descendants unless a verified local-coordinate animation path exists.
- For runtime-cloned controls, wait until cloning, explicit sizing, scroll registration, and final layout are complete. Reject implausibly small dimensions and retry briefly instead of caching them.
- Prefer lazy binding for hover/press feedback: register the control path after layout, then read its metrics on the first real `HoverIn` or `Down` immediately before starting the feedback animation.
- Animate visual children for button feedback while leaving the root hitbox and layout control unchanged. Ignore unmatched initialization events such as `HoverOut` without a preceding `HoverIn`.

## NetEase composite UI integration

- Before adding a UI entry, inspect MainSetting, native/pause proxies, HUD entries, and user-prepared buttons. Reuse the user-designated entry and do not create a competing pause-screen or HUD entry.
- Administrator pages must receive server-confirmed permission before `PushUI`; client visibility is not authorization.
- Keep ordinary vertical list content top-aligned with local `point_y: 0`. Evaluate navigation, action-button, and content proportions at the user's actual GUI scale instead of accepting percentage math alone.
- Reuse the established black minimal templates and close-button artwork. Do not replace an existing close icon with text `X`, and do not add a full-screen dim layer unless explicitly requested.
- Treat modal rendering and modal input as separate audits. Assign explicit layer bands to shield, modal background, content, and buttons; while a foreground modal scroll is active, unregister any overlapping background scroll and restore exactly one registration after close.
- After a dynamic grid rebuild, discard animation metrics and bindings for removed clone paths. Complete cloning, scroll registration, and `UpdateScreen()` before binding new dynamic interactions.

## NetEase UI data and platform fallbacks

- Verify the documented accepted value types of engine persistence APIs. Do not pass dictionaries or lists unless the exact interface documentation permits them; serialize complex state to a supported UTF-8 JSON string and preserve known legacy migration reads.
- Platform-only images must have a deterministic fallback for unsupported environments. Never expose an empty image control while waiting for an unverified texture, because ModPC may display a gray placeholder.
- Do not claim ModPC proves mobile-only UI behavior. Record the platform limitation and require the appropriate mobile test for final visual verification.

## NetEase UI runtime helper qualification

- Resolve every copied runtime helper to its defining module. When UI helpers are accessed through `UIMod`, call `UIMod.GetCompData`, `UIMod.GetCompMustPosition`, and other helpers with the module qualifier unless they are explicitly imported by name.
- Do not rely on wildcard imports from unrelated modules to expose UI helpers. Python compilation checks syntax but does not detect unresolved globals that execute only during Create/Open or Escape/Close.
- Add focused regression checks for both opening and closing animation paths, including searches for unqualified new helper calls.

## NetEase UI lifecycle readiness

- `UIModComp(uiName)` returning a ScreenNode proves only that the engine has exposed a screen object; it does not prove that `Create()`, `AddCreateFunc`, control-tree instantiation, layout, or business initialization has completed. Never use this check alone as UI readiness.
- Any persistent HUD or screen accessed by Tick, timers, event handlers, RPC callbacks, AI/combat updates, or delayed animation callbacks must expose an explicit readiness gate. Initialize it to false, keep it false during create/rebuild, and set it true only at the end of the screen's successful create callback after every required control is available.
- Guard both high-frequency business entry points and the lowest-level UI-writing helpers. When the gate is false or the screen has been destroyed, skip all control access; every asynchronous callback must re-check readiness when it executes.
- Do not call `GetBetterUIControl`, `SetVisible`, `GetCompData`, animation helpers, or similar control APIs before readiness. An early lookup may return and cache `None`, poisoning later access even after creation finishes.
- On destroy or recreation, close the gate before cleanup, cancel delayed work, and invalidate cached screen/control references. Do not hide lifecycle defects with blanket `try/except`; preserve business state or queue data, then apply visuals after the next successful ready transition.
- Add lifecycle regression coverage for Tick-before-Create, callbacks during creation, delayed callbacks after destroy, and destroy/recreate. These cases must produce zero control calls before readiness and resume normal updates afterward.
