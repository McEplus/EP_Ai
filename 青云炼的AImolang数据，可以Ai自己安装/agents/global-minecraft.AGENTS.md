# Global filesystem deletion safety

- Unless the user explicitly authorizes the exact deletion scope, do not bulk-delete, recursively delete, mass-clean, or otherwise remove large numbers of files or directories from a project.
- Never delete files or directories outside the current project/workspace unless the user explicitly names the external target and clearly authorizes its deletion.
- Before any authorized bulk or external deletion, resolve and verify the absolute target paths, report what will be removed, and keep the operation strictly within the user-approved scope.
- When deletion authority is absent or ambiguous, limit work to read-only inspection and ask the user for confirmation; do not infer permission from cleanup, refactoring, build, migration, or troubleshooting requests.

# Minecraft API documentation verification

- Before writing any Minecraft-related project code that uses a Minecraft, Bedrock, NetEase ModAPI, component, event, UI-control method, or other engine API not already used by the current project's runtime source, first verify the exact API symbol in the applicable official interface documentation.
- For NetEase Minecraft work, query the ModAPI documentation tools for the exact method or event name and verify its existence, client/server side, parameters, return value, platform restrictions, and relevant usage notes before implementation.
- If the exact API symbol cannot be found in the official interface documentation, do not write or call it. Stop and report that it is undocumented or unverified, then use a documented alternative or request explicit direction from the user.
- Calls found only in old projects, third-party libraries, wrappers, engine stubs, examples, search results, or remembered code do not prove that an API exists or is supported. They may be supporting evidence only after the official documentation confirms the exact symbol.
- Do not infer an API by adding a plausible suffix, changing a documented method name, or guessing from neighboring interfaces. Exact-name documentation verification is mandatory.
- Before implementing a newly verified Minecraft API, briefly report the documentation result and any platform or environment limitation that affects testing or release behavior.

# Global task completion audio

- After a user-requested task is genuinely complete and immediately before the final response, play the global completion sound by running `powershell -NoProfile -ExecutionPolicy Bypass -File "$HOME/.codex/skills/task-completion-chime/scripts/play_completion_chime.ps1"`.
- This rule applies in every project and workspace. Use the user-level audio asset at `C:\Users\Administrator\.codex\assets\completion_chime.mp3`; do not replace it unless the user explicitly requests another sound.
- Play the sound only for genuine task completion. Do not play it for status updates, partial progress, clarification questions, blocked work, failed tasks, or turns that only explain information without completing requested work.
- Treat playback as a courtesy notification: if it fails because audio output or Windows playback is unavailable, briefly report the playback failure without treating the completed task as failed.
