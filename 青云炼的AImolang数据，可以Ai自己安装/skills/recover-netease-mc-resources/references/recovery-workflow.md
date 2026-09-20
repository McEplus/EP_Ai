# Owner-authorized NetEase pack recovery workflow

This reference captures a successful local recovery case and the failed approaches
that mattered. The cipher details are a case study, not a universal NetEase format.

## Contents

1. [Evidence ladder](#evidence-ladder)
2. [Observed encrypted format](#observed-encrypted-format)
3. [Probe and candidate validation](#probe-and-candidate-validation)
4. [Runtime strategy](#runtime-strategy)
5. [Performance lessons](#performance-lessons)
6. [Intrusive approaches to avoid](#intrusive-approaches-to-avoid)
7. [Recovery output](#recovery-output)
8. [Bedrock semantic organization](#bedrock-semantic-organization)
9. [Failure and fallback](#failure-and-fallback)

## Evidence ladder

Work from least to most invasive:

1. Installed RP/BP filesystem inventory.
2. Existing source-control history, editor backups, creator exports, and old devices.
3. Plaintext files, manifests, texts, models, or already-decompiled pack scripts.
4. Header/ciphertext characterization with bounded reads.
5. Offline analysis of user-owned helper/unpacker binaries.
6. External read-only inspection of the exact game process after the user naturally
   loads their own pack.
7. Stop before credentials, process dumps, executable patching, or anti-cheat bypass.

Record observed facts separately from inference at every step.

## Observed encrypted format

In one recovered pack, all target animation/controller JSON files had:

- a 64-byte wrapper header;
- an ASCII UUID beginning at byte 4;
- ciphertext beginning at byte 64;
- a 16-byte ASCII content key;
- AES-128 CFB with the key bytes also used as the IV;
- CFB segment size 8 for the validated output.

Equivalent case-study logic was:

```python
plaintext = AES.new(key_bytes, AES.MODE_CFB, key_bytes, segment_size=8).decrypt(blob[64:])
```

Do not copy this assumption to another pack without validation. Test CFB8 and CFB128
only when static evidence supports this family, and accept neither until the expected
JSON probe validates.

Never print, log, or save `key_bytes`.

## Probe and candidate validation

Choose one small or distinctive encrypted file as the probe. Record its exact path,
size, header, and expected resource root.

Use a staged validator:

1. Decrypt only the first 256 bytes.
2. Require plausible UTF-8/JSON structure and an expected marker such as
   `format_version`, `animations`, `animation_controllers`, or
   `minecraft:client_entity`.
3. Only then decrypt the full probe.
4. Decode with strict UTF-8.
5. Parse with a real JSON parser.
6. Require the exact expected top-level object and reasonable definition count.

Do not accept printable text, braces, or a partial prefix alone. False positives are
common when testing many candidates.

## Runtime strategy

Prefer an external, read-only process reader:

- Open only the confirmed official game PID with query/read rights.
- Enumerate committed, readable regions.
- Prefer `MEM_PRIVATE` pages to avoid rescanning executable/image data.
- Read in bounded blocks with overlap only where candidate boundaries require it.
- Search narrowly shaped candidates supported by static evidence.
- Validate in memory and write only successfully parsed, in-scope plaintext.

Candidate shapes that were useful in the successful case:

- 16-byte low-ASCII strings inside short 16-24 byte runs;
- AES-128 expanded key schedules in direct and per-word-reversed layouts.

Expanded schedule detection can reject most memory positions by checking only the
first derived round words before reconstructing the original 16-byte candidate.
Scan on a conservative alignment such as 8 bytes unless evidence requires finer
alignment.

For deduplication, store a fixed-size candidate fingerprint such as FNV-1a 64-bit,
not a Base64 string for every candidate. A fingerprint collision is theoretically
possible, so document this tradeoff; for a bounded local scan it is usually
preferable to unbounded memory growth.

When a candidate validates:

1. Keep it only in process memory.
2. Decrypt the explicit allowlisted paths.
3. Validate every plaintext before writing.
4. Clear the candidate and expanded schedules when practical.
5. Exit the scanner.

## Performance lessons

Three implementation mistakes caused major slowdowns in the case study:

1. Allocating a full 176-byte AES key schedule at every 4-byte position.
   Replace this with allocation-free first-round checks.
2. Fully decrypting a roughly 190 KB probe for every superficially plausible
   candidate. Validate a 256-byte prefix first.
3. Deduplicating with `HashSet<string>` of Base64 candidates. This grew to hundreds
   of MB. Use fixed-size fingerprints and restrict ASCII run lengths.

Useful runtime telemetry:

- bytes scanned;
- candidates tested;
- scanner CPU and working set;
- game `Responding` state;
- elapsed time and current region count.

Check at least every 30 seconds. After a command timeout, explicitly confirm that no
scanner child process remains.

## Intrusive approaches to avoid

The following approaches were ineffective or destabilizing in the case study:

- global `RtlAllocateHeap` hooks;
- global `memcpy`/`memmove` hooks;
- broad allocator/copy interception through Frida;
- repeated in-process object/stack scans during world loading;
- OpenSSL/AES/CNG hooks when the client used a custom/internal implementation;
- searching only near UUID strings in memory;
- waiting for raw ciphertext to remain resident;
- full process dumps.

Global hooks generated extreme event volume and caused lag or automatic client exit.
Raw ciphertext disappeared quickly while UUID metadata remained, so UUID-adjacent
candidate scans produced no validated key. These failures are evidence to narrow the
next attempt, not justification to become more invasive.

Never retrieve account tokens to make a legacy unpacker login work. Treat the tool as
incompatible and use owner-supported recovery routes instead.

## Recovery output

Write to a new workspace-local directory. Preserve:

- original relative path;
- source encrypted filename;
- SHA-256 of the source;
- detected wrapper UUID/header family;
- recovered resource type and `format_version`;
- validation result and definition count.

Recommended validation for Bedrock JSON:

- strict UTF-8 JSON parsing;
- actor animations use an `animations` object;
- animation controllers use an `animation_controllers` object;
- client entities contain `minecraft:client_entity` under `minecraft:client_entity`
  format conventions appropriate to that version;
- no duplicate full identifiers across output files;
- expected file and definition counts match the target inventory.

Keep false positives in a separate diagnostic location and never count them as
recovered target files.

## Bedrock semantic organization

Recovered marketplace filenames may remain opaque even after decryption. Organize by
resource identifiers rather than filename guesses:

1. Parse every JSON object.
2. Classify full animation/controller identifiers by the longest exact entity token.
3. Use bone names, controller names, and source-file co-occurrence as corroboration.
4. Put generic actions, turn overlays, item poses, setup, and shared controllers in a
   `common` group.
5. Split mixed batch files only at the definition boundary.
6. Preserve every definition value exactly during the first organization pass.
7. Aggregate before/after definitions and require deep equality.
8. Generate a mapping from every semantic output identifier back to the original
   opaque filename.

For animation behavior analysis, trace:

```text
client entity animations alias
-> scripts.animate entry
-> animation controller
-> actor animation full identifier
-> animated bones
-> geometry bones/pivots
```

If client entity bindings remain encrypted, label alias mapping and pre-animation
variable producers as unresolved rather than inferred fact.

## Failure and fallback

Stop after repeated bounded failures with no new evidence. Do not escalate into
credential access, executable modification, anti-cheat bypass, or broad dumping.

Fallback routes:

- Git/source-control reflog and editor history;
- old machines, disks, cloud backups, zip exports, and build artifacts;
- NetEase creator-console versions or official support/export;
- decompiled user-owned BP scripts;
- reconstruction from current project resources;
- manual semantic migration of the successfully recovered subset.

Report exactly what was recovered, what remains encrypted, and which missing layer
blocks further proof.
