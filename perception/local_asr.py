import io
import os
import wave
import base64
import tempfile
import requests


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Convert raw 16-bit PCM bytes into an in-memory WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def transcribe_pcm_gemini_audio(pcm_data: bytes, api_key: str, model: str = "gemini-3.8-flash") -> str:
    """
    Use Gemini native multimodal audio understanding to transcribe speech directly.
    Zero extra local models or third-party ASR keys required.
    """
    if not api_key:
        raise RuntimeError("使用 Gemini 原生语音识别需要先配置 Gemini API Key。")

    # Ensure we use an active Gemini Flash model that supports native audio on AI Studio
    m_low = (model or "").lower()
    if not m_low or any(k in m_low for k in ("2.5", "argon", "hydrogen", "claude", "gpt")):
        model = "gemini-3.8-flash"

    wav_bytes = pcm_to_wav_bytes(pcm_data)
    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

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

    resp = None
    for candidate_model in (model, "gemini-flash-latest"):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent?key={api_key}"
        resp = requests.post(url, json=payload, headers=headers, timeout=20)
        if resp.status_code != 404:
            break
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini 语音识别请求失败 ({resp.status_code}): {resp.text[:160]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought") and p.get("text")).strip()
        return text
    return ""


_WHISPER_MODEL = None


def transcribe_pcm_local(pcm_data: bytes) -> str:
    """
    Offline local ASR (inspired by Coopanion):
    Passes 16kHz float32 PCM directly to faster-whisper (bypassing PyAV av.open
    and temp WAV files) and caches the loaded model for fast subsequent runs.
    """
    global _WHISPER_MODEL
    try:
        import numpy as np
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        raise RuntimeError(
            "未检测到本地离线语音库 (faster-whisper)。\n"
            "请在虚拟环境中运行: pip install faster-whisper\n"
            "或者在设置中心将语音识别切换为「Gemini 原生听写 (免配置)」。"
        )

    if _WHISPER_MODEL is None:
        _WHISPER_MODEL = WhisperModel("base", device="cpu", compute_type="int8")

    audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
    if audio_np.size == 0:
        return ""

    segments, _ = _WHISPER_MODEL.transcribe(audio_np, beam_size=3, vad_filter=True)
    return "".join(seg.text for seg in segments).strip()

