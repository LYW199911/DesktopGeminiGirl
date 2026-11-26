import threading
from PyQt6.QtCore import QTimer
from perception.window_tracker import get_foreground_window_info


class VoiceInputMixin:
    """Shared Push-to-Talk & Hotkey Voice Input lifecycle for both Classic and Dynamic controllers."""

    def _init_voice_input(self):
        self._voice_stream = None
        self._voice_chunks = []
        self._voice_recording = False
        self._voice_transcribing = False
        self._voice_context = None

        self.voice_toggle_requested.connect(self._toggle_voice_input)
        self.voice_result_ready.connect(self._on_voice_result)

        self.pet.voice_input_start.connect(self._start_voice_input)
        self.pet.voice_input_stop.connect(self._finish_voice_recording)

        self.voice_timeout_timer = QTimer(self)
        self.voice_timeout_timer.setSingleShot(True)
        self.voice_timeout_timer.timeout.connect(self._finish_voice_recording)

    def _show_voice_status(self, message: str):
        self.pet.show()
        self.pet.show_critique(message)

    def _toggle_voice_input(self):
        if self._voice_recording:
            self._finish_voice_recording()
        else:
            self._start_voice_input()

    def _start_voice_input(self):
        if self._voice_recording:
            return
        hk_label = self.config_mgr.get("voice_hotkey", "Ctrl+F1") or "Ctrl+F1"
        if self._voice_transcribing:
            self._show_voice_status("喵呜，正在识别刚才的语音，请稍等一下~")
            return
        if self._is_analyzing:
            self._show_voice_status("我正在回复上一条消息，等一下再语音输入吧~")
            return

        asr_provider = self.config_mgr.get("asr_provider", "tencent").strip()
        if asr_provider == "tencent":
            if not self.config_mgr.get("tencent_secret_id", "").strip() or not self.config_mgr.get("tencent_secret_key", "").strip():
                self._show_voice_status(f"请先在设置中心填写腾讯云 SecretId 和 SecretKey（或切换为 Gemini 原生/本地语音识别），再按 {hk_label} 录音喵~")
                self.show_settings()
                return
        elif asr_provider == "gemini_audio":
            if not self.config_mgr.get("api_key", "").strip():
                self._show_voice_status("使用 Gemini 原生语音识别需要先配置 Gemini API Key 喵~")
                self.show_settings()
                return

        try:
            import sounddevice as sd

            self._voice_context = get_foreground_window_info()
            if self._voice_context.get("is_self", False):
                self._voice_context["scene"] = "general"
                self._voice_context["rect"] = None
            self._voice_chunks = []
            self._voice_recording = True
            self.pet.set_voice_listening(True)

            def collect_audio(indata, frames, time_info, status):
                self._voice_chunks.append(indata.copy().tobytes())

            self._voice_stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="int16",
                callback=collect_audio,
            )
            self._voice_stream.start()
            self.voice_timeout_timer.start(55000)
            self._show_voice_status(f"🎙 正在倾听… 按 {hk_label} 或松开右键即可结束并识别")
            self.logger.info("语音输入开始录音。")
        except Exception as exc:
            self._voice_recording = False
            self.pet.set_voice_listening(False)
            if self._voice_stream is not None:
                try:
                    self._voice_stream.close()
                except Exception:
                    pass
                self._voice_stream = None
            self._show_voice_status(f"无法启动麦克风录音：{exc}")
            self.logger.error(f"无法启动麦克风录音: {exc}")

    def _finish_voice_recording(self):
        if not self._voice_recording:
            return
        self.voice_timeout_timer.stop()
        self._voice_recording = False
        self.pet.set_voice_listening(False)

        stream = self._voice_stream
        self._voice_stream = None
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception as exc:
            self.logger.error(f"停止麦克风录音时出错: {exc}")

        pcm_data = b"".join(self._voice_chunks)
        self._voice_chunks = []
        if not pcm_data:
            self._show_voice_status("没有录到语音，请检查麦克风后重试喵~")
            return

        self._voice_transcribing = True
        asr_provider = self.config_mgr.get("asr_provider", "tencent").strip()
        if asr_provider == "gemini_audio":
            self._show_voice_status("录音结束，正在使用 Gemini 原生听写…")
        elif asr_provider == "local_asr":
            self._show_voice_status("录音结束，正在使用本地离线模型识别…")
        else:
            self._show_voice_status("录音结束，正在连接腾讯云识别…")

        secret_id = self.config_mgr.get("tencent_secret_id", "").strip()
        secret_key = self.config_mgr.get("tencent_secret_key", "").strip()
        api_key = self.config_mgr.get("api_key", "").strip()
        model = self.config_mgr.get("model", "gemini-3.8-flash").strip()

        def recognize():
            try:
                if asr_provider == "gemini_audio":
                    from perception.local_asr import transcribe_pcm_gemini_audio
                    text = transcribe_pcm_gemini_audio(pcm_data, api_key=api_key, model=model)
                elif asr_provider == "local_asr":
                    from perception.local_asr import transcribe_pcm_local
                    text = transcribe_pcm_local(pcm_data)
                else:
                    from perception.tencent_asr import transcribe_pcm
                    text = transcribe_pcm(pcm_data, secret_id, secret_key)
                if not text:
                    self.voice_result_ready.emit(False, "没有听清你说了什么，再试一次吧~")
                else:
                    self.voice_result_ready.emit(True, text)
            except Exception as exc:
                self.voice_result_ready.emit(False, str(exc))

        threading.Thread(target=recognize, daemon=True).start()

    def _on_voice_result(self, success: bool, text: str):
        self._voice_transcribing = False
        if not success:
            self._voice_context = None
            self._show_voice_status(f"语音识别失败：{text}")
            self.logger.error(f"语音识别失败: {text}")
            return

        self.logger.info(f"语音识别结果: {text}")
        self._show_voice_status(f"听到啦：{text}")
        context = self._voice_context
        self._voice_context = None
        self.handle_user_reply(text, context)

    def _cleanup_voice_input(self):
        if getattr(self, "voice_timeout_timer", None):
            self.voice_timeout_timer.stop()
        if getattr(self, "_voice_stream", None) is not None:
            try:
                self._voice_stream.stop()
                self._voice_stream.close()
            except Exception:
                pass
            self._voice_stream = None
        self._voice_recording = False
        try:
            self.pet.set_voice_listening(False)
        except Exception:
            pass
