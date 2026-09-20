---
name: molang-animation-authoring
description: Author, modify, and review Minecraft Bedrock / NetEase China Molang expressions for resource-pack animations, animation controllers, bones, render resources, scripts.pre_animation variables, q.mod custom queries, and SwordSoul_NewERA_Fight animation JSON files.
---

# Molang Animation Authoring

## Scope

Use this skill when working on Molang in `src/SwordSoul_NewERA_R`, especially:

- `animations/**/*.animation.json`
- `animation_controllers/**/*.json`
- client entity animation bindings and `scripts.pre_animation`
- bone `rotation`, `position`, `scale` expressions
- controller `switch`, `case`, and transition conditions

Do not use Molang for server-side combat judgment, hitboxes, damage, motion authority, or SWS state timing. Keep those in SWS / Mob combat code.

For full geometry, actor animation JSON, animation controller, client entity binding, or cross-resource linkage work, use `.codex/skills/bedrock-animation-authoring/SKILL.md` as the broader entry point.

## Local Agents

- For writing expressions, use `.codex/agents/common/animation/molang-animation-expression-agent.md`.
- For checking JSON structure and parse risks, use `.codex/agents/common/animation/molang-animation-json-review-agent.md`.
- For root motion extraction, use `.codex/agents/common/animation/root-motion-json-analysis-agent.md`.

Read the relevant agent file before editing or reviewing the target resource.

## Required Official Docs

Before any Molang animation authoring or review work, open or otherwise consult the current Microsoft Learn docs below. If network access is unavailable, state that limitation and proceed from the local rules only when the change is low risk.

- Introduction: `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/introduction?view=minecraft-bedrock-stable`
- Syntax guide: `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/syntax-guide?view=minecraft-bedrock-stable`
- Practical Molang: `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/practical-molang?view=minecraft-bedrock-stable`
- Query functions: `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/molangreference/examples/molangconcepts/queryfunctions?view=minecraft-bedrock-stable`
- Math functions: `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/molangreference/examples/molangconcepts/mathfunctions?view=minecraft-bedrock-stable`

## Workflow

1. Consult the required Microsoft Molang docs above.
2. Read the target animation/controller JSON with UTF-8 parsing.
3. Search nearby project examples with `rg`, especially same weapon, same body type, or same controller family.
4. Identify the expression context: bone channel, animation controller condition, `scripts.pre_animation`, or render/controller binding.
5. For controller animation weights, resolve every object key as a registered animation short name before writing the Molang value. Do not use a full `animation.*` resource name to work around a missing binding; Molang computes the weight and does not resolve resources.
6. Identify every data source: native `q.xxx`, NetEase `q.mod.xxx`, `v.xxx`, `temp.xxx`, or `math.xxx`.
7. Before changing rotation expressions, inspect the target bone pivot/origin in the model. If the pivot is not where the hinge should be, either compensate with rotation plus position offsets or, only when the user explicitly permits it, edit the pivot/origin directly.
8. Decide whether the expression can stay simple or must become a complex expression with assignments and `return`.
9. Edit only source files under `src/` or project-local `.codex/` files requested by the user.
10. Verify JSON parseability and run the Molang review checklist. Do not reload the game unless the user explicitly asks.

## Core Molang Rules

- `query.xxx` may be shortened to `q.xxx`; this is the game-native query namespace.
- `query.mod.xxx` may be shortened to `q.mod.xxx`; this is NetEase China custom query data, not a native Bedrock query.
- `variable.xxx` may be shortened to `v.xxx`; animation expressions may assign and read these values.
- Treat `q.xxx` and `q.mod.xxx` as different data sources. Confirm `q.mod.xxx` from project/NetEase context, not from Microsoft Bedrock docs.
- Booleans are numeric: `0.0` is false and non-zero is true.
- Multi-statement expressions use semicolons and must explicitly `return` a final value when used in a value-returning animation field.
- Any expression that assigns `v.xxx = ...` is a complex expression and must end with `return ...`.
- In a controller animation-weight object such as `{ "walk": "expression" }`, `walk` must be an already registered animation/controller short name. Do not write `{ "animation.some.full_name": "expression" }` unless that exact dotted string is independently verified as a registered short name.
- For a multi-part sequence in one state/case, give every full animation resource its own registered short name, then blend those short names with Molang.
- A bone channel expression must return a number or a numeric vector matching the channel shape.
- Never emit directly adjacent operators such as `+ -20`, `- -20`, `* -20`, `/ -20`, `+ +20`, `* +20`, or `/ +20`; Blockbench/Molang can reject them. For negative phase or offset, write `q.anim_time * 120 - 20`, or use parentheses like `(0 - 20)` when a signed value is unavoidable.

## Animation Math

- Bedrock Molang trigonometric functions use degrees.
- `math.sin(q.anim_time * 360)` is a 1-second cycle.
- Use `math.sin` / `math.cos` for breathing, floating, swinging, recoil, and other reciprocal or circular motion.
- Always reason about amplitude, period, phase offset, and channel unit before writing the expression.
- Prefer clamping or bounded waves for visible bones so errors cannot create extreme poses.
- A wrong pivot cannot be fixed cleanly by amplitude alone. If rotation appears to orbit, tear, or bend from the wrong hinge, check the model pivot/origin before tuning the Molang.
- For segmented soft-body bending with dual-pivot wrapper bones, compute one shared `base` wave per segment, then split it into inward hinge rotations with `math.min(base, 0)` and `math.max(base, 0)`. The visible segment bone should usually stay whole; animate the wrapper axes rather than splitting the visible mesh into half-cubes.
- For left/right grass sway, prefer Z-axis bending on `*_left` / `*_right` wrapper bones. Do not introduce Y-axis twist unless the user explicitly asks for four-direction or torsion behavior.
- Make phase offsets explicit and parser-safe. Write `q.anim_time * 180 + 348` or `q.anim_time * 180 - 12`, never `q.anim_time * 180 + -12`.
- When a visual reads too slow or too stiff, adjust frequency and amplitude intentionally. A 2-second primary loop uses `q.anim_time * 180`; add a smaller `q.anim_time * 360` harmonic for lively secondary flutter.

## Smoothness Rules

- Do not mix Molang expressions with smooth keyframes on the same animation channel; the resource can fail to parse.
- Native position, coordinate, and yaw/pitch queries that come from player state may update at only 20 ticks per second.
- Do not directly drive high-frequency visual animation from 20tick native query data when smoothness matters.
- For smooth position or yaw following, use `q.delta_time` and `v.xxx` variables to interpolate from the previous visual value toward the current query value.
- For smooth yaw, store the previous visual yaw in `v.xxx`; handle wrap-around before interpolation when the angle crosses `-180/180` or `0/360`.
- When several animation weights share one `v.progress` timer, increment it in exactly one expression per frame and let the other expressions only read it. Incrementing the same timer in every animation weight makes elapsed time advance multiple times per frame.
- Reset a state-local progress timer in `on_entry` (or the matching project lifecycle hook) so re-entering the state restarts the sequence.

## Root Motion Boundary

- Treat `anim_time_update` as a clock mapping only: `source_time = state_time * rate`. It does not convert model units to blocks, move the server entity, compensate `SetMotion` friction, or validate actual travel distance.
- Molang bone `position` affects rendered animation space, not Mob combat authority, collision, hitbox origin, or server physics. Keep entity root-motion scheduling in SWS/Mob code.
- When root position depends on Molang variables or queries instead of deterministic keyframes, do not pretend a static server timeline can reproduce it. Identify every input and either provide the same authoritative server data source or mark physical synchronization unresolved.
- For deterministic keyframed root motion, report the expression rate and source/state sample mapping to `auto-fill-mob-move-config`; that layer chooses between species-calibrated instantaneous speeds and 20Hz per-tick block deltas. Never insert an empirical scale such as `0.00527` into Molang as a unit conversion. See [the root-motion parameter model](../auto-fill-mob-move-config/references/parameter-model.md).

## Review Checklist

- JSON parses as UTF-8.
- Names referenced by controllers, animations, and client entity bindings still match.
- Every controller animation-weight key is a registered short name that resolves one-to-one to the intended full animation resource; no full resource name is used to bypass a missing binding.
- Shared `q.delta_time` progress is assigned once per frame, and state re-entry resets the timer.
- `q.xxx` native queries and `q.mod.xxx` NetEase custom queries are not confused.
- Any `v.xxx =` assignment has a final `return`.
- No same-channel smooth keyframe/Molang mixing.
- Vector channel dimensions match the target property.
- Rotation expressions were tuned after checking the target bone pivot/origin, or the response states why geometry was unavailable.
- Expressions using trig functions follow degree-based timing.
- Expressions contain no adjacent operator pairs such as `+ -`, `- -`, `* -`, `/ -`, `+ +`, `* +`, or `/ +`.
- Dual-pivot hinge pairs use the same base wave on both sides, split with `math.min` / `math.max`, and only drive the intended axis.
- Expressions using 20tick data either accept low-rate updates intentionally or perform interpolation.
- Root-motion expressions clearly separate visual model-space position, animation clock mapping, and server physical displacement; no Molang-only change is claimed to move the entity.
- `.build/dist` is untouched.
