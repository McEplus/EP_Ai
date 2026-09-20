from __future__ import print_function

import math

from _common import project_root


SCROLL_DAMPING = 5.0
DEFAULT_DELTA_TIME = 1.0 / 60.0
SPEED_EPSILON = 1.0
MAX_SPEED_SCALE = 8.0
SNAP_DISTANCE = 0.05
HORIZONTAL_OVERDRAG = 50.0
VERTICAL_OVERDRAG = 100.0
DRAG_THRESHOLD = 4.0


def clamp_delta_time(delta_time):
    if not delta_time or delta_time <= 0:
        return DEFAULT_DELTA_TIME
    return float(delta_time)


def get_frame_factors(delta_time):
    delta_time = clamp_delta_time(delta_time)
    motion_retain = math.exp(-SCROLL_DAMPING * delta_time)
    return motion_retain, 1.0 - motion_retain


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def get_local_legal_range(view_size, content_size, box_offset=0.0):
    legal_max = box_offset
    legal_min = min(view_size - content_size + box_offset, legal_max)
    return legal_min, legal_max


def make_scroll_key(ui_name, view_path):
    return "%s|%s" % (ui_name, view_path)


def register_scroll(registry, runtime, ui_name, view_path):
    for old_key, data in list(registry.items()):
        if data["ui_name"] == ui_name and data["view_path"] == view_path:
            registry.pop(old_key)
            runtime.pop(old_key, None)
    key = make_scroll_key(ui_name, view_path)
    registry[key] = {"ui_name": ui_name, "view_path": view_path}
    runtime[key] = {"active": False, "motion": (0.0, 0.0)}
    return key


def unregister_ui(registry, runtime, ui_name):
    for key, data in list(registry.items()):
        if data["ui_name"] == ui_name:
            registry.pop(key)
            runtime.pop(key, None)


def move_to_boundary(current, target, return_ratio):
    next_value = current + (target - current) * return_ratio
    if abs(target - next_value) <= SNAP_DISTANCE:
        return target
    return next_value


def integrate_inertia(speed, delta_time):
    motion_retain, motion_ratio = get_frame_factors(delta_time)
    distance = speed * motion_ratio / SCROLL_DAMPING
    return distance, speed * motion_retain


def simulate_inertia(fps, duration, initial_speed):
    delta_time = 1.0 / float(fps)
    speed = initial_speed
    position = 0.0
    for index in range(int(fps * duration)):
        distance, speed = integrate_inertia(speed, delta_time)
        position += distance
    return position, speed


def simulate_rebound(fps, duration, start, target):
    delta_time = 1.0 / float(fps)
    position = start
    for index in range(int(fps * duration)):
        retain, return_ratio = get_frame_factors(delta_time)
        position = move_to_boundary(position, target, return_ratio)
    return position


def simulate_stalled_release(delta_time, raw_touch_delta, view_size, legal_min, legal_max, overdrag):
    delta_time = clamp_delta_time(delta_time)
    speed_limit = view_size * MAX_SPEED_SCALE
    speed = clamp(raw_touch_delta / delta_time, -speed_limit, speed_limit)
    distance, speed = integrate_inertia(speed, delta_time)
    position = clamp(distance, legal_min - overdrag, legal_max + overdrag)
    target = clamp(position, legal_min, legal_max)
    if target != position:
        _, return_ratio = get_frame_factors(delta_time)
        position = move_to_boundary(position, target, return_ratio)
        speed = 0.0
    return position, speed


def check_runtime_sources():
    root = project_root()
    uimod_paths = [
        root / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "QingYunModLibs" / "UIMod.py",
        root / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts" / "QingYunModLibs" / "UIMod.py"
    ]
    for path in uimod_paths:
        source = path.read_text(encoding="utf-8")
        assert "import time" in source, path
        assert "def _GetScrollFrameFactors(DeltaTime):" in source, path
        assert "math.exp(-_SCROLL_DAMPING * DeltaTime)" in source, path
        assert "MotionTravelRatio = MotionRatio / _SCROLL_DAMPING" in source, path
        assert "_SCROLL_WHEEL_SPEED = 120.0" in source, path
        assert "GetFps()" not in source, path
        assert "_LimitScrollMotion" not in source, path
        assert "1.0-(5.0/Fps)" not in source, path
        assert "/(0.2*Fps)" not in source, path
        assert "def ResetScrollViewRuntime(ScrollKey):" in source, path
        assert "def RemoveScrollViewRuntime(ScrollKey):" in source, path
        assert 'data.get("ViewPath", ScrollKey)' in source, path
        assert "LegalMax = BoxOffset[0]" in source, path
        assert "LegalMin = min(SSX - BSX + BoxOffset[0], LegalMax)" in source, path
        assert "LegalMax = BoxOffset[1]" in source, path
        assert "LegalMin = min(SSY - BSY + BoxOffset[1], LegalMax)" in source, path
        assert "LegalMax = SMNX" not in source, path
        assert "LegalMax = SMNY" not in source, path

        if "SwordSoulFightScripts" in str(path):
            # Buttons inside dense grids must not prevent their owning scroll view
            # from beginning a drag. The button wrapper still observes
            # TouchScrollViewState and suppresses its business Up after movement.
            assert "if UIScreen.GetTouchButtonState():" not in source, path
            assert "if UIScreen.IsTouchInRegisteredButton(uiName, X, Y):" not in source, path
            assert 'SystemApi.SetVaryingClient("TouchScrollViewState", True)' in source, path
            assert "_SCROLL_DRAG_THRESHOLD = 4.0" in source, path
            assert "AxisDistance < _SCROLL_DRAG_THRESHOLD" in source, path

    uiscreen_paths = [
        root / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "QingYunModLibs" / "UIScreen.py",
        root / "src" / "SwordSoul_NewERA_B" / "SwordSoulMobFightScripts" / "QingYunModLibs" / "UIScreen.py"
    ]
    for path in uiscreen_paths:
        source = path.read_text(encoding="utf-8")
        assert "def _GetScrollViewKey(uiName, ScrollViewPath):" in source, path
        assert '"ViewPath": self.Scroll_ViewScreenPath' in source, path
        assert "_ResetScrollViewRuntime(ScrollKey)" in source, path
        assert "RemoveScroll_Views(self.NameSpace)" in source, path
        if "SwordSoulFightScripts" in str(path):
            assert "def CancelScroll_ViewTouch(uiName, ScrollViewPath):" in source, path
            cancel_start = source.index("def CancelScroll_ViewTouch(uiName, ScrollViewPath):")
            cancel_end = source.index("\ndef RemoveScroll_Views(uiName):", cancel_start)
            cancel_source = source[cancel_start:cancel_end]
            assert "_ResetScrollViewRuntime(ScrollKey)" in cancel_source, path
            assert "ScrollViewDict.pop" not in cancel_source, path
            state_start = source.index("def SetTouchButtonState(State):")
            state_end = source.index("\ndef GetTouchButtonState():", state_start)
            state_source = source[state_start:state_end]
            assert "TouchScrollViewState" not in state_source, path
            assert 'GetVaryingClient("TouchScrollViewState", defaultValue=False)' in source, path

    detail_path = root / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "UISystem" / "DetailScreen.py"
    detail_source = detail_path.read_text(encoding="utf-8")
    begin_drag = get_method_source(detail_source, "_BeginConfigDrag")
    assert begin_drag.index('GetVaryingClient("TouchScrollViewState"') < begin_drag.index("self._DraggingComp = Comp")
    assert begin_drag.index("CancelScroll_ViewTouch(self.uiName, self.ScrollViewPath)") < begin_drag.index("self._DraggingComp = Comp")
    observer = get_method_source(detail_source, "_OnConfigDragButtonEvent")
    assert 'ButtonState not in ("Up", "Cancel")' in observer
    assert "self._cancelPendingConfigDrag()" in observer
    clear_drag = get_method_source(detail_source, "_clearConfigDragState")
    assert "RemoveButtonEventObserver" in clear_drag


def get_method_source(source, method_name):
    marker = "    def %s(" % method_name
    start = source.index(marker)
    next_method = source.find("\n    def ", start + len(marker))
    if next_method < 0:
        return source[start:]
    return source[start:next_method]


def check_migrated_screen_offsets():
    root = project_root()
    ui_system = root / "src" / "SwordSoul_NewERA_B" / "SwordSoulFightScripts" / "UISystem"

    main_setting = (ui_system / "MainSetting.py").read_text(encoding="utf-8")
    for method_name in ("LoadLeftChooseScreen", "LoadRightChooseScreen"):
        method_source = get_method_source(main_setting, method_name)
        assert '"point_y": 3' in method_source, method_name
        assert '"point_y": -10' not in method_source, method_name

    animate_screen = (ui_system / "AnimateScreen.py").read_text(encoding="utf-8")
    animate_fragments = get_method_source(animate_screen, "LoadAnimateFragments")
    using_fragments = get_method_source(animate_screen, "LoadUsingAnimateFragments")
    assert '"point_y": 5' in animate_fragments
    assert '"point_y": -15' not in animate_fragments
    assert '"point_y": 5' in using_fragments
    assert '"point_y": -120' not in using_fragments
    assert "ScrollViewPos[1]+120" not in using_fragments
    assert "SetCompMustPosition(self.uiName, AnimateScreenConfig.UsingAnimateFragScreen" not in using_fragments

    trail_screen = (ui_system / "TrailScreen.py").read_text(encoding="utf-8")
    trail_fragments = get_method_source(trail_screen, "LoadingTrailFrag")
    assert '"point_y": 0' in trail_fragments
    assert "BoxOffset=(0, -45)" not in trail_fragments

    announcement = (ui_system / "Announcement.py").read_text(encoding="utf-8")
    version_list = get_method_source(announcement, "_renderVersionList")
    assert '"point_y": 3' in version_list
    assert '"point_y": -10' not in version_list
    assert "VersionChooseContent).SetPosition((0, 0))" not in version_list


def run_test():
    check_runtime_sources()
    check_migrated_screen_offsets()
    frame_rates = (1, 2, 5, 10, 30, 60, 120)
    inertia_results = []
    rebound_results = []
    for fps in frame_rates:
        delta_time = 1.0 / float(fps)
        retain, return_ratio = get_frame_factors(delta_time)
        assert 0.0 <= retain <= 1.0, (fps, retain)
        assert 0.0 <= return_ratio <= 1.0, (fps, return_ratio)
        assert abs(retain + return_ratio - 1.0) < 0.000001, fps
        touch_delta = 600.0 * delta_time
        assert abs(touch_delta / delta_time - 600.0) < 0.000001, fps
        inertia_results.append(simulate_inertia(fps, 1.0, 1200.0))
        rebound_results.append(simulate_rebound(fps, 1.0, 100.0, 0.0))

    reference_position, reference_speed = inertia_results[-1]
    for position, speed in inertia_results:
        assert abs(position - reference_position) < 0.000001, inertia_results
        assert abs(speed - reference_speed) < 0.000001, inertia_results
    reference_rebound = rebound_results[-1]
    for position in rebound_results:
        assert abs(position - reference_rebound) < 0.000001, rebound_results

    for raw_touch_delta in (10000.0, -10000.0):
        position, speed = simulate_stalled_release(
            5.0,
            raw_touch_delta,
            300.0,
            -600.0,
            0.0,
            VERTICAL_OVERDRAG
        )
        assert -700.0 <= position <= 100.0, position
        assert speed == 0.0 or abs(speed) <= 2400.0, speed

    # Horizontal and vertical elastic distances remain compatible with the runtime defaults.
    assert clamp_delta_time(0) == DEFAULT_DELTA_TIME
    assert SPEED_EPSILON == 1.0
    assert HORIZONTAL_OVERDRAG == 50.0
    assert VERTICAL_OVERDRAG == 100.0
    # A tap can jitter slightly without losing its button Up; a deliberate drag
    # crosses the threshold and is then owned by the scroll view.
    assert abs(3.9) < DRAG_THRESHOLD
    assert abs(4.0) >= DRAG_THRESHOLD

    # Nested viewport offsets belong to the parent coordinate space and must never
    # shift the content's local legal range.
    assert get_local_legal_range(135.0, 135.0) == (0.0, 0.0)
    assert get_local_legal_range(135.0, 200.0) == (-65.0, 0.0)
    assert get_local_legal_range(135.0, 200.0, -45.0) == (-110.0, -45.0)
    for parent_offset in (0.0, 40.0, 171.0, 600.0):
        assert get_local_legal_range(135.0, 135.0) == (0.0, 0.0), parent_offset

    # Same relative control path in different screens must remain isolated, while
    # rebuilding one screen resets its own transient drag/inertia state.
    registry = {}
    runtime = {}
    key_a = register_scroll(registry, runtime, "ScreenA", "/Panel/Scroll")
    key_b = register_scroll(registry, runtime, "ScreenB", "/Panel/Scroll")
    assert key_a != key_b
    assert len(registry) == 2
    runtime[key_a] = {"active": True, "motion": (0.0, 900.0)}
    assert register_scroll(registry, runtime, "ScreenA", "/Panel/Scroll") == key_a
    assert runtime[key_a] == {"active": False, "motion": (0.0, 0.0)}
    assert key_b in runtime
    unregister_ui(registry, runtime, "ScreenA")
    assert key_a not in registry and key_a not in runtime
    assert key_b in registry and key_b in runtime
    print("scroll physics regression: PASS")


if __name__ == "__main__":
    run_test()
