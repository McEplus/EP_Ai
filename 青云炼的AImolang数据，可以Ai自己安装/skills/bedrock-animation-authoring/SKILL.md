---
name: bedrock-animation-authoring
description: "Author, modify, and review Minecraft Bedrock / NetEase China resource-pack animation assets: geometry .geo.json models, actor .animation.json files, animation controllers, client entity animation bindings, Molang expressions, bones, locators, timelines, and SwordSoul_NewERA_R animation resources."
---

# Bedrock Animation Authoring

## Scope

Use this skill for resource-pack animation work in `src/SwordSoul_NewERA_R`, especially:

- `models/**/*.geo.json` and Blockbench-exported geometry.
- `animations/**/*.animation.json`.
- `animation_controllers/**/*.json`.
- client entity geometry / animation / `scripts.animate` bindings.
- Molang in animation channels, controllers, render resources, and `scripts.pre_animation`.

Do not use this skill for server-side combat authority, damage, hitboxes, or SWS timing. Use SWS/Mob combat rules for runtime gameplay logic.

## Agent Routing

- Overall routing and resource-chain review: `.codex/agents/common/animation/bedrock-animation-resource-agent.md`.
- Geometry model review: `.codex/agents/common/animation/geometry-model-review-agent.md`.
- Actor animation JSON work: `.codex/agents/common/animation/actor-animation-json-agent.md`.
- Animation controller work: `.codex/agents/common/animation/animation-controller-agent.md`.
- Client entity / geometry / animation binding checks: `.codex/agents/common/animation/animation-binding-linkage-agent.md`.
- Molang expression authoring: `.codex/agents/common/animation/molang-animation-expression-agent.md`.
- Molang expression review: `.codex/agents/common/animation/molang-animation-json-review-agent.md`.
- Root motion keyframe extraction: `.codex/agents/common/animation/root-motion-json-analysis-agent.md`.

Read the relevant agent before editing or reviewing resources.

## Required Official Docs

Before geometry, animation, controller, binding, or Molang work, consult the relevant current Microsoft Learn docs. If network access is unavailable, say so and proceed only for low-risk local edits.

If a documentation/search tool reports a decode, stream, parser, or response-format error, treat it as a recoverable tool-path failure rather than immediately declaring the network unavailable or switching tools. Preserve the exact error, retry the smallest equivalent request, isolate URLs/queries one at a time, reduce the requested response size, and try the same tool's supported open/search or encoding-safe variants. Use an alternate read-only HTTP client or cached source only after the original path's reasonable recovery options have all failed; state the fallback explicitly and keep the source restricted to the required official domain.

Molang:

- `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/introduction?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/syntax-guide?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/documents/molang/practical-molang?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/molangreference/examples/molangconcepts/queryfunctions?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/molangreference/examples/molangconcepts/mathfunctions?view=minecraft-bedrock-stable`

Geometry:

- `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_geometry_1.12.0?view=minecraft-bedrock-stable`

Animations:

- `https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationsoverview?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationcontroller?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/reference/content/schemasreference/schemas/minecraftschema_actor_animation_1.8.0?view=minecraft-bedrock-stable`
- `https://learn.microsoft.com/en-us/minecraft/creator/documents/animations/animationupgrade?view=minecraft-bedrock-stable`

## Workflow

1. Consult the relevant official docs above.
2. Read the target JSON with Python `json.load(open(path, encoding="utf-8"))`.
3. Search same-family project examples with `rg`.
4. Identify the layer being changed: geometry, actor animation, controller, client entity binding, Molang, or root motion analysis.
5. Check the reference chain before editing: client entity -> geometry identifier -> animation/controller short names -> animation/controller full names -> animation bones -> geometry bones/locators.
6. For every animation used by a controller state/case, resolve `controller short name -> player/client binding -> full animation resource`. If the full resource exists but no short name is registered, the controller-only change is not complete: report the missing binding or request scope expansion. Do not place a full `animation.*` resource name in the controller to bypass the missing short name.
7. For segmented soft-body visuals such as capes, grass, cloth, tails, vines, ribbons, or chains, inspect the model topology before writing animation expressions. Confirm whether the effect needs center-pivot sway, dual-pivot inward hinge bending, or true four-direction bending.
8. Before tuning rotation animation, inspect the target bone pivots/origins. If the pivot is wrong and the user did not allow pivot edits, compensate with rotation plus position offsets; if the user explicitly allows pivot edits, prefer fixing the pivot/origin first.
9. Keep project format conventions unless the user requests migration:
   - geometry usually uses `format_version: 1.12.0`.
   - actor animations usually use `format_version: 1.8.0`.
   - animation controllers usually use `format_version: 1.10.0`.
10. Edit only requested source files under `src/` or project-local `.codex/` rules.
11. Verify JSON parseability and run the matching agent checklist. Do not touch `.build/dist` or reload the game unless explicitly requested.

## Project Rules

- NetEase `query.mod.xxx` / `q.mod.xxx` is custom query data, not Microsoft native Molang query.
- This project uses both official `states/transitions` controllers and project/NetEase `switch/case` controllers. Do not flag `switch/case` as invalid only because it is not the vanilla controller style.
- Controller `animations` entries use registered short names. Full resource names such as `animation.fight.use_bow_sneaking` belong on the binding side, not inside a controller state/case.
- When one state blends multiple actor animations, register a distinct short name for every full resource and reference those short names one-to-one. A Molang blend expression controls weight; it cannot make an unregistered animation resource addressable.
- A user restriction such as "only edit the controller" does not authorize a broken binding shortcut. If the requested result requires adding or correcting a binding outside that scope, explain the dependency and stop instead of inventing an unsupported controller reference.
- Geometry bone names are the contract for animation bone channels. A typo may parse but silently fail visually.
- Locators are contracts for particles, effects, attachments, and event binding. Preserve locator names unless intentionally migrating all references.
- Bone pivots/origins are part of the animation contract. Do not blindly increase rotation amplitude when an effect bends around the wrong point; first check whether the pivot/origin is correct for the intended hinge.
- Do not mix Molang expressions with smooth keyframe data on the same channel.
- Do not write Molang with adjacent operators such as `+ -20`, `- -20`, `* -20`, `/ -20`, `+ +20`, `* +20`, or `/ +20`; for negative offsets, render them as subtraction (`... - 20`) or parenthesize the signed value.
- For seamless segmented bending such as capes, grass, cloth strips, tails, or vines, do not hide broken joints with patch/link cubes. Use a dual-pivot wrapper chain like `segment_N_left -> segment_N_right -> segment_N_bone + segment_(N+1)_left`, where the visible segment stays whole under its bone and the two wrapper origins sit on the left/right or front/back edges of the joint. Drive the two wrappers as one-sided inward hinges, for example `math.min(base, 0)` on one side and `math.max(base, 0)` on the other, so the joint closes inward instead of exposing the split.
- For cape-like topology, mirror the existing pattern `line_N_front -> line_N_back -> boneN + line_(N+1)_front`. For left/right grass sway, use the analogous chain `grass_N_left -> grass_N_right -> grass_N_bone + grass_(N+1)_left`. Do not replace this with sibling left/right chains.
- Resource edits require in-game / MC Studio resource reload to observe, but Codex must not trigger reload without user permission.

## Root Motion Handoff

- Treat `bones.root_move.position` as cumulative model-space animation data. It does not move the server entity, collision box, AI position, or damage origin by itself; never translate its numeric value directly into `SetMotion.power`.
- Establish and report the complete handoff: model-unit scale, source keyframes, `pre/post`, interpolation mode, source-to-state clock from `anim_time_update`, axis mapping, net displacement, and which layer owns visible/physical root motion. Standard Bedrock/Blockbench models commonly use `16 model units = 1 block`, but verify the target geometry/exporter before using that ratio.
- Check the geometry hierarchy. A data-only `root_move` with no visible descendants can carry extraction data while producing no visible translation; a visible skeleton inheriting the same translation while the server also moves the entity creates double root motion.
- `anim_time_update` changes only animation time. It does not convert model units to blocks, apply physics, compensate friction, or prove entity travel distance.
- When handing a curve to Mob combat, do not provide a guessed global scale. For exact authored travel, provide 20Hz curve samples or sufficient keyframes for Catmull-Rom resampling and defer physical scheduling to `swordsoul-mob-fight` / `auto-fill-mob-move-config`. See [the root-motion parameter model](../auto-fill-mob-move-config/references/parameter-model.md).

## Review Checklist

- JSON parses as UTF-8.
- Required official docs were consulted or the limitation was stated.
- Format versions match the file type and project convention.
- Client entity references resolve to existing geometry identifiers and animation/controller names.
- Animation/controller short names resolve to full resource names.
- Controller states/cases contain no full `animation.*` resource names used as substitutes for missing short-name bindings.
- Multi-part animations have distinct registered short names for each resource before their Molang blend weights are reviewed.
- Animation bone names exist in the target geometry when the geometry is known.
- Target bone pivots/origins were checked before changing rotation effects; any rotation/position compensation or direct pivot edit is intentional.
- Locator references exist in the target geometry when used by effects/events.
- Controller transitions and blend settings follow the intended project style.
- Molang data source, return shape, and 20tick smoothness risks are checked.
- Molang expressions are scanned for adjacent operator pairs before finalizing.
- Segmented soft-body assets use the intended topology: whole visible segments under visible bones, wrapper axes at joint edges, no seam-covering patch cubes, no accidental sibling split-chain.
- Animation axes match the intended physical bend. For left/right grass sway this usually means Z-axis bend only; do not add Y-axis twist unless the user explicitly asks for twist/four-direction behavior.
- Root-motion review states the model-unit scale, clock mapping, axis mapping, interpolation, net model displacement, visible-root ownership, and server handoff; it does not claim actor animation alone moved the entity.
- `.build/dist` is untouched.
