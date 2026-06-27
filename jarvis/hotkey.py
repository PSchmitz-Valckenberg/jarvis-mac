"""Global hotkey listener.

A *tap* on the configured key (default macOS Option/alt) is treated as
typed-input mode; holding it down drives hold-to-talk voice capture. The
press/release split lets the same listener serve both without rewiring.

NOTE: macOS requires Accessibility permission for global key capture.
Grant it under System Settings -> Privacy & Security -> Accessibility for
your terminal / Python launcher, then restart the app.
"""

from __future__ import annotations

from typing import Callable

from pynput import keyboard

# Map a friendly config name to the set of pynput keys that should match it.
# Modifiers have left/right variants we treat as equivalent.
_KEY_ALIASES: dict[str, set] = {
    "alt": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r},
    "option": {keyboard.Key.alt, keyboard.Key.alt_l, keyboard.Key.alt_r},
    "cmd": {keyboard.Key.cmd, keyboard.Key.cmd_l, keyboard.Key.cmd_r},
    "ctrl": {keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r},
    "shift": {keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r},
}


def _resolve_keys(name: str) -> set:
    name = name.lower()
    if name in _KEY_ALIASES:
        return _KEY_ALIASES[name]
    # Function keys like "f9" -> keyboard.Key.f9
    if hasattr(keyboard.Key, name):
        return {getattr(keyboard.Key, name)}
    # Fall back to Option so the app still works with a bad config value.
    return _KEY_ALIASES["alt"]


class HotkeyListener:
    """Watches for the trigger key in a background thread.

    Callbacks are invoked from pynput's listener thread — if they touch the
    GUI, marshal back to the main thread (the app does this via Qt signals).
    """

    def __init__(
        self,
        hotkey: str,
        on_press: Callable[[], None],
        on_release: Callable[[], None] | None = None,
    ) -> None:
        self._keys = _resolve_keys(hotkey)
        self._on_press = on_press
        self._on_release = on_release
        self._held = False  # guards against key-repeat spamming on_press
        self._listener: keyboard.Listener | None = None

    def _handle_press(self, key) -> None:
        if key in self._keys and not self._held:
            self._held = True
            self._on_press()

    def _handle_release(self, key) -> None:
        if key in self._keys and self._held:
            self._held = False
            if self._on_release:
                self._on_release()

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
