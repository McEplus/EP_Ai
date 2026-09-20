# AI collaboration rules

## MODSDKSpring notification channels

- Treat `@AllowNotify` as part of the `MODSDKSpring.Network.NotifyManage` RPC channel, not as a handler for a system's native `NotifyToClient` or `NotifyToMultiClients` methods.
- A client/server method decorated with `@AllowNotify` must be called through the matching functions imported from `EpJxkScript.plugins.MODSDKSpring.Network.NotifyManage`: `NotifyToClient`, `NotifyToMultiClients`, `BroadcastToAllClient`, or `NotifyToServer` as appropriate.
- Never mix an `@AllowNotify` receiver with `self.NotifyToClient`, `self.NotifyToMultiClients`, or another engine/system-native notification API. Those native APIs require an explicitly registered/listened native event with the matching namespace and system name.
- When adding or reviewing cross-end communication, verify the complete pair before considering it working: sender API, event/RPC name, receiver registration mechanism, namespace/system, target player, and payload shape.
- Do not treat successful execution of the sender, swallowed chat text, or absence of an exception as proof that the receiver ran. Add a focused test or runtime trace at the receiver boundary when practical.

## Generated test artifacts

- Every AI conversation in this project must clean up disposable artifacts it creates during testing or validation before finishing the task.
- Cleanup includes `__pycache__`, `*.pyc`, `*.pyo`, `*.tmp`, ad-hoc test scripts, temporary test output files, and other files created only for validation.
- Python syntax checks and test discovery can generate bytecode beside production and test sources. Prefer commands that suppress bytecode generation when supported, such as `python -B`, or set `PYTHONDONTWRITEBYTECODE=1` for the command.
- After Python tests or `py_compile`, explicitly search the workspace for newly generated `__pycache__`, `*.pyc`, and `*.pyo`, then remove them before reporting completion.
- Before recursive cleanup, resolve and verify every target is inside the intended workspace. Do not remove user-authored files, checked-in fixtures, caches required by the game runtime, or project assets.
