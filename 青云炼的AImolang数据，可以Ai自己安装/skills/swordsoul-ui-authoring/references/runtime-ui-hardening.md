# NetEase Runtime UI Hardening

## Contents

1. Entry and ownership
2. Visual baseline and proportions
3. Dynamic lists and top alignment
4. Modal layering and input isolation
5. Scroll registration
6. Runtime data and persistence
7. Platform images and undocumented APIs
8. Animation lifecycle
9. Python helper namespaces
10. Control-tree readiness and asynchronous access
11. Verification matrix

## 1. Entry and ownership

- Inspect the existing setting page, native proxy, pause proxy, HUD entry, and UI stack before adding an entry.
- Reuse the user-designated entry. Do not add a second pause-screen or HUD entry merely because it is easier to reach.
- Keep permission checks on the server before pushing an administrator UI. Hiding a client button is not authorization.
- Use `PushUI` for stack pages and preserve the existing close/return flow. Do not mix stack pages with permanent HUD creation.
- Keep generic UI primitives in QingYunModLibs and business data, permission, RPC, and labels in SWS adapters.

## 2. Visual baseline and proportions

- Use `MainSetting.json`, tutorial, and announcement screens as the black premium-minimal baseline.
- Reuse established textures and close-button artwork. Do not substitute a text `X` when the project already has the close icon/template.
- Do not add a full-screen dim layer unless the design explicitly calls for one. A panel background and a modal shield have different purposes.
- Treat screenshots at the actual GUI scale as authoritative for proportions. A mathematically valid percentage layout may still feel oversized.
- Judge vertical centering by visible pixels, not by matching `anchor`, `offset`, or control height. NetEase labels can render their glyphs above the geometric center; after setting the final font scale, compare the glyph center or baseline against the adjacent number, icon, or toggle center and apply a label-only Y compensation.
- Do not move an entire row to correct a label-only vertical bias. Keep the value/toggle on the intended row center and adjust the label child independently; recheck after every font-size change because font metrics change the required compensation.
- Keep navigation buttons compact enough that content remains dominant. Re-evaluate the entire composition after changing one control size.
- Align header status text by the visual center of the close control, then tune font scale and vertical offset together.
- Start primary content at the top of its viewport. Empty vertical space above the first row usually signals an incorrect anchor, grid origin, or centered container.
- Add a visible selected state for tabbed navigation; do not rely on users remembering which page was clicked.

## 3. Dynamic lists and top alignment

- Clone and populate rows before registering scrolling or measuring positions.
- Use stable item identifiers for callbacks. Never derive business identity from a transient visual index after sorting or rebuilding.
- Use `point_y: 0` for an ordinary top-aligned vertical grid. Do not compensate for the viewport offset inside the grid.
- Derive content height from row count and row interval, while clamping it to at least the viewport height.
- Rebuild button bindings after a grid rebuild and discard animation metrics for removed clone paths.
- Keep row action controls narrow and reserve most row width for names, state summaries, and member indicators.
- Limit dense preview elements such as avatars, then show an overflow count instead of compressing every member into one row.
- Preserve offline members in server data when the feature requires stable assignments. Online discovery and persistent membership are separate concepts.

## 4. Modal layering and input isolation

- Define explicit layer bands: base page, modal shield, modal background, modal content, modal buttons, and toast.
- Do not assume a high parent layer automatically fixes descendants that declare lower explicit layers. Audit every visible modal descendant.
- Place the shield above all base-page controls and below all modal visuals.
- A visual layer does not necessarily isolate custom Python input dispatch. Treat rendering order and input routing as separate systems.
- While a modal is open, block base-page buttons and suspend background scroll registration.
- Restore the background scroll only after the top modal has closed and its scroll registration has been removed.
- Keep modal close and confirm controls inside the modal layer band so underlying row buttons cannot appear or receive input through them.
- Verify nested modal close, repeated open, rapid close, and clicking empty modal areas.

## 5. Scroll registration

- `CreateScroll_View` registers Python-side input behavior; it is not automatically governed by JSON `layer`.
- Never leave overlapping parent and child scroll views active simultaneously.
- Call `RemoveScroll_View` for the background viewport before activating a foreground modal scroll view.
- On modal close, remove the foreground scroll first, rebuild the visible background page if needed, then register its scroll again.
- Keep viewport placement in JSON and collision/content coordinates local to the scrolling content.
- Run `test_scroll_physics.py` after changing grid origins, viewport offsets, nested scroll behavior, or modal registration order.

## 6. Runtime data and persistence

- Verify the exact accepted value types of engine storage APIs before persisting UI state.
- Do not assume that every Python basic container is accepted by a NetEase engine API.
- Serialize complex dictionaries and lists to a documented supported scalar form, normally a UTF-8 JSON string, when the API does not explicitly accept containers.
- Load defensively across schema versions: accept the current serialized form and migrate any known legacy form without discarding valid data.
- Keep one authoritative player-to-team mapping so a player cannot exist in multiple teams.
- Make destructive quick allocation explicit: preview, confirm, replace old assignments, and retain an undo snapshot when required.
- Store display profiles separately from online entity state so names and assignments survive disconnects.

## 7. Platform images and undocumented APIs

- Search official ModAPI documentation for the exact symbol before adding any engine or UI-control API.
- An old project call, third-party wrapper, runtime stub, or plausible method suffix is not proof that an API exists.
- Record client/server side, arguments, return value, supported platform, and timing restrictions before implementation.
- `SetSpritePlatformHead` is documented for the current mobile launcher account only; it does not provide arbitrary teammate avatars and is ineffective on other platforms.
- Do not invent an ID-based variant of a documented API.
- ModPC cannot validate mobile-only image behavior. Provide a deterministic PC fallback instead of displaying a blank image layer.
- Do not make a dynamic image control visible before a verified texture is available; an empty texture can render as a gray placeholder.
- For teammate identity without a documented cross-player avatar API, use a stable cross-platform fallback such as an initial frame, online/offline color, and overflow count.

## 8. Animation lifecycle

- Read `ui-animation-agent.md` before adding entrance, exit, page transition, modal, list, or button feedback animation.
- Finish cloning, text assignment, sizing, grid layout, scroll registration, and `UpdateScreen()` before measuring or binding dynamic interactions.
- Move only stable parent containers. Use alpha-only staggering for dynamic scroll/grid rows.
- Disable business interaction during entrance, exit, and page transition animations.
- After a moving parent finishes, call `UpdateScreen()` and lazily bind descendant button metrics on the first real interaction.
- Animate button visual children, not root hitboxes.
- Fade selected tab markers, page content, modals, and toasts only when the complete alpha propagation chain is present.
- Invalidate pending list-entry timers with a generation token when a grid is rebuilt.
- Stop animations, cancel timers, clear metrics, and guard delayed callbacks when the screen is destroyed.
- Delay `PopTopUI()` until the exit animation completes.

## 9. Python helper namespaces

- Locate the defining module of every runtime helper before copying a call from another screen.
- If a module is imported as `UIMod`, qualify its helpers as `UIMod.GetCompData`, `UIMod.GetCompMustPosition`, and similar names unless those exact functions are explicitly imported.
- Do not rely on a wildcard import from a different module to expose UI helpers.
- Python compilation validates syntax but does not detect an unresolved global that is only reached at runtime.
- Add source assertions or a lightweight runtime smoke path for new helper families, especially open and close animation paths.
- Test both creation and Escape/close. A failed creation can leave enough screen state for the close handler to expose a second unresolved symbol.

## 10. Control-tree readiness and asynchronous access

- Treat UI registration, ScreenNode availability, `CreateUI` return, `UiInitFinished`, control-tree creation, layout completion, and business readiness as distinct lifecycle stages. `UIModComp(uiName)` being truthy is not a create-complete signal.
- Give persistent HUD/screen owners an explicit readiness flag. Initialize it to false, set it false before each create/rebuild, and set it true only at the end of the successful `Create`/`AddCreateFunc` business initializer after all required controls and bindings exist.
- Gate every Tick, timer, event handler, RPC result, combat/AI update, and delayed animation callback before it reaches `GetBetterUIControl`, `SetVisible`, `GetCompData`, animation helpers, or direct control methods. Re-check inside the callback rather than trusting the state at scheduling time.
- Apply two layers of protection: stop high-frequency work at its business entry, and independently guard the lowest-level helper that writes the control. This prevents a new caller from bypassing the lifecycle rule.
- Do not look up controls early merely to test whether they exist. QingYunModLibs control lookup may return and cache `None`; store business data or a pending visual intent instead, then resolve the control only after readiness.
- Close the readiness gate before destruction and recreation, cancel timers, invalidate generation tokens, and discard cached screen/control references. A stale screen object is not a valid readiness signal.
- Keep the not-ready path quiet and deterministic: skip visual work, reset time baselines when needed, and avoid blanket `try/except` that would turn a lifecycle bug into silent per-frame failure.

## 11. Verification matrix

### Layout

- Wide and narrow window.
- Actual user GUI scale.
- First item starts at the viewport top.
- Header text aligns with close control.
- Buttons do not dominate content.
- No inherited rectangular texture becomes square.

### Layering and input

- Base controls never render above a modal.
- Base buttons do not activate through a modal.
- Foreground scrolling does not move the background list.
- Closing the modal restores exactly one background scroll registration.

### Data

- Create, delete, add, remove, move, quick assign, undo, reconnect, and reopen.
- Offline members remain assigned when required.
- Persistence survives reload using only documented storage value types.

### Animation

- First open, rapid Escape during open, normal close, repeat open.
- Rapid tab switching.
- Hover, press, cancel, and hover-out initialization.
- Dynamic list refresh while a modal is open.
- No stale timer or animation callback after destruction.

### Lifecycle readiness

- Start Tick-driven business components before the HUD `Create` callback; verify that no control API is called and no `None.SetVisible`-style error is emitted.
- Deliver event/RPC results while the screen is creating; verify that data remains valid and visuals apply only after readiness.
- Destroy or recreate the screen with timers and delayed callbacks pending; verify that stale work is rejected and the new screen resumes updates after its own ready transition.
- Search high-frequency call chains for bare `UIModComp` checks and direct UI writes that bypass the explicit readiness gate.

### Platform and APIs

- Exact API symbol is present in official documentation.
- Platform restrictions have a visible fallback.
- ModPC-only evidence is not used to claim mobile behavior.
- No blank dynamic image layer is exposed while loading or after failure.

### Static gates

- Compile modified runtime Python.
- Parse modified JSON and reject BOM.
- Run `validate_ui_json.py`, `audit_ui.py --strict`, `delivery_check.py`, and relevant focused regression scripts.
- Search edited runtime code for unqualified new helper calls and undocumented API symbols.
- Report that static checks do not replace in-game rendering and input verification.
