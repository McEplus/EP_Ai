---
name: recover-netease-mc-resources
description: Safely inspect, diagnose, recover, validate, and semantically organize owner-authorized NetEase China Minecraft Bedrock local resource/behavior packs, including 网易我的世界基岩互通版 local mod discovery, encrypted JSON/header recognition, low-intrusion runtime recovery planning, animation/controller source restoration, and recovery audit reports. Use only for assets the user owns or is explicitly authorized to recover; never use it to obtain account credentials, tokens, third-party marketplace content, or generalized DRM-bypass tooling.
---

# Recover NetEase MC Resources

Recover user-owned NetEase Minecraft local pack sources with a static-first,
evidence-driven workflow. Preserve installed files and produce a separate recovery
directory.

## Required agent

Before taking task actions, read the complete user-level agent at:

`%USERPROFILE%\.codex\agents\netease-mc-resource-recovery-agent.md`

If it is unavailable, apply the authorization and safety rules below directly and
report the missing agent.

## Authorization gate

Require the user to identify the exact local pack and state ownership or explicit
authorization before decrypting or inspecting another process. If authorization is
unclear, limit work to filesystem inventory and encrypted-format identification,
then request confirmation.

Never:

- retrieve, request, display, or persist account tokens, cookies, session secrets,
  launcher credentials, or server authentication material;
- recover unrelated third-party marketplace packs;
- patch the game, disable anti-cheat, automate login, or contact private APIs;
- write a reusable credential/key extractor or print recovered content keys;
- create full process dumps, which can contain unrelated secrets;
- delete or overwrite installed packs or trigger a game/resource reload without
  explicit permission.

## Routing

1. For pack discovery and format inventory, read
   [references/pack-layout.md](references/pack-layout.md), then run
   `scripts/inspect_netease_pack.py`.
2. For encrypted JSON recovery or runtime inspection, read
   [references/recovery-workflow.md](references/recovery-workflow.md) completely.
3. For recovered animation/controller analysis, also use an available Bedrock
   animation skill and official Minecraft Creator documentation.
4. For recovery validation, run `scripts/validate_recovered_resources.py`.

## Core workflow

1. Resolve the exact RP/BP roots, pack/item ID, client version, and target file
   classes. Record absolute paths; distinguish the official client from MC Studio.
2. Inventory first. Parse plaintext JSON normally and identify encrypted candidates
   from bounded header reads. Do not infer encryption solely from a `.json` suffix.
3. Search authorized backups, developer exports, creator-console branches, caches,
   and already-decrypted script artifacts before considering runtime inspection.
4. Establish a known encrypted probe and a deterministic plaintext validator.
   Accept a candidate only after UTF-8 decoding, JSON parsing, and expected-root
   validation.
5. Prefer an external read-only process reader over in-process injection. Inspect
   only the exact official game PID while the user has intentionally loaded their
   own pack. Bound memory, candidate count, runtime, and output paths.
6. Keep a recovered key ephemeral: never print or save it, decrypt only in-scope
   paths, clear buffers when practical, and write only validated plaintext.
7. Recover into a new workspace-local directory. Preserve original encrypted files,
   relative paths, and a source-to-output manifest.
8. Validate all outputs, counts, format versions, duplicate resource identifiers,
   and expected Bedrock root objects. Organize mixed animation batches only after
   equality checks against the recovered definitions.
9. Report evidence, uncertainty, failed approaches, output locations, and whether
   any runtime process remains attached.

## Reusable commands

Static inventory:

```powershell
python "$env:USERPROFILE\.codex\skills\recover-netease-mc-resources\scripts\inspect_netease_pack.py" <pack-root>
```

Recovery validation:

```powershell
python "$env:USERPROFILE\.codex\skills\recover-netease-mc-resources\scripts\validate_recovered_resources.py" <recovery-root> --strict
```

Both scripts are read-only.

## Completion criteria

- Original installed resources remain untouched.
- Every reported plaintext file parses and has the expected resource root.
- Identifier counts and duplicates are reported.
- No credential, token, content key, or unrelated memory is persisted.
- Runtime helpers have exited and the game remains responsive, if runtime inspection
  was authorized.
- The final response links the recovered directory, manifest/audit, and any reusable
  local tools created for the authorized task.
