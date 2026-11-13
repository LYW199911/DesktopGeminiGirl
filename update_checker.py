import re
import os
import sys
import threading
import requests
import webbrowser
from PyQt6.QtCore import QObject, pyqtSignal

GITHUB_REPO_OWNER = "LYW199911"
GITHUB_REPO_NAME = "DesktopGeminiGirl"
API_LATEST_RELEASE = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

def parse_version_tuple(v_str: str) -> tuple:
    """Parses version strings like 'v1.5.0', '1.5.0-dynamic', 'v1.4.2' into comparable integer tuples."""
    if not v_str:
        return (0, 0, 0)
    clean = re.sub(r'^[vV]', '', str(v_str).strip())
    clean = clean.split('-')[0].split('+')[0]
    parts = clean.split('.')
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

def is_newer_version(current_ver: str, remote_ver: str) -> bool:
    """Returns True if remote_ver is strictly newer than current_ver."""
    curr = parse_version_tuple(current_ver)
    remote = parse_version_tuple(remote_ver)
    return remote > curr

class UpdateChecker(QObject):
    check_finished = pyqtSignal(dict, bool, str)  # (release_data, is_newer, error_msg)
    download_progress = pyqtSignal(int)          # 0 ~ 100
    download_finished = pyqtSignal(str)          # downloaded file path
    download_error = pyqtSignal(str)             # error message

    def __init__(self, current_version: str = "v1.5.0", parent=None):
        super().__init__(parent)
        self.current_version = current_version
        self.latest_data = {}
        self.is_downloading = False

    def check_async(self):
        """Asynchronously queries GitHub Releases in a daemon thread."""
        def worker():
            try:
                headers = {
                    "User-Agent": "HaGemi-Update-Checker",
                    "Accept": "application/vnd.github.v3+json"
                }
                resp = requests.get(API_LATEST_RELEASE, headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json()
                    self.latest_data = data
                    remote_tag = data.get("tag_name", "")
                    newer = is_newer_version(self.current_version, remote_tag)
                    self.check_finished.emit(data, newer, "")
                else:
                    self.check_finished.emit({}, False, f"GitHub 返回状态码: {resp.status_code}")
            except Exception as e:
                self.check_finished.emit({}, False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def download_asset_async(self, download_url: str, dest_dir: str, filename: str):
        """Streams asset download with progress updates."""
        if self.is_downloading:
            return
        self.is_downloading = True

        def worker():
            try:
                os.makedirs(dest_dir, exist_ok=True)
                dest_path = os.path.join(dest_dir, filename)
                temp_path = dest_path + ".tmp"

                headers = {"User-Agent": "HaGemi-Update-Checker"}
                resp = requests.get(download_url, headers=headers, stream=True, timeout=15)
                resp.raise_for_status()

                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = int((downloaded / total_size) * 100)
                            self.download_progress.emit(percent)

                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
                os.rename(temp_path, dest_path)
                self.is_downloading = False
                self.download_finished.emit(dest_path)
            except Exception as e:
                self.is_downloading = False
                self.download_error.emit(str(e))

        threading.Thread(target=worker, daemon=True).start()
