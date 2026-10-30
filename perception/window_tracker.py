import os
import sys
import ctypes
from ctypes import wintypes
from typing import Tuple, Dict, Any

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Self-ignore list: never critique our own pet, terminal, or launcher!
SELF_PROCESS_NAMES = [
    "python.exe", "pythonw.exe"
]

SELF_TITLE_KEYWORDS = [
    "gemini desktop pet", "ha-gemi", "哈gemi", "辉星喵喵子"
]

GAME_PROCESS_KEYWORDS = [
    "steam", "genshin", "starrail", "honkai", "epicgames", "league", "riot",
    "valorant", "dota2", "cs2", "csgo", "minecraft", "javaw", "blackmyth", "wukong",
    "eldenring", "monsterhunter", "overwatch", "apex", "pubg", "tslgame",
    "wutheringwaves", "zenlesszonezero", "zzz", "endfield", "palworld",
    "cyberpunk2077", "baldursgate3", "bg3", "sekiro", "darktide", "helldivers"
]

VIDEO_PROCESS_NAMES = [
    "potplayer64.exe", "potplayer.exe", "vlc.exe", "mpv.exe", "bilibili.exe"
]

VIDEO_TITLE_KEYWORDS = [
    "哔哩哔哩", "bilibili", "youtube", "腾讯视频", "爱奇艺", "优酷",
    "douyin", "抖音", "tiktok", "twitch", "acfun", "niconico",
    "直播", "live", "电影", "动漫", "剧场版", "ep", "第", "集", "season",
    "番剧", "录播", "up主", "up:"
]

DEV_PROCESS_KEYWORDS = [
    "code.exe", "devenv.exe", "pycharm64.exe", "idea64.exe", "clion64.exe", "cursor.exe", "sublime_text.exe"
]

CURRENT_PID = os.getpid()

def get_foreground_window_info() -> Dict[str, Any]:
    """Extract foreground window handle, title, process name, window rect and categorized scene."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "title": "", "process": "", "scene": "desktop", "rect": None, "is_self": False}

    # Window title
    length = user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title_buf, length + 1)
    title = title_buf.value.strip()

    # Process name & PID
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = ""

    h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if h_process:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
            process_name = os.path.basename(buf.value).lower()
        kernel32.CloseHandle(h_process)

    # Check if this window belongs to our desk pet or our own terminal
    is_self = False
    if pid.value == CURRENT_PID:
        is_self = True
    elif process_name in SELF_PROCESS_NAMES:
        is_self = True
    elif any(kw in title.lower() for kw in SELF_TITLE_KEYWORDS):
        is_self = True

    # Window Rect
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    window_rect = {
        "left": rect.left,
        "top": rect.top,
        "width": max(0, rect.right - rect.left),
        "height": max(0, rect.bottom - rect.top)
    }

    # Classify Scene
    scene = classify_scene(process_name, title)

    return {
        "hwnd": hwnd,
        "title": title,
        "process": process_name,
        "scene": scene,
        "rect": window_rect,
        "is_self": is_self
    }

def classify_scene(process_name: str, title: str) -> str:
    p_lower = process_name.lower()
    t_lower = title.lower()

    # 1. Video & Live Stream Check (Priority high so web video gets recognized)
    if p_lower in VIDEO_PROCESS_NAMES:
        return "video"
    for kw in VIDEO_TITLE_KEYWORDS:
        if kw in t_lower:
            return "video"

    # 2. Game Check
    for kw in GAME_PROCESS_KEYWORDS:
        if kw in p_lower:
            return "game"
    if any(k in t_lower for k in ["steam", "game", "游戏", "原神", "崩坏", "星穹铁道", "黑神话", "艾尔登法环"]):
        return "game"

    # 3. Dev / Work Check
    for kw in DEV_PROCESS_KEYWORDS:
        if kw in p_lower:
            return "work"

    # 4. Default browse / general desktop
    return "general"
