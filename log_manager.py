import time
from typing import List, Dict
from PyQt6.QtCore import QObject, pyqtSignal

class LogManager(QObject):
    log_added = pyqtSignal(str, str, str)  # timestamp, level, text

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        super().__init__()
        self.logs: List[Dict[str, str]] = []
        self.max_logs = 300

    def log(self, level: str, message: str):
        t_str = time.strftime("%H:%M:%S")
        entry = {
            "time": t_str,
            "level": level.upper(),
            "message": message
        }
        self.logs.append(entry)
        if len(self.logs) > self.max_logs:
            self.logs.pop(0)

        # Print to console as well
        print(f"[{t_str}] [{level.upper()}] {message}", flush=True)
        self.log_added.emit(t_str, level.upper(), message)

    def info(self, msg: str):
        self.log("INFO", msg)

    def critique(self, msg: str):
        self.log("CRITIQUE", msg)

    def scene(self, msg: str):
        self.log("SCENE", msg)

    def error(self, msg: str):
        self.log("ERROR", msg)
