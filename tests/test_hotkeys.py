from flowstate.hotkeys.manager import (
    VK_LCONTROL,
    VK_LMENU,
    VK_LSHIFT,
    VK_LWIN,
    VK_MENU,
    VK_RCONTROL,
    VK_RMENU,
    VK_RSHIFT,
    VK_SPACE,
    HotkeyBinding,
    HotkeyManager,
    bindings_conflict,
    vk_to_tokens,
)

LLKHF_EXTENDED = 0x01
VK_A = ord("A")
VK_D = ord("D")

# vk, flags pairs for common physical keys
CTRL_L = (0x11, 0)
CTRL_R = (0x11, LLKHF_EXTENDED)
ALT_L = (VK_MENU, 0)
ALT_R = (VK_MENU, LLKHF_EXTENDED)
SHIFT_L = (VK_LSHIFT, 0)
SHIFT_R = (VK_RSHIFT, 0)
SPACE = (VK_SPACE, 0)

# Some keyboards/drivers deliver the side-specific VK codes directly at the
# low-level hook instead of the generic VK_CONTROL/VK_MENU + LLKHF_EXTENDED
# pairing above -- both spellings must resolve to the same tokens.
CTRL_L_SIDE_SPECIFIC = (VK_LCONTROL, 0)
CTRL_R_SIDE_SPECIFIC = (VK_RCONTROL, 0)
ALT_L_SIDE_SPECIFIC = (VK_LMENU, 0)
ALT_R_SIDE_SPECIFIC = (VK_RMENU, 0)


def test_vk_to_tokens_side_specific_and_family_for_modifiers():
    assert vk_to_tokens(*ALT_R) == {"alt_r", "alt"}
    assert vk_to_tokens(*ALT_L) == {"alt_l", "alt"}
    assert vk_to_tokens(*CTRL_L) == {"ctrl_l", "ctrl"}
    assert vk_to_tokens(*CTRL_R) == {"ctrl_r", "ctrl"}


def test_vk_to_tokens_for_side_specific_ctrl_and_alt_vk_codes():
    """Regression test for a real bug: some keyboards/drivers send
    VK_LCONTROL/VK_RCONTROL (and VK_LMENU/VK_RMENU) directly at the
    low-level hook instead of the generic VK_CONTROL/VK_MENU code paired
    with LLKHF_EXTENDED. vk_to_tokens only handled the generic pairing,
    so on affected machines every Ctrl (and Alt) press resolved to an
    empty token set -- Ctrl never joined _pressed, so no toggle/ptt
    binding that included ctrl could ever complete. Symptom: hotkeys
    silently do nothing, no matter how they're bound."""
    assert vk_to_tokens(*CTRL_L_SIDE_SPECIFIC) == {"ctrl_l", "ctrl"}
    assert vk_to_tokens(*CTRL_R_SIDE_SPECIFIC) == {"ctrl_r", "ctrl"}
    assert vk_to_tokens(*ALT_L_SIDE_SPECIFIC) == {"alt_l", "alt"}
    assert vk_to_tokens(*ALT_R_SIDE_SPECIFIC) == {"alt_r", "alt"}


def test_vk_to_tokens_for_space_and_letters():
    assert vk_to_tokens(*SPACE) == {"space"}
    assert vk_to_tokens(VK_A, 0) == {"a"}
    assert vk_to_tokens(VK_D, 0) == {"d"}


def test_binding_matches_generic_family():
    binding = HotkeyBinding("ctrl+shift+space")
    assert binding.matches({"ctrl_l", "ctrl", "shift_l", "shift", "space"})
    assert not binding.matches({"ctrl", "space"})


def test_binding_side_specific_alt_r_does_not_match_alt_l():
    binding = HotkeyBinding("alt_r")
    assert binding.matches({"alt_r", "alt"})
    assert not binding.matches({"alt_l", "alt"})


class _Recorder:
    def __init__(self):
        self.toggle_count = 0
        self.ptt_start_count = 0
        self.ptt_stop_count = 0

    def on_toggle(self):
        self.toggle_count += 1

    def on_ptt_start(self):
        self.ptt_start_count += 1

    def on_ptt_stop(self):
        self.ptt_stop_count += 1


def _manager(recorder: _Recorder, toggle="ctrl+shift+space", ptt="alt_r") -> HotkeyManager:
    mgr = HotkeyManager(
        on_toggle=recorder.on_toggle,
        on_ptt_start=recorder.on_ptt_start,
        on_ptt_stop=recorder.on_ptt_stop,
        toggle_spec=toggle,
        push_to_talk_spec=ptt,
    )
    # Override _dispatch to call synchronously for tests (no threads)
    mgr._dispatch = mgr._safe_call = lambda fn: fn()
    return mgr


def _down(mgr, vk_flags):
    return mgr._on_keydown(vk_to_tokens(*vk_flags))


def _up(mgr, vk_flags):
    return mgr._on_keyup(vk_to_tokens(*vk_flags))


def test_toggle_fires_once_on_full_chord_press():
    recorder = _Recorder()
    mgr = _manager(recorder)

    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)

    assert recorder.toggle_count == 1


def test_toggle_does_not_refire_on_autorepeat():
    recorder = _Recorder()
    mgr = _manager(recorder)

    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    _down(mgr, SPACE)  # OS autorepeat while held
    _down(mgr, SPACE)

    assert recorder.toggle_count == 1


def test_toggle_fires_again_after_full_release_and_repress():
    recorder = _Recorder()
    mgr = _manager(recorder)

    for k in (CTRL_L, SHIFT_L, SPACE):
        _down(mgr, k)
    for k in (CTRL_L, SHIFT_L, SPACE):
        _up(mgr, k)
    for k in (CTRL_L, SHIFT_L, SPACE):
        _down(mgr, k)

    assert recorder.toggle_count == 2


def test_push_to_talk_start_and_stop():
    recorder = _Recorder()
    mgr = _manager(recorder)

    _down(mgr, ALT_R)
    assert recorder.ptt_start_count == 1
    assert recorder.ptt_stop_count == 0

    _up(mgr, ALT_R)
    assert recorder.ptt_stop_count == 1


def test_push_to_talk_left_alt_does_not_trigger_right_alt_binding():
    recorder = _Recorder()
    mgr = _manager(recorder)

    _down(mgr, ALT_L)
    assert recorder.ptt_start_count == 0


def test_rebinding_resets_state():
    recorder = _Recorder()
    mgr = _manager(recorder)
    _down(mgr, ALT_R)
    assert recorder.ptt_start_count == 1

    mgr.set_bindings("ctrl+alt+d", "shift_r")
    _up(mgr, ALT_R)  # stale release after rebind: must not fire stop
    assert recorder.ptt_stop_count == 0

    _down(mgr, SHIFT_R)
    assert recorder.ptt_start_count == 2


def test_toggle_survives_when_ptt_keys_are_a_subset_of_toggle_keys():
    """Regression test for a real bug: toggle "ctrl+shift+space" and ptt
    "shift+space" share keys. Pressing the toggle chord used to also
    spuriously satisfy ptt along the way, and releasing any one key a
    moment later (completely normal) fired ptt's *stop* -- killing the
    recording toggle had just started. Symptom looked like "the HUD
    flashes for a second and disappears."."""
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space", ptt="shift+space")

    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 1
    assert recorder.ptt_start_count == 0  # must NOT have activated ptt too

    # Release the keys in a normal, quick order -- must not stop anything,
    # since this is toggle mode: it should stay on until pressed again.
    _up(mgr, SPACE)
    _up(mgr, SHIFT_L)
    _up(mgr, CTRL_L)
    assert recorder.ptt_stop_count == 0
    assert recorder.toggle_count == 1

    # Pressing the toggle chord again turns it back off, as expected.
    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 2


def test_toggle_takes_over_when_ptt_keys_are_pressed_before_ctrl():
    """Same overlapping bindings, but this time the physical press order
    is ptt's own keys FIRST (shift, space -- legitimately starts ptt),
    THEN ctrl is added, completing the full toggle chord on top of an
    already-running ptt session. This must hand control to toggle (so
    releasing shift/space afterward does NOT stop the recording) rather
    than stopping it outright."""
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space", ptt="shift+space")

    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.ptt_start_count == 1  # legitimately started via ptt

    _down(mgr, CTRL_L)  # completes the toggle chord on top of the ptt session
    assert recorder.toggle_count == 1  # dispatches on_toggle to notify controller of takeover
    assert recorder.ptt_stop_count == 0

    # Session is now toggle-controlled: releasing the ptt keys (and even
    # ctrl) must NOT stop it anymore.
    _up(mgr, SPACE)
    _up(mgr, SHIFT_L)
    _up(mgr, CTRL_L)
    assert recorder.ptt_stop_count == 0

    # Only pressing the full chord again stops it.
    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 2
    assert recorder.ptt_stop_count == 0


def test_ptt_alone_still_works_when_its_keys_are_a_toggle_subset():
    """Same overlapping bindings as above, but this time only the ptt
    keys (not the full toggle chord) are pressed -- ptt must still work
    normally since the toggle's extra key (ctrl) was never pressed."""
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space", ptt="shift+space")

    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.ptt_start_count == 1
    assert recorder.toggle_count == 0

    _up(mgr, SPACE)
    assert recorder.ptt_stop_count == 1


# -- Suppression: the whole point of the rewrite -----------------------


def test_bare_space_is_not_suppressed_when_no_modifiers_held():
    """Space bar used for normal typing (no chord in progress) must pass
    through untouched -- this is what "text keeps getting spaces" was."""
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space")

    suppressed = _down(mgr, SPACE)
    assert suppressed is False


def test_space_is_suppressed_only_once_modifiers_of_toggle_are_held():
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space")

    assert _down(mgr, CTRL_L) is False  # bare ctrl: not part of a completing combo yet... but IS a toggle token
    assert _down(mgr, SHIFT_L) is False
    assert _down(mgr, SPACE) is True  # this press completes the chord -> suppressed
    assert recorder.toggle_count == 1


def test_ptt_key_is_always_suppressed_while_pressed():
    recorder = _Recorder()
    mgr = _manager(recorder, ptt="space")

    assert _down(mgr, SPACE) is True
    assert recorder.ptt_start_count == 1
    assert _up(mgr, SPACE) is True
    assert recorder.ptt_stop_count == 1


def test_unrelated_letter_typing_is_never_suppressed():
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space", ptt="alt_r")

    for ch in "hello world":
        if ch == " ":
            continue
        vk = ord(ch.upper())
        assert _down(mgr, (vk, 0)) is False
        assert _up(mgr, (vk, 0)) is False
    assert recorder.toggle_count == 0
    assert recorder.ptt_start_count == 0


def test_ctrl_press_during_active_toggle_does_not_stop_recording():
    """Pressing Ctrl to do a Ctrl+drag screenshot while toggle recording is
    active must NOT toggle off or interrupt the recording session."""
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space", ptt="alt_r")

    # Start toggle recording via Ctrl+Shift+Space
    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 1

    # Release hotkey chord (user is now speaking)
    _up(mgr, SPACE)
    _up(mgr, SHIFT_L)
    _up(mgr, CTRL_L)
    assert recorder.toggle_count == 1

    # User presses Ctrl for Ctrl+drag screenshot capture
    _down(mgr, CTRL_L)
    assert recorder.toggle_count == 1  # must still be 1 (recording remains ON)
    _up(mgr, CTRL_L)
    assert recorder.toggle_count == 1

    # Pressing full toggle chord again stops recording cleanly
    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 2


def test_bindings_conflict_when_one_is_a_subset_of_the_other():
    assert bindings_conflict("ctrl+shift+space", "shift+space")
    assert bindings_conflict("shift+space", "ctrl+shift+space")
    assert bindings_conflict("alt_r", "alt_r")


def test_bindings_do_not_conflict_when_keys_are_disjoint():
    assert not bindings_conflict("ctrl+shift+space", "alt_r")
    assert not bindings_conflict("ctrl+shift+space", "shift_r")


def test_reset_active_mode():
    recorder = _Recorder()
    mgr = _manager(recorder, toggle="ctrl+shift+space")

    _down(mgr, CTRL_L)
    _down(mgr, SHIFT_L)
    _down(mgr, SPACE)
    assert recorder.toggle_count == 1
    assert mgr._active_mode == "toggle"

    mgr.reset_active_mode()
    assert mgr._active_mode is None
