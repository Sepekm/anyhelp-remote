"""Host-side input injection driven by control events from the controller.

Events arrive as small JSON dicts over the WebRTC data channel:
    {"t": "m",  "x": 0.5, "y": 0.3}     mouse move (normalized to screen)
    {"t": "md", "b": "left"}            mouse button down
    {"t": "mu", "b": "left"}            mouse button up
    {"t": "scroll", "dy": 1}            wheel
    {"t": "kd", "char": "a"}            key down (printable base char)
    {"t": "kd", "key": "enter"}         key down (named special key)
    {"t": "ku", ...}                    key up
    {"t": "releaseall"}                 release everything (e.g. focus lost)

Shift/Ctrl/Alt are sent as their own key events, so the host OS applies them
naturally (capitals, "!", Ctrl+C, etc.).
"""
import logging

from pynput.keyboard import Controller as Keyboard
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as Mouse

log = logging.getLogger("anyhelp.inject")

_BUTTONS = {"left": Button.left, "right": Button.right, "middle": Button.middle}

_SPECIAL = {
    "enter": Key.enter,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "tab": Key.tab,
    "space": Key.space,
    "delete": Key.delete,
    "insert": Key.insert,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "home": Key.home,
    "end": Key.end,
    "pageup": Key.page_up,
    "pagedown": Key.page_down,
    "shift": Key.shift,
    "shift_r": Key.shift_r,
    "ctrl": Key.ctrl,
    "ctrl_r": Key.ctrl_r,
    "alt": Key.alt,
    "alt_gr": Key.alt_gr,
    "cmd": Key.cmd,
    "cmd_r": Key.cmd_r,
    "caps_lock": Key.caps_lock,
    "menu": Key.menu,
    "print_screen": Key.print_screen,
    "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
    "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
    "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
}


class Injector:
    def __init__(self, monitor: dict):
        self._mon = monitor
        self._mouse = Mouse()
        self._kb = Keyboard()
        self.enabled = False
        self._pressed_keys = set()
        self._pressed_buttons = set()

    def handle(self, ev: dict) -> None:
        if not self.enabled:
            return
        t = ev.get("t")
        try:
            if t == "m":
                x = self._mon["left"] + float(ev["x"]) * self._mon["width"]
                y = self._mon["top"] + float(ev["y"]) * self._mon["height"]
                self._mouse.position = (int(x), int(y))
            elif t == "md":
                btn = _BUTTONS.get(ev.get("b"), Button.left)
                self._mouse.press(btn)
                self._pressed_buttons.add(btn)
            elif t == "mu":
                btn = _BUTTONS.get(ev.get("b"), Button.left)
                self._mouse.release(btn)
                self._pressed_buttons.discard(btn)
            elif t == "scroll":
                self._mouse.scroll(0, int(ev.get("dy", 0)))
            elif t == "kd":
                key = self._resolve(ev)
                if key is not None:
                    self._kb.press(key)
                    self._pressed_keys.add(key)
            elif t == "ku":
                key = self._resolve(ev)
                if key is not None:
                    self._kb.release(key)
                    self._pressed_keys.discard(key)
            elif t == "releaseall":
                self.release_all()
        except Exception as exc:
            log.debug("inject failed for %s: %s", ev, exc)

    @staticmethod
    def _resolve(ev: dict):
        if "key" in ev:
            return _SPECIAL.get(ev["key"])
        char = ev.get("char")
        if isinstance(char, str) and len(char) == 1:
            return char
        return None

    def release_all(self) -> None:
        for key in list(self._pressed_keys):
            try:
                self._kb.release(key)
            except Exception:
                pass
        for btn in list(self._pressed_buttons):
            try:
                self._mouse.release(btn)
            except Exception:
                pass
        self._pressed_keys.clear()
        self._pressed_buttons.clear()

    def shutdown(self) -> None:
        self.enabled = False
        self.release_all()
