import os
import shutil
import hashlib
import logging
from pathlib import Path
from urllib.parse import unquote
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class AssetManager:
    def __init__(self, base_output_dir: str, asset_folder_name: str = "assets"):
        """
        初始化资源管理器
        :param base_output_dir: 输出的根目录 (例如 data/output)
        :param asset_folder_name: 存放图片的文件夹名称 (默认 assets)
        """
        self.base_output_dir = Path(base_output_dir)
        self.asset_dir = self.base_output_dir / asset_folder_name
        self.asset_folder_name = asset_folder_name
        
        # 确保输出目录存在
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    def process_html_content(self, html_content: str, source_html_path: Path, relative_path_from_root: Path) -> str:
        """
        处理 HTML 文本中的所有图片资源
        
        :param html_content: 原始 HTML 字符串
        :param source_html_path: 原始 HTML 文件的绝对路径 (用于定位本地资源)
        :param relative_path_from_root: 当前文件相对于输入根目录的路径 (用于计算回溯路径 ../)
        :return: 处理过图片路径的 HTML 字符串
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')

        if not images:
            return html_content

        # 计算 Markdown 文件到 assets 文件夹的相对层级
        # 例如：如果文件在 output/folder/doc.md，资源在 output/assets
        # 引用路径应该是 ../assets/image.png
        # parent.parts 比如 ('folder',) -> 长度1 -> 需要一个 "../"
        depth = len(relative_path_from_root.parent.parts)
        path_prefix = "../" * depth
        
        # 最终在 Markdown 中的资源前缀，例如: ../../assets/
        md_asset_prefix = f"{path_prefix}{self.asset_folder_name}/"

        count = 0
        for img in images:
            original_src = img.get('src')
            if not original_src:
                continue

            # 忽略网络图片和 Base64
            if original_src.startswith(('http:', 'https:', 'data:', '//')):
                continue

            # --- 核心修复：更强的本地文件查找逻辑 ---
            found_asset_path = self._resolve_local_path(source_html_path, original_src)
            
            if not found_asset_path:
                logger.warning(f"无法定位图片: {original_src} (在 {source_html_path.name} 中)")
                continue

            # --- 复制并重命名 ---
            new_filename = self._copy_and_rename_asset(found_asset_path)
            if new_filename:
                # --- 更新 HTML 引用 ---
                # 使用计算好的相对前缀，确保无论 MD 在哪一层都能找到图片
                new_relative_path = f"{md_asset_prefix}{new_filename}"
                img['src'] = new_relative_path
                count += 1
        
        logger.info(f"成功处理 {count}/{len(images)} 张图片")
        return str(soup)

    def _resolve_local_path(self, html_path: Path, src: str) -> Path:
        """
        尝试多种方式解析本地图片路径，解决 URL 编码和分隔符问题
        """
        parent_dir = html_path.parent
        
        # 候选列表
        candidates = []
        
        # 1. 直接拼接 (即使有 %20)
        candidates.append(parent_dir / src)
        
        # 2. URL 解码拼接 (处理 %20 -> 空格)
        decoded_src = unquote(src)
        candidates.append(parent_dir / decoded_src)
        
        # 3. 处理 Windows/Linux 分隔符差异
        # 浏览器有时保存为 "Folder/Image.png"，有时 "Folder\Image.png"
        candidates.append(parent_dir / decoded_src.replace('/', '\\'))
        candidates.append(parent_dir / decoded_src.replace('\\', '/'))
        
        # 4. 暴力搜索 (针对某些奇怪的相对路径前缀)
        # 如果 src 是 "./images/pic.png"，去掉 ./
        clean_src = decoded_src.lstrip('./').lstrip('.\\')
        candidates.append(parent_dir / clean_src)

        for path in candidates:
            try:
                if path.exists() and path.is_file():
                    return path.resolve()
            except OSError:
                continue
                
        return None

    def _copy_and_rename_asset(self, source_path: Path) -> str:
        """
        复制文件并返回哈希文件名
        """
        try:
            file_content = source_path.read_bytes()
            file_hash = hashlib.md5(file_content).hexdigest()
            suffix = source_path.suffix.lower() or ".jpg"
            
            new_filename = f"{file_hash}{suffix}"
            target_path = self.asset_dir / new_filename

            if not target_path.exists():
                target_path.write_bytes(file_content)
            
            return new_filename
        except Exception as e:
            logger.error(f"复制图片失败 {source_path}: {e}")
            return None