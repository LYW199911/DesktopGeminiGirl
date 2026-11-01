import os
import re
import json
import base64
import requests
from typing import Optional, Tuple
from config_manager import ConfigManager
from log_manager import get_log_manager
from .prompts import get_system_prompt, build_scene_prompt, build_interactive_prompt
from .context_memory import ContextMemoryManager

def is_valid_gemini_key(key: str) -> bool:
    """校验 Google Gemini API Key 是否符合规范 (同时兼容传统 AIzaSy 与新版 AQ 开头)"""
    if not key:
        return False
    return bool(re.match(r"^(AIzaSy|AQ)[A-Za-z0-9_-]{20,}$", key.strip()))

class GeminiCritiqueEngine:
    def __init__(self):
        self.config_mgr = ConfigManager()
        self.context_memory = ContextMemoryManager()
        self.logger = get_log_manager()

    @property
    def provider(self) -> str:
        # 1. 优先以显式配置的 api_provider 为准
        prov = self.config_mgr.get("api_provider", "").strip().lower()
        if prov in ("gemini", "google"):
            return "gemini"
        if prov in ("openai_compatible", "openai", "openrouter"):
            return "openai_compatible"

        # 2. 兜底识别：若未显式指定，根据 Key 前缀自动判断 (AQ / AIzaSy 均归入 gemini)
        key = self.api_key
        if key.startswith("AIzaSy") or key.startswith("AQ"):
            return "gemini"
        if key.startswith("sk-"):
            return "openai_compatible"
        return "gemini"

    @property
    def api_key(self) -> str:
        return self.config_mgr.get("api_key", "").strip()

    @property
    def model(self) -> str:
        return self.config_mgr.get("model", "gemini-3.8-flash").strip()

    @property
    def custom_url(self) -> str:
        return self.config_mgr.get("custom_api_url", "https://openrouter.ai/api/v1").strip()

    def test_connection(
        self,
        key: Optional[str] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        custom_url: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Test API Key validity for either Gemini or OpenAI/OpenRouter provider."""
        test_key = key.strip() if key is not None else self.api_key
        test_model = model.strip() if model else self.model
        test_prov = provider.strip().lower() if provider else self.provider
        test_url = custom_url.strip() if custom_url else self.custom_url

        if not test_key:
            return False, "API Key 不能为空！"

        # 若未指定有效 provider，根据 Key 前缀自动路由 (明确归入 Google Gemini 或 OpenAI 兼容)
        if test_prov not in ("gemini", "openai_compatible"):
            if test_key.startswith("AIzaSy") or test_key.startswith("AQ"):
                test_prov = "gemini"
            elif test_key.startswith("sk-"):
                test_prov = "openai_compatible"
            else:
                test_prov = "gemini"

        if test_prov == "openai_compatible":
            base = test_url.rstrip("/")
            endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {test_key}",
                "HTTP-Referer": "https://github.com/LYW199911/DesktopGeminiGirl",
                "X-Title": "HaGemi Desktop Pet"
            }
            payload = {
                "model": test_model,
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 5
            }
            try:
                r = requests.post(endpoint, json=payload, headers=headers, timeout=10)
                if r.status_code == 200:
                    return True, f"连接成功！{test_model} 算力响应正常。"
                else:
                    return False, f"API 返回错误 ({r.status_code}): {r.text[:120]}"
            except Exception as e:
                return False, f"网络连接超时或错误: {e}"
        else:
            # Google Gemini native (双通道传递：URL 参数 ?key= 与 HTTP 请求头 x-goog-api-key)
            base = "https://generativelanguage.googleapis.com"
            url = f"{base}/v1beta/models/{test_model}:generateContent?key={test_key}"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": test_key
            }
            payload = {
                "contents": [{"parts": [{"text": "ping"}]}],
                "generationConfig": {"maxOutputTokens": 10, "thinkingConfig": {"thinkingBudget": 0}}
            }
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=10)
                if r.status_code == 200:
                    return True, f"连接成功！Google Gemini ({test_model}) 算力响应正常。"
                else:
                    return False, f"Gemini API 返回错误 ({r.status_code}): {r.text[:120]}"
            except Exception as e:
                return False, f"网络连接超时或错误: {e}"

    def generate_critique(
        self,
        scene: str,
        window_title: str,
        process_name: str,
        image_b64: Optional[str] = None
    ) -> str:
        pet_name = self.config_mgr.get("pet_name", "哈Gemi")
        if not self.api_key:
            return f"[curious] 喵？主人还没有在控制台配置 API Key 喵！快去填上密钥~"

        catchphrases = self.config_mgr.get("catchphrases", ["喵~", "喵？！", "哼~", "盯——"])
        custom_prompt = self.config_mgr.get("custom_system_prompt", "")
        persona_style = self.config_mgr.get("persona_style", "元气毒舌 (默认)")

        # Retrieve rolling context memory (minimal tokens: ~20-35 tokens)
        history_context = self.context_memory.get_recent_context(scene, window_title, max_items=2)
        if history_context:
            self.logger.memory(f"提取到 {len(history_context)} 条前情记忆承接上下文: \"{history_context[-1][:20]}...\"")

        sys_prompt = get_system_prompt(pet_name, catchphrases, custom_prompt, persona_style=persona_style)
        user_prompt = build_scene_prompt(
            scene, window_title, process_name,
            pet_name=pet_name,
            persona_style=persona_style,
            history_context=history_context
        )

        if self.provider == "openai_compatible":
            text = self._call_openai_compatible(sys_prompt, user_prompt, image_b64, pet_name)
        else:
            text = self._call_gemini_native(sys_prompt, user_prompt, image_b64, pet_name)

        # Record into memory so subsequent critiques on this video/window will follow up and not repeat
        if text and not text.startswith("[relieved] 喵呜！"):
            self.context_memory.record_critique(scene, window_title, text, pet_name=pet_name)

        return text

    def generate_interactive_reply(
        self,
        scene: str,
        window_title: str,
        process_name: str,
        user_comment: str,
        image_b64: Optional[str] = None
    ) -> str:
        pet_name = self.config_mgr.get("pet_name", "哈Gemi")
        if not self.api_key:
            return f"[curious] 喵？主人还没有在控制台配置 API Key 喵！快去填上密钥~"

        catchphrases = self.config_mgr.get("catchphrases", ["喵~", "喵？！", "哼~", "盯——"])
        custom_prompt = self.config_mgr.get("custom_system_prompt", "")
        persona_style = self.config_mgr.get("persona_style", "元气毒舌 (默认)")

        # Record user's comment into memory FIRST
        self.context_memory.record_user_comment(scene, window_title, user_comment)

        # Retrieve rolling context memory including user's comment
        history_context = self.context_memory.get_recent_context(scene, window_title, max_items=3)
        self.logger.memory(f"主人在气泡吐槽: \"{user_comment}\" (上下文记忆 {len(history_context)} 条)")

        sys_prompt = get_system_prompt(pet_name, catchphrases, custom_prompt, persona_style=persona_style)
        user_prompt = build_interactive_prompt(
            scene, window_title, process_name,
            user_comment=user_comment,
            pet_name=pet_name,
            persona_style=persona_style,
            history_context=history_context
        )

        if self.provider == "openai_compatible":
            text = self._call_openai_compatible(sys_prompt, user_prompt, image_b64, pet_name)
        else:
            text = self._call_gemini_native(sys_prompt, user_prompt, image_b64, pet_name)

        if text and not text.startswith("[relieved] 喵呜！"):
            self.context_memory.record_critique(scene, window_title, text, pet_name=pet_name)

        return text

    def _call_gemini_native(self, sys_prompt: str, user_prompt: str, image_b64: Optional[str], pet_name: str) -> str:
        base_url = "https://generativelanguage.googleapis.com"
        url = f"{base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        parts = []
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })
        parts.append({"text": user_prompt})

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": parts
                }
            ],
            "system_instruction": {
                "parts": [
                    {"text": sys_prompt}
                ]
            },
            "generationConfig": {
                "temperature": float(self.config_mgr.get("temperature", 0.88)),
                "maxOutputTokens": 300,
                "thinkingConfig": {
                    "thinkingBudget": 64
                }
            }
        }
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=12)
            if resp.status_code == 200:
                result = resp.json()
                candidates = result.get("candidates", [])
                if candidates:
                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if content_parts:
                        text = content_parts[0].get("text", "").strip()
                        text = text.replace('"', '').replace('“', '').replace('”', '').strip()
                        return text
                return f"[curious] 盯——主人当前的操作让本{pet_name}都陷入思考了喵..."
            else:
                print(f"[GeminiEngine] API Error {resp.status_code}: {resp.text}", flush=True)
                return "[relieved] 喵呜！网络信号刚才抖了一下，算力连接稍有延迟喵~"
        except Exception as e:
            print(f"[GeminiEngine] Request failed: {e}", flush=True)
            return f"[relieved] 喵呜~刚才星轨通讯受到干扰，本{pet_name}正在重新调谐天线！"

    def _call_openai_compatible(self, sys_prompt: str, user_prompt: str, image_b64: Optional[str], pet_name: str) -> str:
        base = self.custom_url.rstrip("/")
        endpoint = base if base.endswith("/chat/completions") else f"{base}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://github.com/LYW199911/DesktopGeminiGirl",
            "X-Title": "HaGemi Desktop Pet"
        }

        user_content = []
        if image_b64:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }
            })
        user_content.append({
            "type": "text",
            "text": user_prompt
        })

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": float(self.config_mgr.get("temperature", 0.88)),
            "max_tokens": 300
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                result = resp.json()
                choices = result.get("choices", [])
                if choices:
                    text = choices[0].get("message", {}).get("content", "").strip()
                    text = text.replace('"', '').replace('“', '').replace('”', '').strip()
                    return text
                return f"[curious] 盯——主人当前的操作让本{pet_name}都陷入思考了喵..."
            else:
                print(f"[OpenAIEngine] API Error {resp.status_code}: {resp.text}", flush=True)
                return f"[relieved] 喵呜！API 服务端返回了错误 ({resp.status_code})，快检查下模型和密钥喵~"
        except Exception as e:
            print(f"[OpenAIEngine] Request failed: {e}", flush=True)
            return f"[relieved] 喵呜~自定义 API 连接超时了，请检查网络或 URL 喵！"
