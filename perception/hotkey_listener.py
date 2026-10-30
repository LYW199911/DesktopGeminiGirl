import threading
from typing import Callable, Optional
from pynput import keyboard

class GlobalHotkeyManager:
    def __init__(
        self,
        on_trigger_critique: Callable[[], None],
        on_toggle_mute: Optional[Callable[[], None]] = None,
        on_switch_outfit: Optional[Callable[[], None]] = None
    ):
        self.on_trigger_critique = on_trigger_critique
        self.on_toggle_mute = on_toggle_mute
        self.on_switch_outfit = on_switch_outfit
        self._listener: Optional[keyboard.GlobalHotKeys] = None

    def start(self):
        hotkeys = {
            '<ctrl>+<f9>': self._handle_critique
        }
        if self.on_toggle_mute:
            hotkeys['<ctrl>+<f10>'] = self._handle_mute
        if self.on_switch_outfit:
            hotkeys['<ctrl>+<f11>'] = self._handle_switch_outfit

        self._listener = keyboard.GlobalHotKeys(hotkeys)
        self._listener.daemon = True
        self._listener.start()
        print("[Hotkey] Registered <ctrl>+<f9> (Critique), <ctrl>+<f10> (Mute), <ctrl>+<f11> (Switch Outfit)")

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _handle_critique(self):
        print("[Hotkey] <ctrl>+<f9> pressed -> Instant Critique triggered!")
        if self.on_trigger_critique:
            self.on_trigger_critique()

    def _handle_mute(self):
        print("[Hotkey] <ctrl>+<f10> pressed -> Toggle Mute triggered!")
        if self.on_toggle_mute:
            self.on_toggle_mute()

    def _handle_switch_outfit(self):
        print("[Hotkey] <ctrl>+<f11> pressed -> Switch Outfit triggered!")
        if self.on_switch_outfit:
            self.on_switch_outfit()
