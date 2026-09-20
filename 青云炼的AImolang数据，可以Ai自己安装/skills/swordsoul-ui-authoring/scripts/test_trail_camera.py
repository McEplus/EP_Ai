#!/usr/bin/env python3
"""刀光编辑器预览相机Roll、拖动惯性与生命周期回归。"""

from __future__ import print_function

from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
TRAIL_SCREEN = ROOT / "src/SwordSoul_NewERA_B/SwordSoulFightScripts/UISystem/TrailScreen.py"


def method_source(source, name):
    marker = "    def %s(" % name
    start = source.index(marker)
    end = source.find("\n    def ", start + len(marker))
    return source[start:] if end < 0 else source[start:end]


def load_frame_tick(source):
    namespace = {}
    class_source = "class TrailCameraProbe(object):\n" + method_source(source, "OnDragFrameTick")
    exec(compile(class_source, str(TRAIL_SCREEN), "exec"), namespace)
    return namespace["TrailCameraProbe"]


def load_apply_rotation(source, client_api):
    namespace = {"ClientApi": client_api}
    class_source = "class TrailCameraApplyProbe(object):\n" + method_source(
        source, "_applyCameraPreviewRotation"
    )
    exec(compile(class_source, str(TRAIL_SCREEN), "exec"), namespace)
    return namespace["TrailCameraApplyProbe"]


def main():
    source = TRAIL_SCREEN.read_text(encoding="utf-8")
    open_source = method_source(source, "OnOpen")
    close_source = method_source(source, "OnClose")
    drag_start_source = method_source(source, "OnDragStart")
    frame_source = method_source(source, "OnDragFrameTick")
    drag_end_source = method_source(source, "OnDragEnd")
    init_source = method_source(source, "InitCamera")
    restore_source = method_source(source, "RestoreCamera")

    assert "self.CameraRoll = 10.0" in source
    assert "self.CameraTickListening = False" in source
    assert "Ry-45, self.CameraRoll" in open_source
    assert "self._scheduleCameraPreviewTick()" in open_source
    assert "self._startCameraPreviewTick()" not in init_source
    assert "self._startCameraPreviewTick()" in drag_start_source
    assert "ClientMod.CreateTimer(0.51, StartPreviewTick, False)" in source
    assert "if not self.Editing or self.Closing:" in source
    assert "self._cancelCameraPreviewStart()" in close_source
    assert "self._stopCameraPreviewTick()" in close_source
    assert close_source.index("self._cancelCameraPreviewStart()") < close_source.index("self.PlayerCloseAnimation()")
    assert close_source.index("self._stopCameraPreviewTick()") < close_source.index("self.PlayerCloseAnimation()")
    assert "self._cancelCameraPreviewStart()" in restore_source
    assert "self._stopCameraPreviewTick()" in restore_source
    assert "ListenClientEvents" not in drag_start_source
    assert "UnListenClient" not in frame_source
    assert "UnListenClient" not in drag_end_source
    assert frame_source.count("self._applyCameraPreviewRotation()") == 1
    assert "SetCameraRotation" not in frame_source

    rotations = []
    camera_api = type("CameraApi", (), {
        "SetCameraRotation": staticmethod(rotations.append)
    })
    player_api = type("PlayerApi", (), {"Camera": camera_api})
    client_api = type("ClientApiProbe", (), {"Player": player_api})
    apply_probe = load_apply_rotation(source, client_api)()
    apply_probe.CameraPitch = -10.0
    apply_probe.CameraYaw = 35.0
    apply_probe.CameraRoll = 10.0
    apply_probe._applyCameraPreviewRotation()
    assert rotations == [(-10.0, 35.0, 10.0)]

    probe = load_frame_tick(source)()
    probe.LastTouchPos = None
    probe.IsInertia = False
    probe.CameraVelocityX = 0.0
    probe.CameraVelocityY = 0.0
    probe.CameraYaw = 20.0
    probe.CameraPitch = -10.0
    applied = []
    probe._applyCameraPreviewRotation = lambda: applied.append(
        (probe.CameraPitch, probe.CameraYaw, probe.CameraVelocityX, probe.CameraVelocityY)
    )
    probe.OnDragFrameTick()
    assert applied == [(-10.0, 20.0, 0.0, 0.0)]

    applied[:] = []
    probe.IsInertia = True
    probe.CameraVelocityX = 0.01
    probe.CameraVelocityY = -0.01
    probe.OnDragFrameTick()
    assert probe.IsInertia is False
    assert probe.CameraVelocityX == 0.0 and probe.CameraVelocityY == 0.0
    assert len(applied) == 1

    applied[:] = []
    probe.IsInertia = True
    probe.CameraVelocityX = 2.0
    probe.CameraVelocityY = -1.0
    old_yaw, old_pitch = probe.CameraYaw, probe.CameraPitch
    probe.OnDragFrameTick()
    assert probe.CameraYaw != old_yaw and probe.CameraPitch != old_pitch
    assert len(applied) == 1

    print("trail camera roll regression: PASS")


if __name__ == "__main__":
    main()
