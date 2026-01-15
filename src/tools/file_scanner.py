import os
import logging
from pathlib import Path
from typing import List, Optional, Dict
from dataclasses import dataclass

# 配置日志（如果在 main.py 中已配置，这里可以省略 basicConfig）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ScanResult:
    """
    定义单个扫描结果的数据结构
    """
    html_path: Path             # HTML 文件的绝对路径
    resource_dir: Optional[Path] # 对应的 _files 文件夹路径 (如果存在)
    relative_path: Path         # 相对于输入根目录的路径 (用于保持输出结构)
    file_stem: str              # 文件名 (不含后缀)，用于命名 MD 文件

class FileScanner:
    def __init__(self, root_dir: str):
        """
        初始化扫描器
        :param root_dir: 数据的根目录 (例如 data/input)
        """
        self.root_dir = Path(root_dir)
        if not self.root_dir.exists():
            raise FileNotFoundError(f"输入目录不存在: {self.root_dir}")

    def scan(self) -> List[ScanResult]:
        """
        递归扫描目录，寻找 .html/.htm 文件及其对应的资源文件夹
        :return: ScanResult 对象列表
        """
        results = []
        logger.info(f"开始扫描目录: {self.root_dir} ...")

        # os.walk 递归遍历
        for root, dirs, files in os.walk(self.root_dir):
            root_path = Path(root)
            
            for file in files:
                # 检查是否为网页文件
                if file.lower().endswith(('.html', '.htm')):
                    file_path = root_path / file
                    
                    # 尝试寻找对应的资源文件夹
                    # 规则：如果文件是 "Page Name.html"，资源文件夹通常是 "Page Name_files"
                    # Windows 下有时候也会是 ".files"，这里优先匹配你的截图结构 "_files"
                    file_stem = file_path.stem
                    expected_resource_name = f"{file_stem}_files"
                    
                    resource_dir = None
                    if expected_resource_name in dirs:
                        resource_dir = root_path / expected_resource_name
                        logger.debug(f"找到资源关联: {file} -> {expected_resource_name}")
                    else:
                        logger.debug(f"未找到资源文件夹，将作为纯文本处理: {file}")

                    # 计算相对路径 (用于后续保持输出目录结构)
                    try:
                        relative_path = file_path.relative_to(self.root_dir)
                    except ValueError:
                        relative_path = Path(file) # 兜底

                    scan_result = ScanResult(
                        html_path=file_path.absolute(),
                        resource_dir=resource_dir.absolute() if resource_dir else None,
                        relative_path=relative_path,
                        file_stem=file_stem
                    )
                    
                    results.append(scan_result)

        logger.info(f"扫描完成，共找到 {len(results)} 个网页文件。")
        return results

# --- 测试代码 (直接运行此文件时执行) ---
if __name__ == "__main__":
    # 假设你在这个脚本的上两级目录运行，且有一个 data/input 文件夹
    test_input_dir = "../../data/input" 
    
    # 简单的 mock 数据创建，防止报错，实际使用请确保目录存在
    if not os.path.exists(test_input_dir):
        print(f"提示：测试目录 {test_input_dir} 不存在，请手动创建或修改路径进行测试。")
    else:
        scanner = FileScanner(test_input_dir)
        tasks = scanner.scan()
        
        print("\n--- 扫描结果预览 ---")
        for i, task in enumerate(tasks, 1):
            print(f"[{i}] 文件: {task.file_stem}")
            print(f"    路径: {task.html_path}")
            print(f"    资源: {'存在' if task.resource_dir else '无'}")
            if task.resource_dir:
                print(f"    资源路径: {task.resource_dir}")
            print("-" * 30)