# NetEase Minecraft local pack layout

Use this reference for read-only discovery and process selection. Paths vary by
launcher channel and client version; treat these as patterns, not universal facts.

## Common roots

NetEase Bedrock interoperability builds commonly store installed content below a
roaming profile root resembling:

```text
%APPDATA%\MinecraftPC_Netease_*\games\com.netease\
```

Typical installed pack names encode the marketplace/item ID and side:

```text
resource_packs\<item-id>_resource_packs_R
behavior_packs\<item-id>_behavior_packs_B
```

MC Studio development clients commonly live in a separate installation such as:

```text
D:\MCStudioDownload\game\MinecraftPE_Netease\<version>\
```

Do not assume the MC Studio process is the official client that loaded an installed
marketplace pack.

## Useful resource-pack directories

```text
animation_controllers/
animations/
attachables/
entity/
materials/
models/
particles/
render_controllers/
shaders/
sounds/
texts/
textures/
ui/
```

Behavior packs may include entities, functions, loot tables, Python `.mcp` content,
scripts, and NetEase-specific configuration. Inventory both RP and BP before deciding
that source is absent.

## Discovery procedure

1. Search exact item ID first when known.
2. Otherwise inspect pack directory names, manifests, text assets, and timestamps.
3. Record RP and BP absolute paths together; one side can identify the other.
4. Count files by top-level directory and extension.
5. Read only a bounded prefix to classify plaintext JSON versus encrypted/binary
   content.
6. Hash important inputs before recovery; never rename or overwrite installed files.

Run the bundled inspector:

```powershell
python "$env:USERPROFILE\.codex\skills\recover-netease-mc-resources\scripts\inspect_netease_pack.py" <pack-root>
```

## Process selection checklist

For every candidate `Minecraft.Windows.exe`, record:

- PID;
- full executable path;
- process start time;
- responsiveness;
- parent/launcher context when available.

The official client and MC Studio client can run simultaneously with the same process
name. Select by exact executable path, not name alone. Re-resolve the PID after every
restart.

## Encrypted-header recognition

One observed NetEase pack family used a 64-byte wrapper:

```text
offset 0x00: 4-byte marker
offset 0x04: 36-byte ASCII UUID
offset 0x28: zero/reserved padding through 0x3f
offset 0x40: ciphertext
```

This signature is strong evidence for that wrapper family but does not prove the
cipher, key, or IV. Confirm with a known probe and successful JSON validation. Other
client versions or content systems may use different layouts.

## What not to use as proof

- A `.json` suffix does not prove plaintext.
- A UUID in a header does not prove that nearby memory contains the key.
- Old third-party unpackers do not prove current compatibility.
- A login failure does not authorize token extraction.
- Finding a plausible 16-byte string does not prove a key without deterministic
  plaintext and full JSON validation.
