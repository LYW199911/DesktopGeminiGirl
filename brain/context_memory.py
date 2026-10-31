import time
import re
from typing import List, Dict, Optional

class ContextMemoryManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        # Rolling list of recent critiques and user comments:
        # [{"scene": str, "title": str, "text": str, "time": float}]
        self.history: List[Dict[str, any]] = []
        self.max_total = 25

    def record_critique(self, scene: str, window_title: str, text: str, pet_name: str = "哈Gemi"):
        if not text or not text.strip():
            return
        # Strip emotion tag like [shocked] so the memory context is purely clean dialogue
        clean_text = re.sub(r'^\s*\[[a-zA-Z]+\]\s*', '', text).strip()
        self.history.append({
            "scene": scene,
            "title": window_title.strip() if window_title else "",
            "text": f"{pet_name}: {clean_text}",
            "time": time.time()
        })
        if len(self.history) > self.max_total:
            self.history.pop(0)

    def record_user_comment(self, scene: str, window_title: str, user_comment: str):
        if not user_comment or not user_comment.strip():
            return
        self.history.append({
            "scene": scene,
            "title": window_title.strip() if window_title else "",
            "text": f"主人: {user_comment.strip()}",
            "time": time.time()
        })
        if len(self.history) > self.max_total:
            self.history.pop(0)

    def get_recent_context(self, scene: str, window_title: str, max_items: int = 3) -> List[str]:
        """
        Extract up to `max_items` previous critiques/dialogues for the current window or scene.
        Extremely lightweight: ~20-40 tokens total, strictly caps token expenditure
        while giving the AI full continuity without repeating itself!
        """
        now = time.time()
        matched = []
        curr_title = window_title.strip() if window_title else ""

        # Search backward from newest to oldest
        for item in reversed(self.history):
            # Only consider context within the last 20 minutes
            if now - item["time"] > 1200:
                continue

            item_title = item.get("title", "")
            # 1. Exact match on window title (e.g. same video or document)
            if curr_title and (curr_title in item_title or item_title in curr_title):
                if item["text"] not in matched:
                    matched.append(item["text"])
            # 2. Or same specialized scene (e.g. watching video or playing game)
            elif scene in ["video", "game"] and item.get("scene") == scene:
                if item["text"] not in matched:
                    matched.append(item["text"])

            if len(matched) >= max_items:
                break

        # Return chronological order (oldest to newest)
        return list(reversed(matched))

    def clear(self):
        self.history.clear()
