# Directional skeletal lightning VFX

Use this reference for SwordSoul forward lightning built from a skeletal/free-model mesh, custom entity material, GLSL, `CreateSuperEffect`, and optional post-process interaction. Treat current user-tuned values as the source of truth; these rules describe the workflow and invariants, not permission to retune unrelated parameters.

## 1. Start from a visual contract

Write down these decisions before editing:

- Direction: radial burst, bidirectional web, or one-sided movement trail.
- Anchor: live bone follow, entity follow, or world-space release-point lock.
- Arc hierarchy: which arcs are continuous main arcs and which arcs may become branches or debris.
- Color/coverage: opaque white, tinted, additive, or translucent.
- Timeline: appearance extension, frozen interval, release motion, breakup, debris fade, and cleanup.
- Occlusion: normal world depth, glass-only override, or unconditional overlay.

For the tuned `dimensional_sever` lightning, preserve these established semantics unless the user changes them:

- One-sided directional trail rather than a centered radial web.
- Three longest arcs are the readable main arcs; shorter arcs are branches/debris.
- Pure white opaque surviving pixels; randomness controls coverage/discard, not gray alpha.
- A single logical trigger at the distortion/time-stop event; never periodic respawn.
- The release position and horizontal facing are locked once so later player motion does not drag world-space lightning.

## 2. Build topology for shader control

Use crossed ribbon strips for view-robust arcs. Keep the mesh low-poly and validate every triangle.

Encode independent arc metadata when the mesh format has no custom vertex channel:

```text
uv.x = arc_id * 2 + arc_progress
arc_id = floor(uv.x * 0.5)
arc_progress = uv.x - arc_id * 2
uv.y = ribbon side / cross-section coordinate
```

Contract:

- `arc_progress = 0` is the far trail end.
- `arc_progress = 1` is the character/root end.
- Every vertex in one crossed-ribbon segment must decode to the same `arc_id`.
- Do not sample a texture with this encoded U coordinate unless wrapping beyond `0..1` is intentional.
- Values around `0..21` are safe for the current 11-arc layout, but still validate the actual vertex attribute path.

Make the longest arcs the first stable IDs when later shader logic must protect them. In the current mesh, arc IDs `0..2` are the three main arcs.

## 3. Shape, scale, thickness, and randomness

Inspect the model axes and bounding box before scaling. A wrong axis multiplier turns an intended trail into a screen-sized lightning cage.

Separate these controls:

- Center path width/length: transform `POSITION`.
- Ribbon thickness: extrude with transformed `NORMAL` and the `uv.y` side sign.
- Fragment core/halo: control coverage across the already-thickened ribbon.

If a line is too thin, enlarge actual ribbon geometry first. Expanding only the fragment white core cannot create pixels outside a subpixel strip.

Avoid regular endpoints:

- Give every `arc_id` an independent length multiplier.
- Add independent root and tail offsets with smooth endpoint masks.
- Keep root offsets smaller than tail offsets for a trail attached near the character.
- Include `arc_id` in fragment cell hashes; a single global seed is not enough to decorrelate all arcs.

Avoid the failed looks:

- Do not stack many identical layers to fake density; it becomes a wide white net.
- Do not use checker/grid coverage markers for visible lightning.
- Do not add cyan/blue tint when the requested result is pure bloom-white.
- Do not make entry and exit coordinates share one cutoff plane.

## 4. Runtime ownership and one-shot emission

Use one public effect call for one logical lightning event. Configure the emitter so it creates only the intended part, then clean up every returned effect ID.

For `CreateSuperEffect`:

- `partHealth` is the rendered part lifetime.
- `Health` is the emitter lifetime; keep it short enough to avoid another emission.
- Verify `ShootSpeed * Health` behavior instead of assuming `Health` is only visual lifetime.
- Store and destroy all IDs; remove them from `QyEngine_EffectCache` through the established destroy path.

When two render passes must draw the same lightning, share all stochastic inputs and the absolute start time. Independent expression constructors create mismatched arcs at the overlap boundary.

Current project pattern:

```text
EXTRA_VECTOR1 = (progress, seed, intensity, flickerVariant)
```

The normal and stencil-overlay `CreateSuperEffect` instances receive one shared `(seed, variant, start_time)` payload. The current implementation stores it in `QyParticle.corePosition` only because bound-entity `QyPart.getShootPos()` ignores that field; re-verify this QyEngine behavior before reusing the trick elsewhere.

## 5. Freeze motion without freezing the whole effect

Freeze every time-dependent visual source during time stop:

- Vertex electric frame/jitter.
- Fragment flicker tick and spatial random frame.
- Debris scatter and breakup progress.

Do not assume freezing geometry alone makes the lightning static; changing fragment coverage still looks like motion.

Derive a separate motion clock:

```glsl
motion_progress = clamp(
    (progress - freeze_progress) / (1.0 - freeze_progress),
    0.0,
    1.0
);
```

Use `progress` for lifecycle brightness/appearance and `motion_progress` for movement, breakup, and post-stop randomness. This preserves a first-frame flash or intensity envelope while keeping the spatial lightning frozen.

## 6. Extend real time without moving progress landmarks

When the user says “do not move progress; extend the disappearance time,” do not shift shader thresholds. Stretch only the post-freeze wall-clock interval with a piecewise mapping.

For a freeze ending at real time `freeze_time`, old pre-freeze lifetime scale `base_time`, and extended total `life_time`:

```python
if part_time <= freeze_time:
    progress = part_time / base_time
else:
    disappear_time = life_time - freeze_time
    progress = freeze_progress + (
        (part_time - freeze_time) / disappear_time
    ) * (1.0 - freeze_progress)
```

Validate these exact points:

- `part_time = freeze_time -> progress = freeze_progress`.
- `part_time = life_time -> progress = 1`.
- Appearance duration before the freeze remains unchanged.
- Cleanup time and post-process shutdown still cover the new lifetime.

## 7. Appearance extension and post-stop breakup

Define `arc_progress` direction before writing the mask. For the tuned trail, the requested sweep is far trail (`0`) toward character/root (`1`).

```glsl
extension_progress = smoothstep(0.0, extension_duration, progress);
extension_front = extension_progress;
extension_mask = 1.0 - smoothstep(
    extension_front,
    extension_front + edge_width,
    arc_progress
);
```

Convert normalized duration back to seconds before judging whether it is visible. A `0.04` progress interval means `0.096 s` only when the pre-freeze scale is `2.4 s`. Check the actual number of display frames.

Use slight per-arc duration variation so the sweep is not a straight synchronized wall. Preserve the far-to-root direction when making it faster; do not accidentally reverse the mask.

For disappearance:

- Keep main arcs continuous when they carry readability.
- Let branch arcs split into cells, widen gaps, scatter, and randomly drop out.
- Use one fast `main_arc_break` curve for branch breakup and a slower `debris_decay` curve for residue loss.
- Limit main-arc scatter and impose a minimum brightness jump so main arcs do not vanish for a random frame.
- Fade debris over the extended real-time interval; do not preserve the main arc by delaying all breakup unless the user asks for that.

## 8. Discrete electric motion and opaque white output

For violent post-stop motion, discrete random frames are clearer than very high-frequency smooth interpolation. Choose a visible frame rate in seconds, not only a large normalized multiplier.

- Geometry: select a discrete `electric_frame`; remove interpolation when a hard pose jump is desired.
- Brightness: use a small number of explicit levels, including an optional near-off level for branches.
- Main arcs: clamp the minimum jump level if they must remain readable.
- Final output: `discard` below coverage and write `vec4(1.0)` for surviving pixels when the contract is opaque white.

Do not claim bloom from a color tint. Bloom is a pipeline/material outcome; the shader should provide a stable bright white source, and the post chain must actually include it.

## 9. Glass refraction, depth, and stencil masking

Never solve glass overlap by forcing all lightning to the near clip plane and enabling depth write. That makes lightning cover the player and world geometry.

A single fixed-function pass cannot express:

```text
normal scene depth passes OR pixel belongs to glass
```

Use two synchronized lightning draws:

1. Normal layer: real depth test, no forced clip-space Z, usually no depth write.
2. Glass overlay layer: `DisableDepthTest`, but stencil test `Equal` on a dedicated bit.
3. Glass marker layer: normal depth test, stencil `Always`; `stencilDepthFailOp = Keep`; `stencilPassOp = Replace`.

This guarantees:

- A player/wall in front makes glass depth fail, so glass does not write the bit.
- The overlay cannot pass stencil where glass is hidden by the player/wall.
- Where visible glass wrote the bit, only the synchronized overlay ignores glass depth.
- Normal lightning remains governed by real scene depth everywhere else.

Reserve stencil bits deliberately. The current lightning/glass protocol uses bit `32`; existing player/dodge materials use bit `64`. Set `stencilReadMask` and `stencilWriteMask` to preserve unrelated bits.

Use the official NetEase material fields exactly: `StencilWrite`, `EnableStencilTest`, `stencilRef`, `stencilReadMask`, `stencilWriteMask`, `frontFace`, `backFace`, `Always`, `Equal`, `Keep`, and `Replace`. Re-check official documentation before inventing a new field or value.

## 10. Post-process interaction

The dimensional-sever glass is an alpha/depth marker used by a later refraction pass. Render-order reasoning must include both the forward marker draw and the fullscreen post-process consumer.

- `DisableRGBWrite` may still leave alpha/depth writes active.
- Glass depth can reject later transparent lightning even when glass has no direct RGB color.
- A fullscreen refraction pass can resample over lightning; solving only blend color is insufficient.
- If distortion must affect the refracted image, compute/select the refracted sample first, then feed that result through distortion sampling order.

## 11. Validation checklist

### Mesh

- Strict JSON parse and no UTF-8 BOM.
- Expected vertex/triangle counts.
- Indices in range; no degenerate triangles.
- Finite unit normals and valid weights.
- Decoded `arc_id` and `arc_progress` ranges.
- One arc ID per crossed-ribbon segment.
- Main arc IDs still correspond to the longest intended arcs.

### Shader

- Balanced braces and preprocessor blocks.
- Vertex/fragment varying agreement.
- Freeze boundary produces zero motion on both sides of the exact threshold.
- Appearance start/half/end masks prove the intended direction.
- Normalized durations are converted to real seconds.
- Main arcs cannot enter fragment dropout when continuity is required.
- Pure-white contract remains `discard` plus opaque white.
- No accidental clip-space Z override remains.

### Material and runtime

- Material JSONC parses after comment removal.
- Stencil bit does not collide with existing masks.
- Glass writes only after depth success; overlay uses `Equal` on the same bit.
- Normal/overlay layers share seed, variant, start time, model, expression, and lifetime.
- One public trigger creates no periodic respawn.
- Every effect ID has a cleanup path.
- Piecewise progress hits freeze and lifetime endpoints exactly.
- Related Python files compile.

### In game

- Test after shader hot reload; material changes require resource reload/re-entry.
- Observe from top, side, and behind.
- Put the player in front of glass and lightning; the player must still occlude lightning.
- Put lightning behind visible glass; only the glass overlap should receive the override.
- Confirm the first sweep direction, freeze stillness, main-arc continuity, branch debris, and final cleanup.
- Do not judge a material change from the shader-only `H` reload key.

## 12. Common failure diagnosis

| Symptom | Likely cause | Preferred fix |
|---|---|---|
| Lightning fills the sky | Wrong model axis/scale | Inspect mesh bounds and transform axes |
| Lightning never moves | Progress never drives a frame/jitter source | Add a verified motion clock |
| Lightning moves during time stop | Fragment tick or scatter still uses raw progress | Gate every motion source with `motion_progress` |
| Endpoints line up | One global length/cutoff | Hash by `arc_id`; offset root/tail independently |
| Looks like a dense net | Too many duplicate layers or wide ribbons | Reduce layers/branches; preserve hierarchy |
| Single arc stays too thin | Only fragment core was widened | Extrude ribbon geometry with normal + side |
| Looks gray/transparent | Alpha output used for strength | Binary coverage plus opaque white output |
| Reappears periodically | Emitter lifetime permits another shot | Re-check `ShootSpeed`, `Health`, and shot count |
| Two overlap passes disagree | Independent seed/start time | Share seed, variant, and absolute time |
| Lightning covers the player | Near-plane Z/depth override | Restore real depth; use glass-only stencil overlay |
| Sweep is invisible | Duration too short in seconds | Convert progress duration to frames and increase it |
| Sweep travels the wrong way | `arc_progress` semantics reversed | Verify endpoint masks with start/end assertions |
| Fade was delayed by moving thresholds | Progress landmarks were shifted | Use piecewise real-time remapping instead |

