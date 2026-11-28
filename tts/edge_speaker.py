import os
import sys
import time
import uuid
import glob
import base64
import asyncio
import tempfile
import threading
import queue
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
        voice: str = "zh-CN-XiaoyiNeural",
        rate: str = "+10%",
        pitch: str = "+10Hz",
        enabled: bool = True,
        engine_type: str = "edge_tts",
        api_url: str = "",
        api_key: str = "",
        model: str = "",
        gemini_api_key: str = "",
        gemini_voice: str = "Aoede",
        gemini_model: str = "gemini-3.8-flash-tts",
        volume: int = 100
    ):
        self.voice = voice or "zh-CN-XiaoyiNeural"
        self.rate = rate or "+10%"
        self.pitch = pitch or "+10Hz"
        self.volume = max(0, min(100, int(volume)))
        self.enabled = enabled
        self.engine_type = engine_type or "edge_tts"
        self.api_url = (api_url or "").strip()
        self.api_key = (api_key or "").strip()
        self.model = (model or "").strip()
        self.gemini_api_key = (gemini_api_key or "").strip()
        self.gemini_voice = (gemini_voice or "Aoede").strip()
        self.gemini_model = (gemini_model or "gemini-3.8-flash-tts").strip()

        self._temp_dir = os.path.join(tempfile.gettempdir(), "gemini_pet_tts")
        os.makedirs(self._temp_dir, exist_ok=True)
        self._current_alias = "gemini_voice"
        self._lock = threading.Lock()
        self._speech_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._current_process: Optional[subprocess.Popen] = None
        self.on_start = None  # Callback signature: Callable[[int], None] -> duration_ms
        self._worker_thread = threading.Thread(target=self._tts_worker_loop, daemon=True)
        self._worker_thread.start()

    def update_config(
        self,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None,
        enabled: Optional[bool] = None,
        engine_type: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        gemini_api_key: Optional[str] = None,
        gemini_voice: Optional[str] = None,
        gemini_model: Optional[str] = None,
        volume: Optional[int] = None
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
        if gemini_api_key is not None:
            self.gemini_api_key = gemini_api_key.strip()
        if gemini_voice is not None:
            self.gemini_voice = gemini_voice.strip()
        if gemini_model is not None:
            self.gemini_model = gemini_model.strip()
        if volume is not None:
            self.volume = max(0, min(100, int(volume)))

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.clear_queue()
            self.stop()
        return self.enabled

    def clear_queue(self):
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except queue.Empty:
                break

    def stop(self):
        """Immediately stop any currently playing speech."""
        self._stop_event.set()
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
        if not clean_text:
            return
        # Cap backlog at 3 queued sentences so speech never falls far behind
        while self._speech_queue.qsize() >= 3:
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except queue.Empty:
                break
        self._speech_queue.put(clean_text)

    def _tts_worker_loop(self):
        while True:
            text = self._speech_queue.get()
            try:
                if self.enabled and text:
                    self._stop_event.clear()
                    duration_ms = self._run_tts_and_play(text)
                    if duration_ms > 0:
                        self._wait_playback_or_cutoff(duration_ms)
            except Exception as e:
                print(f"[TTS] Worker error: {e}", flush=True)
            finally:
                self._speech_queue.task_done()

    def _wait_playback_or_cutoff(self, duration_ms: int):
        """Waits for current speech to finish; cuts off overly long speech (>12s) if next item is queued."""
        max_wait_s = min(max(duration_ms, 500) / 1000.0 + 0.2, 25.0)
        t0 = time.monotonic()
        while not self._stop_event.is_set() and self.enabled:
            elapsed = time.monotonic() - t0
            if elapsed >= max_wait_s:
                break
            # If next sentence is waiting and current sentence has played > 12s, cut it off cleanly
            if not self._speech_queue.empty() and elapsed >= 12.0:
                self.stop()
                break
            if IS_WIN and winmm and elapsed > 0.35:
                try:
                    buf = ctypes.create_unicode_buffer(64)
                    if winmm.mciSendStringW(f"status {self._current_alias} mode", buf, 64, None) == 0:
                        if buf.value.strip().lower() == "stopped":
                            break
                except Exception:
                    pass
            elif self._current_process is not None and self._current_process.poll() is not None:
                break
            time.sleep(0.08)

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

                # Unique filename every time to prevent file-locking
                unique_id = uuid.uuid4().hex[:10]
                audio_path = None

                # Mode 1: Gemini 3.8 Flash TTS
                if self.engine_type == "gemini_tts":
                    audio_path = self._generate_gemini_tts(text, unique_id)
                    if not audio_path:
                        print("[TTS] Gemini TTS generation failed, falling back to Edge-TTS", flush=True)
                        audio_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")
                        self._generate_edge_tts(text, audio_path)

                # Mode 2: OpenAI-compatible custom TTS endpoint (GPT-SoVITS / CosyVoice / Fish Audio)
                elif self.engine_type == "openai_tts" and self.api_url and requests:
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
                            is_wav = resp.content.startswith(b"RIFF") or "wav" in resp.headers.get("Content-Type", "").lower()
                            ext = ".wav" if is_wav else ".mp3"
                            out_path = os.path.join(self._temp_dir, f"speech_{unique_id}{ext}")
                            with open(out_path, "wb") as f:
                                f.write(resp.content)
                            audio_path = out_path
                        else:
                            print(f"[TTS] Custom TTS API failed ({resp.status_code}): {resp.text[:120]}, falling back to Edge-TTS", flush=True)
                            fallback_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")
                            self._generate_edge_tts(text, fallback_path)
                            audio_path = fallback_path
                    except Exception as e:
                        print(f"[TTS] Custom TTS error: {e}, falling back to Edge-TTS", flush=True)
                        fallback_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")
                        self._generate_edge_tts(text, fallback_path)
                        audio_path = fallback_path
                else:
                    # Mode 3: Edge-TTS
                    audio_path = os.path.join(self._temp_dir, f"speech_{unique_id}.mp3")
                    self._generate_edge_tts(text, audio_path)

                if audio_path and os.path.exists(audio_path):
                    dur = self._play_audio(audio_path, text=text)
                    self._cleanup_old_files()
                    return dur
            except Exception as e:
                print(f"[TTS] Error generating or playing speech: {e}", flush=True)
            return 0

    def _generate_gemini_tts(self, text: str, unique_id: str) -> Optional[str]:
        if not requests:
            print("[TTS] requests library is not installed, cannot use Gemini TTS", flush=True)
            return None

        # Resolve API Key: passed key -> tts_api_key -> config_manager api_key
        key = self.gemini_api_key or self.api_key
        if not key:
            try:
                from config_manager import ConfigManager
                key = ConfigManager().get("api_key", "").strip()
            except Exception:
                pass

        if not key:
            print("[TTS] No Gemini API key found for Gemini TTS", flush=True)
            return None

        model_name = self.gemini_model or "gemini-3.8-flash-tts"
        voice_name = self.gemini_voice or "Aoede"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"

        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice_name
                        }
                    }
                }
            }
        }

        try:
            resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            inline = part["inlineData"]
                            mime = inline.get("mimeType", "audio/wav")
                            b64_data = inline.get("data", "")
                            if b64_data:
                                ext = ".wav" if "wav" in mime else ".mp3"
                                out_path = os.path.join(self._temp_dir, f"speech_{unique_id}{ext}")
                                with open(out_path, "wb") as f:
                                    f.write(base64.b64decode(b64_data))
                                return out_path
            print(f"[TTS] Gemini TTS API returned {resp.status_code}: {resp.text[:120]}", flush=True)
        except Exception as e:
            print(f"[TTS] Gemini TTS request error: {e}", flush=True)
        return None

    def _generate_edge_tts(self, text: str, output_path: str):
        voice = self.voice or "zh-CN-XiaoyiNeural"
        async def _generate():
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice,
                rate=self.rate,
                pitch=self.pitch
            )
            await communicate.save(output_path)

        asyncio.run(_generate())

    def _get_audio_duration_ms(self, filepath: str, text: str = "") -> int:
        """Accurately calculates or queries audio duration in milliseconds across different TTS formats."""
        # 1. Exact measurement for WAV (RIFF) using python standard library wave
        try:
            with open(filepath, "rb") as f:
                sig = f.read(4)
            if sig == b"RIFF":
                import wave
                with wave.open(filepath, "rb") as w:
                    frames = w.getnframes()
                    rate = w.getframerate()
                    if rate > 0:
                        return int(frames * 1000 / rate)
        except Exception:
            pass

        # 2. Query Windows MCI length in milliseconds
        if IS_WIN and winmm:
            try:
                buf = ctypes.create_unicode_buffer(128)
                winmm.mciSendStringW(f"set {self._current_alias} time format milliseconds", None, 0, None)
                winmm.mciSendStringW(f"status {self._current_alias} length", buf, 128, None)
                val = buf.value.strip()
                if val.isdigit() and int(val) > 0:
                    return int(val)
            except Exception:
                pass

        # 3. Fallback estimation based on text length (~3.5 Chinese characters per second)
        return max(3500, int(len(text) * 280))

    def _scale_wav_volume(self, filepath: str):
        """Scales 16-bit PCM WAV amplitude in-place when volume < 100 so all players honor volume."""
        if self.volume >= 100:
            return
        try:
            import wave
            import numpy as np
            with wave.open(filepath, "rb") as wf:
                params = wf.getparams()
                if wf.getsampwidth() != 2:
                    return
                raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            scaled = np.clip(arr * (self.volume / 100.0), -32768, 32767).astype(np.int16)
            with wave.open(filepath, "wb") as wf:
                wf.setparams(params)
                wf.writeframes(scaled.tobytes())
        except Exception:
            pass

    def _play_audio(self, filepath: str, text: str = ""):
        duration_ms = 0
        if self.volume <= 0:
            duration_ms = self._get_audio_duration_ms(filepath, text=text)
            if self.on_start:
                self.on_start(duration_ms)
            return

        # Check magic bytes to detect true audio format
        is_wav = False
        try:
            with open(filepath, "rb") as f:
                if f.read(4) == b"RIFF":
                    is_wav = True
        except Exception:
            pass
        if is_wav and self.volume < 100:
            self._scale_wav_volume(filepath)

        if IS_WIN and winmm:
            try:
                # Safely close existing MCI alias
                winmm.mciSendStringW(f"close {self._current_alias}", None, 0, None)
                time.sleep(0.05)

                file_ext = os.path.splitext(filepath)[1].lower()
                if is_wav or file_ext == ".wav":
                    type_clause = "type waveaudio "
                elif file_ext == ".mp3":
                    type_clause = "type mpegvideo "
                else:
                    type_clause = ""

                cmd_open = f'open "{filepath}" {type_clause}alias {self._current_alias}'
                res_open = winmm.mciSendStringW(cmd_open, None, 0, None)
                if res_open != 0:
                    # Retry without type clause or with waveaudio
                    alt_type = "type waveaudio " if not is_wav else ""
                    cmd_open = f'open "{filepath}" {alt_type}alias {self._current_alias}'
                    res_open = winmm.mciSendStringW(cmd_open, None, 0, None)

                duration_ms = self._get_audio_duration_ms(filepath, text=text)

                if res_open == 0:
                    if not is_wav and self.volume < 100:
                        winmm.mciSendStringW(f"setaudio {self._current_alias} volume to {self.volume * 10}", None, 0, None)
                    winmm.mciSendStringW(f"play {self._current_alias}", None, 0, None)
                elif is_wav or file_ext == ".wav":
                    import winsound
                    winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
                else:
                    print(f"[TTS] Windows MCI open failed with error code: {res_open}", flush=True)
            except Exception as e:
                print(f"[TTS] Windows MCI Play Error: {e}", flush=True)
        elif IS_MAC:
            try:
                duration_ms = self._get_audio_duration_ms(filepath, text=text)
                # macOS built-in native audio player supports both .wav and .mp3 + -v volume
                self._current_process = subprocess.Popen(
                    ["afplay", "-v", f"{self.volume / 100.0:.2f}", filepath],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                print(f"[TTS] macOS afplay Error: {e}", flush=True)
        else:
            # Linux fallback (paplay / ffplay / aplay / mpv)
            duration_ms = self._get_audio_duration_ms(filepath, text=text)
            for player in ["mpv", "ffplay", "paplay", "aplay"]:
                try:
                    args = [player, filepath]
                    if player == "mpv":
                        args = [player, f"--volume={self.volume}", filepath]
                    elif player == "ffplay":
                        args = [player, "-nodisp", "-autoexit", "-loglevel", "quiet", "-volume", str(self.volume), filepath]
                    elif player == "mpv":
                        args = [player, "--no-video", filepath]
                    self._current_process = subprocess.Popen(
                        args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    break
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"[TTS] Linux {player} Error: {e}", flush=True)

        # Notify callback that playback has started with the detected audio duration
        if callable(self.on_start):
            try:
                self.on_start(duration_ms)
            except Exception as e:
                print(f"[TTS] on_start callback error: {e}", flush=True)
        return duration_ms

    def _play_mp3(self, filepath: str):
        self._play_audio(filepath)

    def _cleanup_old_files(self):
        try:
            files = glob.glob(os.path.join(self._temp_dir, "speech_*.*"))
            # Keep only the last 5 audio files
            if len(files) > 5:
                files.sort(key=os.path.getmtime)
                for f in files[:-5]:
                    try:
                        os.remove(f)
                    except Exception:
                        pass
        except Exception:
            pass
