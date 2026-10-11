"""Controller-side: translate pygame key events into wire events.

We send the *base* key (ignoring Shift) plus modifiers as their own events,
so the host OS composes the final character itself.
"""
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

_SPECIAL = {
    pygame.K_RETURN: "enter",
    pygame.K_KP_ENTER: "enter",
    pygame.K_ESCAPE: "esc",
    pygame.K_BACKSPACE: "backspace",
    pygame.K_TAB: "tab",
    pygame.K_SPACE: "space",
    pygame.K_DELETE: "delete",
    pygame.K_INSERT: "insert",
    pygame.K_UP: "up",
    pygame.K_DOWN: "down",
    pygame.K_LEFT: "left",
    pygame.K_RIGHT: "right",
    pygame.K_HOME: "home",
    pygame.K_END: "end",
    pygame.K_PAGEUP: "pageup",
    pygame.K_PAGEDOWN: "pagedown",
    pygame.K_LSHIFT: "shift",
    pygame.K_RSHIFT: "shift_r",
    pygame.K_LCTRL: "ctrl",
    pygame.K_RCTRL: "ctrl_r",
    pygame.K_LALT: "alt",
    pygame.K_RALT: "alt_gr",
    pygame.K_LMETA: "cmd",
    pygame.K_RMETA: "cmd_r",
    pygame.K_LSUPER: "cmd",
    pygame.K_RSUPER: "cmd_r",
    pygame.K_CAPSLOCK: "caps_lock",
    pygame.K_MENU: "menu",
    pygame.K_PRINTSCREEN: "print_screen",
    pygame.K_F1: "f1", pygame.K_F2: "f2", pygame.K_F3: "f3", pygame.K_F4: "f4",
    pygame.K_F5: "f5", pygame.K_F6: "f6", pygame.K_F7: "f7", pygame.K_F8: "f8",
    pygame.K_F9: "f9", pygame.K_F10: "f10", pygame.K_F11: "f11", pygame.K_F12: "f12",
}

# Numeric keypad digits/operators -> their base characters.
_KEYPAD = {
    pygame.K_KP0: "0", pygame.K_KP1: "1", pygame.K_KP2: "2", pygame.K_KP3: "3",
    pygame.K_KP4: "4", pygame.K_KP5: "5", pygame.K_KP6: "6", pygame.K_KP7: "7",
    pygame.K_KP8: "8", pygame.K_KP9: "9",
    pygame.K_KP_PERIOD: ".", pygame.K_KP_PLUS: "+", pygame.K_KP_MINUS: "-",
    pygame.K_KP_MULTIPLY: "*", pygame.K_KP_DIVIDE: "/",
}


def encode_key(event) -> dict | None:
    """Return {"key": name} / {"char": ch} for a pygame KEYDOWN/KEYUP, or None."""
    k = event.key
    if k in _SPECIAL:
        return {"key": _SPECIAL[k]}
    if k in _KEYPAD:
        return {"char": _KEYPAD[k]}
    # pygame key constants for printable ASCII equal that char's lowercase code.
    if 32 <= k <= 126:
        return {"char": chr(k)}
    return None
