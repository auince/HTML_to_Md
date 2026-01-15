import re
from pathlib import Path
import os

class PathHelper:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        移除非法的文件名字符 (Windows/Linux)
        """
        # 替换 / \ : * ? " < > | 为下划线
        return re.sub(r'[\\/*?:"<>|]', '_', filename)

    @staticmethod
    def ensure_dir(path: str):
        """确保目录存在"""
        Path(path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_relative_path(full_path: Path, root_path: Path) -> Path:
        """安全地计算相对路径"""
        try:
            return full_path.relative_to(root_path)
        except ValueError:
            return Path(full_path.name)