import os
import json
import datetime
import threading
import requests
from typing import Dict, Tuple
from app_paths import TOKEN_USAGE_DIR

USAGE_DIR = TOKEN_USAGE_DIR

# Built-in reference pricing (USD per 1M tokens)
REFERENCE_PRICING_USD: Dict[str, Tuple[float, float]] = {
    "gemini-3.8-flash": (0.15, 0.60),
    "gemini-3.7-flash": (0.15, 0.60),
    "gemini-3-flash": (0.15, 0.60),
    "gemini-flash-latest": (0.15, 0.60),
    "gemini-4-hydrogen": (1.25, 5.00),
    "gemini-4-argon": (1.25, 5.00),
    "gemini-4-carbon": (1.25, 5.00),
    "gemini-4-neon": (0.30, 1.20),
    "claude-sonnet": (3.00, 15.00),
    "claude-opus": (15.00, 75.00),
    "gpt-oss-120b": (0.40, 1.60),
}


_ONLINE_PRICE_CACHE: Dict[str, Tuple[float, float, str]] = {}


def get_reference_unit_price(model: str, provider: str = "gemini") -> Tuple[float, float]:
    """Returns (input_usd_per_1m, output_usd_per_1m) based on model and provider."""
    if provider == "antigravity":
        return (0.0, 0.0)
    m = (model or "").lower().strip()
    if m in _ONLINE_PRICE_CACHE:
        pin, pout, _ = _ONLINE_PRICE_CACHE[m]
        return (pin, pout)
    for key, pair in REFERENCE_PRICING_USD.items():
        if key in m:
            return pair
    if "pro" in m or "argon" in m or "hydrogen" in m or "opus" in m:
        return (1.25, 5.00)
    return (0.15, 0.60)


def fetch_online_unit_price(model: str) -> Tuple[float, float, str]:
    """
    Fetches live public per-1M-token pricing from OpenRouter's public models API.
    Returns (input_usd_per_1m, output_usd_per_1m, matched_model_id).
    """
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    target = (model or "").lower().split("/")[-1]
    best = None
    for item in r.json().get("data", []):
        mid = item.get("id", "")
        mid_low = mid.lower()
        if target and (mid_low == target or mid_low.endswith("/" + target) or target in mid_low):
            pricing = item.get("pricing", {})
            pin = float(pricing.get("prompt", 0) or 0) * 1_000_000
            pout = float(pricing.get("completion", 0) or 0) * 1_000_000
            best = (round(pin, 4), round(pout, 4), mid)
            if mid_low.endswith("/" + target) or mid_low == target:
                break
    if best:
        _ONLINE_PRICE_CACHE[(model or "").lower().strip()] = best
        return best
    in_p, out_p = get_reference_unit_price(model)
    res = (in_p, out_p, f"{model} (内置官方参考价)")
    _ONLINE_PRICE_CACHE[(model or "").lower().strip()] = res
    return res


class TokenTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._file_lock = threading.Lock()
        os.makedirs(USAGE_DIR, exist_ok=True)

    @staticmethod
    def _empty_stats() -> Dict:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "requests": 0,
            "estimated_cost_usd": 0.0,
        }

    @staticmethod
    def _day_file(dt: datetime.date) -> str:
        return os.path.join(USAGE_DIR, str(dt.year), f"{dt.month}月", f"{dt.day}.json")

    @staticmethod
    def _read_json(path: str) -> Dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @classmethod
    def _accumulate_into(cls, acc: Dict, item: Dict):
        acc["prompt_tokens"] += int(item.get("prompt_tokens", 0) or 0)
        acc["completion_tokens"] += int(item.get("completion_tokens", 0) or 0)
        acc["total_tokens"] += int(item.get("total_tokens", 0) or 0)
        acc["requests"] += int(item.get("requests", 0) or 0)
        acc["estimated_cost_usd"] += float(item.get("estimated_cost_usd", 0.0) or 0.0)

    def get_usage_dir(self) -> str:
        os.makedirs(USAGE_DIR, exist_ok=True)
        return USAGE_DIR

    def record(self, prompt_tokens: int, completion_tokens: int, model: str, provider: str, cfg: dict):
        p_tok = max(0, int(prompt_tokens))
        c_tok = max(0, int(completion_tokens))
        if cfg.get("token_price_mode", "auto") == "custom":
            in_price = float(cfg.get("token_custom_input_price", 0.15))
            out_price = float(cfg.get("token_custom_output_price", 0.60))
        else:
            in_price, out_price = get_reference_unit_price(model, provider)

        cost = (p_tok / 1_000_000.0) * in_price + (c_tok / 1_000_000.0) * out_price
        today = datetime.date.today()
        path = self._day_file(today)
        with self._file_lock:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            day_data = self._empty_stats()
            day_data.update({k: v for k, v in self._read_json(path).items() if k in day_data})
            day_data["prompt_tokens"] += p_tok
            day_data["completion_tokens"] += c_tok
            day_data["total_tokens"] += (p_tok + c_tok)
            day_data["requests"] += 1
            day_data["estimated_cost_usd"] += cost
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(day_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    def get_summary(self, scope: str = "day") -> Dict:
        today = datetime.date.today()
        acc = self._empty_stats()
        with self._file_lock:
            if scope == "day":
                self._accumulate_into(acc, self._read_json(self._day_file(today)))
            elif scope == "month":
                month_dir = os.path.join(USAGE_DIR, str(today.year), f"{today.month}月")
                if os.path.isdir(month_dir):
                    for fn in os.listdir(month_dir):
                        if fn.endswith(".json"):
                            self._accumulate_into(acc, self._read_json(os.path.join(month_dir, fn)))
            else:
                if os.path.isdir(USAGE_DIR):
                    for root, _, files in os.walk(USAGE_DIR):
                        for fn in files:
                            if fn.endswith(".json"):
                                self._accumulate_into(acc, self._read_json(os.path.join(root, fn)))
        return acc
