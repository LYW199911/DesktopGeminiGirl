import os
import sys
import time
import uuid
import glob
import asyncio
import tempfile
import threading
import subprocess
from typing import Optional
import edge_tts

try:
    import requests
except ImportError:
    requests = None

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"

if IS_WIN:
    import ctypes
    winmm = ctypes.windll.winmm
else:
    winmm = None

class EdgeSpeaker:
    def __init__(
        self,
        voice: str = "zh-TW-HsiaoChenNeural",
        rate: str = "+10%",
        pitch: str = "+10Hz",
        enabled: bool = True,
        engine_type: str = "edge_tts",
        api_url: str = "",
        api_key: str = "",
        model: str = ""
    ):
        self.voice = voice or "zh-TW-HsiaoChenNeural"
        self.rate = rate or "+10%"
        self.pitch = pitch or "+10Hz"
        self.enabled = enabled
        self.engine_type = engine_type or "edge_tts"
        self.api_url = (api_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()

        self._temp_dir = os.path.join(tempfile.gettempdir(), "gemini_pet_tts")
        os.makedirs(self._temp_dir, exist_ok=True)
        self._current_alias = "gemini_voice"
        self._lock = threading.Lock()
        self._current_process: Optional[subprocess.Popen] = None

    def update_config(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        enabled: Optional[bool] = None,
        engine_type: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        if voice is not None:
            self.voice = voice
        if rate is not None:
            self.rate = rate
        if pitch is not None:
            self.pitch = pitch
        if enabled is not None:
            self.enabled = enabled
        if engine_type is not None:
            self.engine_type = engine_type
        if api_url is not None:
            self.api_url = api_url.strip()
        if api_key is not None:
            self.api_key = api_key.strip()
        if model is not None:
            self.model = model.strip()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        return self.enabled

    def stop(self):
        """Immediately stop any currently playing speech."""
        if IS_WIN and winmm:
            try:
                winmm.mciSendStringW(f"close {self._current_alias}", None, 0, None)
            except Exception:
                pass
        elif self._current_process:
            try:
                if self._current_process.poll() is None:
                    self._current_process.terminate()
            except Exception:
                pass
            self._current_process = None

    def speak_async(self, text: str):
        if not self.enabled or not text:
            return
        clean_text = self._clean_text_for_speech(text)
        threading.Thread(target=self._run_tts_and_play, args=(clean_text,), daemon=True).start()

    def _clean_text_for_speech(self, text: str) -> str:
        # Filter markdown symbols and emotion tags like [confident], [shocked]
        import re
        t = re.sub(r"\[(confident|curious|shocked|relieved)\]", "", text, flags=re.IGNORECASE)
        t = t.replace("*", "").replace("#", "").replace("`", "").replace("~", "")
        return t.strip()

    def _run_tts_and_play(self, text: str):
        with self._lock:
            try:
                # Stop existing playback before starting new one
                self.stop()

                # Unique filename every time to prevent Windows file-locking Errno 13
                unique_id = uuid.uuid4().hex[:10]
                mp3_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")

                # Mode 1: OpenAI-compatible custom TTS endpoint (GPT-SoVITS / CosyVoice / Fish Audio)
                if self.engine_type == "openai_tts" and self.api_url and requests:
                    try:
                        headers = {"Content-Type": "application/json"}
                        if self.api_key:
                            headers["Authorization"] = f"Bearer {self.api_key}"
                        payload = {
                            "model": self.model or "tts-1",
                            "input": text,
                            "voice": self.voice or "default"
                        }
                        endpoint = self.api_url
                        if not endpoint.endswith("/v1/audio/speech") and not endpoint.endswith("/speech") and "/v1" not in endpoint:
                            endpoint = endpoint.rstrip("/") + "/v1/audio/speech"

                        resp = requests.post(endpoint, json=payload, headers=headers, timeout=12)
                        if resp.status_code == 200 and len(resp.content) > 100:
                            with open(mp3_path, "wb") as f:
                                f.write(resp.content)
                        else:
                            print(f"[TTS] Custom TTS API failed ({resp.status_code}): {resp.text[:120]}, falling back to Edge-TTS", flush=True)
                            self._generate_edge_tts(text, mp3_path)
                    except Exception as e:
                        print(f"[TTS] Custom TTS error: {e}, falling back to Edge-TTS", flush=True)
                        self._generate_edge_tts(text, mp3_path)
                else:
                    # Mode 2: Edge-TTS
                    self._generate_edge_tts(text, mp3_path)

                if os.path.exists(mp3_path):
                    self._play_mp3(mp3_path)
                    self._cleanup_old_files()
            except Exception as e:
                print(f"[TTS] Error generating or playing speech: {e}", flush=True)

    def _generate_edge_tts(self, text: str, output_path: str):
        voice = self.voice or "zh-TW-HsiaoChenNeural"
        async def _generate():
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.rate,
                pitch=self.pitch
            )
            await communicate.save(output_path)

        asyncio.run(_generate())

    def _play_mp3(self, filepath: str):
        if IS_WIN and winmm:
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
                print(f"[TTS] Windows MCI Play Error: {e}", flush=True)
        elif IS_MAC:
            try:
                # macOS built-in native audio player
                self._current_process = subprocess.Popen(
                    ["afplay", filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=0x08000000 if IS_WIN else 0
                )
            except Exception as e:
                print(f"[TTS] macOS afplay Error: {e}", flush=True)
        else:
            # Linux fallback (paplay / ffplay / aplay / mpv)
            for player in ["mpv", "ffplay", "paplay", "aplay"]:
                try:
                    args = [player, filepath]
                    if player == "ffplay":
                        args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", filepath]
                    elif player == "mpv":
                        args = [player, "--no-video", filepath]
                    self._current_process = subprocess.Popen(
                        args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=0x08000000 if IS_WIN else 0
                    )
                    break
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"[TTS] Linux {player} Error: {e}", flush=True)

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
