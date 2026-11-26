import sys
from typing import Callable, Optional
from pynput import keyboard


_SPECIAL_KEYS = {
    "ctrl", "control", "alt", "shift", "cmd", "meta", "win", "super",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "space", "enter", "return", "tab", "esc", "escape", "backspace", "delete",
    "insert", "home", "end", "pageup", "pagedown", "up", "down", "left", "right",
}


def normalize_hotkey_to_pynput(hotkey_str: str, fallback: str = "<ctrl>+<f1>") -> str:
    """Converts human-readable shortcuts like 'Ctrl+F1' or 'Alt+V' to pynput format."""
    raw = (hotkey_str or "").strip()
    if not raw:
        return fallback
    if "<" in raw and ">" in raw:
        return raw.lower()
    parts = [p.strip().lower() for p in raw.split("+") if p.strip()]
    if not parts:
        return fallback
    mapped = []
    for p in parts:
        if p in ("control", "ctrl"):
            mapped.append("<ctrl>")
        elif p in ("meta", "win", "super"):
            mapped.append("<cmd>")
        elif p in _SPECIAL_KEYS:
            mapped.append(f"<{p}>")
        else:
            mapped.append(p)
    return "+".join(mapped)


class GlobalHotkeyManager:
    def __init__(
        self,
        on_trigger_critique: Callable[[], None],
        on_toggle_mute: Optional[Callable[[], None]] = None,
        on_switch_outfit: Optional[Callable[[], None]] = None,
        on_toggle_voice_input: Optional[Callable[[], None]] = None,
        voice_hotkey: str = "Ctrl+F1",
    ):
        self.on_trigger_critique = on_trigger_critique
        self.on_toggle_mute = on_toggle_mute
        self.on_switch_outfit = on_switch_outfit
        self.on_toggle_voice_input = on_toggle_voice_input
        self.voice_hotkey = voice_hotkey or "Ctrl+F1"
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self):
        self.stop()
        hotkeys = {
            '<ctrl>+<f9>': self._handle_critique
        }
        if sys.platform == 'darwin':
            hotkeys['<cmd>+<f9>'] = self._handle_critique

        if self.on_toggle_mute:
            hotkeys['<ctrl>+<f10>'] = self._handle_mute
            if sys.platform == 'darwin':
                hotkeys['<cmd>+<f10>'] = self._handle_mute

        if self.on_switch_outfit:
            hotkeys['<ctrl>+<f11>'] = self._handle_switch_outfit
            if sys.platform == 'darwin':
                hotkeys['<cmd>+<f11>'] = self._handle_switch_outfit

        voice_hk = normalize_hotkey_to_pynput(self.voice_hotkey)
        if self.on_toggle_voice_input:
            hotkeys[voice_hk] = self._handle_voice_input
            if sys.platform == 'darwin' and '<ctrl>' in voice_hk:
                hotkeys[voice_hk.replace('<ctrl>', '<cmd>')] = self._handle_voice_input

        try:
            self._listener = keyboard.GlobalHotKeys(hotkeys)
            self._listener.daemon = True
            self._listener.start()
            print(f"[Hotkey] Registered {voice_hk} (Voice Input), <ctrl>+<f9> (Critique), <ctrl>+<f10> (Mute), <ctrl>+<f11> (Switch Outfit)")
        except Exception as e:
            print(f"[Hotkey] Warning: Could not start global hotkey listener: {e}")
            if sys.platform == 'darwin':
                print("[Hotkey] Note: On macOS, global hotkeys require Accessibility permissions in System Settings -> Privacy & Security -> Accessibility.")

    def update_voice_hotkey(self, new_hotkey: str):
        new_val = (new_hotkey or "Ctrl+F1").strip()
        if normalize_hotkey_to_pynput(new_val) != normalize_hotkey_to_pynput(self.voice_hotkey):
            self.voice_hotkey = new_val
            self.start()
        else:
            self.voice_hotkey = new_val

    def stop(self):
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _handle_critique(self):
        print("[Hotkey] Critique hotkey pressed -> Instant Critique triggered!")
        if self.on_trigger_critique:
            self.on_trigger_critique()

    def _handle_mute(self):
        print("[Hotkey] Mute hotkey pressed -> Toggle Mute triggered!")
        if self.on_toggle_mute:
            self.on_toggle_mute()

    def _handle_switch_outfit(self):
        print("[Hotkey] Switch outfit hotkey pressed -> Switch Outfit triggered!")
        if self.on_switch_outfit:
            self.on_switch_outfit()

    def _handle_voice_input(self):
        print("[Hotkey] Voice input hotkey pressed -> Toggle Voice Input")
        if self.on_toggle_voice_input:
            self.on_toggle_voice_input()
