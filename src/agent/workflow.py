import logging
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional

# 导入工具和组件
from src.tools.file_scanner import FileScanner
from src.tools.asset_manager import AssetManager
from src.tools.html_cleaner import HtmlCleaner
from src.llm.client import LLMClient
from src.agent.state import AgentState

logger = logging.getLogger(__name__)

class ConversionWorkflow:
    def __init__(self, input_dir: str, output_dir: str, api_key: str, llm_config: Optional[Dict[str, Any]] = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        
        # 读取配置中的并发数，默认为 4
        self.config = llm_config or {}
        # 注意：这里假设 processing 配置可能混在 llm_config 里传进来，
        # 或者我们需要在 main.py 里单独把 processing 配置传进来。
        # 为了兼容之前的代码结构，我们暂时硬编码或从 llm_config 获取，建议后续在 main.py 统一传一个全量 config
        # 这里为了简单，先给个默认值 5
        self.max_workers = 5 
        
        # 初始化组件
        self.state = AgentState()
        self.scanner = FileScanner(str(self.input_dir))
        self.asset_manager = AssetManager(str(self.output_dir))
        self.cleaner = HtmlCleaner()
        self.llm_client = LLMClient(api_key=api_key, llm_config=llm_config)

    def set_max_workers(self, workers: int):
        """允许外部设置并发数"""
        self.max_workers = workers

    def run(self):
        """执行主流程 (并行版)"""
        # 1. 扫描任务
        tasks = self.scanner.scan()
        self.state.total_files = len(tasks)
        
        if self.state.total_files == 0:
            logger.warning("未找到任何 HTML 文件，流程结束。")
            return

        logger.info(f"=== 扫描完成，共 {self.state.total_files} 个任务，即将启动 {self.max_workers} 线程并行处理 ===")

        # 2. 线程池并行处理
        # 使用 ThreadPoolExecutor 自动管理线程
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务，建立 future -> task 的映射
            future_to_task = {
                executor.submit(self._process_single_file_safe, task): task 
                for task in tasks
            }

            # as_completed 会在某个任务一旦完成时立刻 yield
            for future in concurrent.futures.as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    # 获取结果，如果函数里抛出异常，会在 future.result() 重新抛出
                    success = future.result()
                    
                    # 状态更新已移至 _process_single_file_safe 内部或在这里调用
                    # 为保持逻辑清晰，我们在 worker 内部处理了大部分逻辑，这里只负责最后的进度打印
                    progress = self.state.get_progress_str()
                    if success:
                        logger.info(f"[{progress}] ✅ 完成: {task.file_stem}")
                    else:
                        logger.warning(f"[{progress}] ⚠️ 失败: {task.file_stem}")

                except Exception as e:
                    self.state.fail_task()
                    logger.error(f"❌ 线程异常 ({task.file_stem}): {e}")

        # 3. 总结报告
        self._print_summary()
    def stop(self):
        """[新增] 外部调用的停止方法"""
        logger.warning("接收到停止指令，正在终止工作流...")
        self.state.set_cancelled()

    def _process_single_file_safe(self, task) -> bool:
        """线程安全的处理函数"""
        try:
            # [新增] 检查点 1：任务刚开始时
            if self.state.is_cancelled:
                return False

            # 1. 读取文件
            raw_html = self._read_file_safe(task.html_path)
            if not raw_html:
                self.state.fail_task()
                return False
            # [新增] 检查点 2：在耗时的 LLM 调用前再次检查
            if self.state.is_cancelled:
                return False
            # 2. 资源本地化
            html_with_assets = self.asset_manager.process_html_content(
                html_content=raw_html, 
                source_html_path=task.html_path,
                relative_path_from_root=task.relative_path
            )

            # 3. 清洗
            cleaned_html = self.cleaner.clean(html_with_assets)
            if not cleaned_html:
                self.state.fail_task()
                return False

            # 4. LLM 转换 (最耗时步骤)
            markdown_content = self.llm_client.convert_html_to_md(cleaned_html)
            if not markdown_content:
                self.state.fail_task()
                return False

            # 5. 保存
            self._save_markdown(markdown_content, task)
            
            # 成功计数
            self.state.complete_task()
            return True

        except Exception as e:
            logger.error(f"处理任务 {task.file_stem} 时发生内部错误: {e}", exc_info=True)
            self.state.fail_task()
            return False

    # _read_file_safe, _save_markdown, _print_summary 保持不变
    def _read_file_safe(self, file_path: Path) -> Optional[str]:
        encodings = ['utf-8', 'gb18030', 'gbk', 'windows-1252']
        for enc in encodings:
            try:
                return file_path.read_text(encoding=enc)
            except UnicodeDecodeError: continue
            except Exception: return None
        return None

    def _save_markdown(self, content: str, task):
        relative_folder = task.relative_path.parent
        target_folder = self.output_dir / relative_folder
        target_folder.mkdir(parents=True, exist_ok=True)
        target_file = target_folder / f"{task.file_stem}.md"
        target_file.write_text(content, encoding='utf-8')

    def _print_summary(self):
        logger.info("=" * 30)
        logger.info(f"🎉 并行处理结束")
        logger.info(f"总任务数: {self.state.total_files}")
        logger.info(f"成功: {self.state.processed_count}")
        logger.info(f"失败: {self.state.failed_count}")
        logger.info("=" * 30)