import os
import time
import uuid
import glob
import asyncio
import tempfile
import threading
import ctypes
import edge_tts

winmm = ctypes.windll.winmm

class EdgeSpeaker:
    def __init__(self, voice: str = "zh-CN-XiaoyiNeural", rate: str = "+12%", pitch: str = "+15Hz", enabled: bool = True):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.enabled = enabled
        self._temp_dir = os.path.join(tempfile.gettempdir(), "gemini_pet_tts")
        os.makedirs(self._temp_dir, exist_ok=True)
        self._current_alias = "gemini_voice"
        self._lock = threading.Lock()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        return self.enabled

    def speak_async(self, text: str):
        if not self.enabled or not text:
            return
        clean_text = self._clean_text_for_speech(text)
        threading.Thread(target=self._run_tts_and_play, args=(clean_text,), daemon=True).start()

    def _clean_text_for_speech(self, text: str) -> str:
        t = text.replace("*", "").replace("#", "").replace("`", "").replace("~", "")
        return t.strip()

    def _run_tts_and_play(self, text: str):
        with self._lock:
            try:
                # Unique filename every time to prevent Windows file-locking Errno 13
                unique_id = uuid.uuid4().hex[:10]
                mp3_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")

                async def _generate():
                    communicate = edge_tts.Communicate(
                        text=text,
                        voice=self.voice,
                        rate=self.rate,
                        pitch=self.pitch
                    )
                    await communicate.save(mp3_path)

                asyncio.run(_generate())

                if os.path.exists(mp3_path):
                    self._play_mp3(mp3_path)
                    self._cleanup_old_files()
            except Exception as e:
                print(f"[TTS] Error generating or playing speech: {e}", flush=True)

    def _play_mp3(self, filepath: str):
        try:
            # Safely close existing MCI alias
            winmm.mciSendStringW(f"close {self._current_alias}", None, 0, None)
            time.sleep(0.05)
            # Open new audio
            cmd_open = f'open "{filepath}" type mpegvideo alias {self._current_alias}'
            res_open = winmm.mciSendStringW(cmd_open, None, 0, None)
            if res_open == 0:
                winmm.mciSendStringW(f"play {self._current_alias}", None, 0, None)
        except Exception as e:
            print(f"[TTS] MCI Play Error: {e}", flush=True)

    def _cleanup_old_files(self):
        try:
            files = glob.glob(os.path.join(self._temp_dir, "speech_*.mp3"))
            # Keep only the last 3 files
            if len(files) > 3:
                files.sort(key=os.path.getmtime)
                for f in files[:-3]:
                    try:
                        os.remove(f)
                    except Exception:
                        pass
        except Exception:
            pass
