import io
import os
import wave
import base64
import tempfile
import requests
from typing import Optional


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw 16-bit PCM bytes into an in-memory WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def transcribe_pcm_gemini_audio(pcm_data: bytes, api_key: str, model: str = "gemini-2.5-flash") -> str:
    """
    Use Gemini native multimodal audio understanding to transcribe speech directly.
    Zero extra local models or third-party ASR keys required.
    """
    if not api_key:
        raise RuntimeError("使用 Gemini 原生语音识别需要先配置 Gemini API Key。")

    # Ensure we use a model that supports native audio on AI Studio
    if model in ("gemini-3.8-flash", "gemini-3.8-flash-high", "gemini-4-argon") or "3.8" in model or "argon" in model:
        model = "gemini-2.5-flash"

    wav_bytes = pcm_to_wav_bytes(pcm_data)
    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "audio/wav",
                        "data": audio_b64
                    }
                },
                {
                    "text": "请准确听写这段音频中的人声内容，只输出识别出的纯文本，不要添加任何标点以外的解释或前缀。如果听不清或没有声音，请输出空字符串。"
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 200
        }
    }

    resp = requests.post(url, json=payload, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini 语音识别请求失败 ({resp.status_code}): {resp.text[:160]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought") and p.get("text")).strip()
        return text
    return ""


def transcribe_pcm_local(pcm_data: bytes) -> str:
    """
    Offline local ASR (inspired by Coopanion):
    Tries faster-whisper (or sherpa-onnx if available) locally with zero cloud dependency.
    """
    wav_bytes = pcm_to_wav_bytes(pcm_data)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tf.write(wav_bytes)
            tmp_path = tf.name

        try:
            from faster_whisper import WhisperModel
            # Use tiny or base model on CPU with int8 for fast local inference
            model = WhisperModel("base", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(tmp_path, beam_size=3, vad_filter=True)
            text = "".join(seg.text for seg in segments).strip()
            return text
        except ImportError:
            pass

        raise RuntimeError(
            "未检测到本地离线语音库 (faster-whisper)。\n"
            "请在虚拟环境中运行: pip install faster-whisper\n"
            "或者在设置中心将语音识别切换为「Gemini 原生听写 (免配置)」。"
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
