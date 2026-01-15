# src/agent/state.py

import threading
from dataclasses import dataclass, field

@dataclass
class AgentState:
    total_files: int = 0
    processed_count: int = 0
    failed_count: int = 0
    
    # [新增] 停止标志，默认为 False
    is_cancelled: bool = False

    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # [新增] 设置停止状态的方法
    def set_cancelled(self):
        with self._lock:
            self.is_cancelled = True

    def complete_task(self):
        with self._lock:
            self.processed_count += 1

    def fail_task(self):
        with self._lock:
            self.failed_count += 1
            
    def get_progress_str(self) -> str:
        with self._lock:
            return f"{self.processed_count + self.failed_count}/{self.total_files}"