import os
import sys
import shutil
import zipfile
import tempfile
import logging
import threading
import queue
import time
from pathlib import Path
import gradio as gr
import yaml
# --- 路径设置 ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
sys.path.append(str(PROJECT_ROOT))

CURRENT_WORKFLOW = None

def process_stream(zip_file, api_key, concurrency):
    global CURRENT_WORKFLOW  # 声明使用全局变量
    
    if not zip_file:
        yield "❌ 未上传文件", 0, 0, "请先上传 ZIP 文件...", None
        return
        
def load_config(config_path: Path):
    """加载 YAML 配置文件"""
    if not config_path.exists():
        print(f"错误: 找不到配置文件 {config_path}")
        return None
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"读取配置文件失败: {e}")
        return None

config_path = PROJECT_ROOT / "config" / "settings.yaml"
config = load_config(config_path)
# 导入后端逻辑
try:
    from src.agent.workflow import ConversionWorkflow
    from src.utils.logger import setup_logger
except ImportError as e:
    print(f"环境错误: {e}")
    sys.exit(1)

# --- 自定义日志处理器 (用于将日志实时推送到 Gradio) ---
class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

# --- 辅助函数 ---
def unzip_file(zip_path: str, extract_to: str):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

def make_zip_archive(source_dir: str, output_path: str):
    shutil.make_archive(output_path, 'zip', root_dir=source_dir)
    return f"{output_path}.zip"

# --- CSS 样式 (复刻参考图风格) ---
custom_css = """
body { background-color: #f9fafb; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }

/* 标题样式 */
.header-title { color: #1e1b4b; font-weight: 800 !important; font-size: 28px !important; }
.header-icon { font-size: 30px; margin-right: 10px; }

/* 标签徽章风格 */
.label-badge { 
    background-color: #e0e7ff; 
    color: #4338ca; 
    padding: 4px 8px; 
    border-radius: 6px; 
    font-weight: bold; 
    font-size: 14px;
    margin-bottom: 5px;
    display: inline-block;
}

/* 状态卡片 */
.stat-card {
    border: 1px solid #e5e7eb;
    background: white;
    border-radius: 8px;
    padding: 15px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    text-align: center;
}

/* 终端日志窗口 */
#terminal-log textarea {
    background-color: #0f172a !important;
    color: #4ade80 !important; /* Matrix Green */
    font-family: 'Consolas', 'Monaco', monospace !important;
    font-size: 13px !important;
    line-height: 1.4 !important;
    border-radius: 8px !important;
    border: 1px solid #334155 !important;
}

/* 按钮风格 */
.primary-btn { 
    background-image: linear-gradient(to right, #4f46e5, #6366f1); 
    border: none;
    color: white !important;
}
.stop-btn {
    background-color: white !important;
    border: 1px solid #ef4444 !important;
    color: #ef4444 !important;
}
"""

# --- 核心处理逻辑 (生成器模式) ---
def process_stream(zip_file, api_key, concurrency):
    """
    生成器函数，实时 yield 日志和状态更新
    """

    if not zip_file:
        yield "❌ 未上传文件", 0, 0, "请先上传 ZIP 文件...", None
        return
    api_key = config.get('llm', {}).get('api_key')
    # 1. 准备环境
    final_api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
    if not final_api_key:
        yield "❌ API Key 缺失", 0, 0, "错误: 未找到 API Key", None
        return

    # 2. 设置日志捕获队列
    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setFormatter(logging.Formatter('[%(asctime)s] %(message)s', datefmt='%H:%M:%S'))
    
    # 获取根 Logger 并添加 Handler
    root_logger = logging.getLogger()
    # 临时移除其他 handler 防止重复或干扰，或者只添加到 root
    original_handlers = root_logger.handlers[:]
    root_logger.addHandler(queue_handler)
    root_logger.setLevel(logging.INFO)

    # 3. 在独立线程中运行 Workflow
    temp_dir_obj = tempfile.TemporaryDirectory()
    temp_dir = Path(temp_dir_obj.name)
    input_dir = temp_dir / "input"
    output_dir = temp_dir / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    # 解压
    try:
        unzip_file(zip_file.name, str(input_dir))
    except Exception as e:
        yield "❌ 解压失败", 0, 0, f"解压错误: {str(e)}", None
        return

    workflow = ConversionWorkflow(
        input_dir=str(input_dir),
        output_dir=str(output_dir),
        api_key=final_api_key,
        llm_config={"max_tokens": 4096}
    )
    workflow.set_max_workers(int(concurrency))
    
    # [关键] 将当前实例赋值给全局变量，以便 Stop 按钮能访问
    CURRENT_WORKFLOW = workflow
    # 定义线程任务
    worker_exception = None
    def run_workflow():
        nonlocal worker_exception
        try:
            workflow.run()
        except Exception as e:
            worker_exception = e

    t = threading.Thread(target=run_workflow)
    t.start()

    # 4. 主循环：读取日志并 Yield 更新 UI
    logs_accumulated = []
    
    while t.is_alive() or not log_queue.empty():
        # 尝试从队列获取所有新日志
        while not log_queue.empty():
            try:
                msg = log_queue.get_nowait()
                logs_accumulated.append(msg)
            except queue.Empty:
                break
        
        # 限制前端日志显示的长度，防止浏览器卡顿 (保留最后 200 行)
        display_logs = "\n".join(logs_accumulated[-200:])
        
        # 获取当前进度状态
        # 注意：workflow.state 需要是线程安全的 (我们之前改过的 AgentState)
        success_count = workflow.state.processed_count
        fail_count = workflow.state.failed_count
        total = workflow.state.total_files
        
        status_text = "🔄 处理中..." if t.is_alive() else "✅ 完成"
        if total > 0 and (success_count + fail_count) == total:
             status_text = "✅ Done!"
        # [新增] 如果发现状态变为已取消，更新 UI 提示
        if workflow.state.is_cancelled:
             yield "🛑 已停止", success_count, fail_count, display_logs + "\n\n[System] 用户手动停止任务。", None
             return # 退出生成器，结束 UI 更新
        # Yield 给 Gradio 更新界面
        yield status_text, success_count, fail_count, display_logs, None
        
        time.sleep(0.1) # 避免刷新过快
    CURRENT_WORKFLOW = None
    # 5. 线程结束后的收尾
    root_logger.removeHandler(queue_handler)
    # 恢复原始 handler (可选)
    # for h in original_handlers: root_logger.addHandler(h)

    if worker_exception:
        logs_accumulated.append(f"\n❌ 发生严重错误: {worker_exception}")
        yield "❌ 出错", success_count, fail_count, "\n".join(logs_accumulated[-200:]), None
    else:
        # 打包结果
        logs_accumulated.append("\n📦 正在打包结果...")
        yield "📦 打包中", success_count, fail_count, "\n".join(logs_accumulated[-200:]), None
        
        result_zip_name = os.path.join(tempfile.gettempdir(), f"html2md_result_{int(time.time())}")
        final_zip = make_zip_archive(str(output_dir), result_zip_name)
        
        logs_accumulated.append(f"✨ 全部完成！结果已准备好。")
        yield "✅ Done!", success_count, fail_count, "\n".join(logs_accumulated[-200:]), final_zip

    # 清理临时目录
    # temp_dir_obj.cleanup() # Gradio 返回文件后需要文件存在，这里依赖系统自动清理或稍后清理
def stop_conversion():
    global CURRENT_WORKFLOW
    if CURRENT_WORKFLOW:
        CURRENT_WORKFLOW.stop() # 调用 Workflow 的 stop 方法
        return "🛑正在停止..."
    return "⚠️当前没有运行的任务"
# --- JS 脚本：用于日志自动滚动到底部 ---
auto_scroll_js = """
function() {
    var ta = document.querySelector('#terminal-log textarea');
    if (ta) {
        ta.scrollTop = ta.scrollHeight;
    }
}
"""

# --- 构建 Gradio 界面 ---
with gr.Blocks(title="HTML2MD Agent", css=custom_css, theme=gr.themes.Soft()) as app:
    
    # Header
    with gr.Row(elem_classes="container"):
        with gr.Column():
            gr.Markdown("""
            # <span class="header-icon">🌐</span> HTML to Markdown Converter (AI Powered)
            <span style="color: #6b7280; font-size: 16px;">上传离线网页 ZIP 包，智能转换为 Markdown 文档。</span>
            """, elem_classes="header-title")

    # Input Section
    with gr.Row(elem_classes="container"):
        with gr.Column(scale=3):
            gr.HTML('<div class="label-badge">Target Website Archive (ZIP)</div>')
            file_input = gr.File(label="", file_count="single", file_types=[".zip"], height=100)
            
            with gr.Accordion("⚙️ 高级设置 (API Key & 并发)", open=False):
                with gr.Row():
                    api_key_input = gr.Textbox(label="API Key", type="password", placeholder="sk-...", show_label=True)
                    concurrency_slider = gr.Slider(1, 20, value=5, step=1, label="并发线程数")

        with gr.Column(scale=1, min_width=150):
            gr.HTML('<div class="label-badge">Actions</div>')
            start_btn = gr.Button("🚀 Start Conversion", elem_classes="primary-btn")
            stop_btn = gr.Button("🛑 Stop", elem_classes="stop-btn") # 停止功能需要后端支持，这里仅做 UI 占位

    # Status Section
    with gr.Row(elem_classes="container"):
        with gr.Column(scale=1):
            gr.HTML('<div class="label-badge">Status</div>')
            status_indicator = gr.Textbox(value="Waiting...", label="", show_label=False, interactive=False, elem_classes="stat-card")
        
        with gr.Column(scale=1):
            gr.HTML('<div class="label-badge">Files Converted</div>')
            success_counter = gr.Number(value=0, label="", show_label=False, interactive=False, elem_classes="stat-card")
            
        with gr.Column(scale=1):
            gr.HTML('<div class="label-badge">Errors (404/Fail)</div>')
            fail_counter = gr.Number(value=0, label="", show_label=False, interactive=False, elem_classes="stat-card")

    # Log & Output Section
    with gr.Row(elem_classes="container"):
        with gr.Column(scale=3):
            gr.HTML('<div class="label-badge">Terminal Log</div>')
            # 使用 elem_id 绑定 CSS，_js 绑定滚动事件
            log_output = gr.TextArea(
                label="", 
                show_label=False, 
                lines=12, 
                max_lines=12,
                elem_id="terminal-log",
                interactive=False,
                value="Waiting for input..."
            )
            
        with gr.Column(scale=1):
            gr.HTML('<div class="label-badge">Download ZIP</div>')
            download_output = gr.File(label="", interactive=False)

    # Event Binding
    # 使用 generator 实时更新
    start_event = start_btn.click(
        fn=process_stream,
        inputs=[file_input, api_key_input, concurrency_slider],
        outputs=[status_indicator, success_counter, fail_counter, log_output, download_output],
    )
    stop_btn.click(
        fn=stop_conversion,
        inputs=[],
        outputs=[status_indicator], # 可以让状态栏显示“正在停止...”
        cancels=[start_event] # [关键] 告诉 Gradio 取消 start_btn 的事件流
    )
    # 当 log_output 变化时，触发 JS 滚动到底部
    log_output.change(None, [], [], js=auto_scroll_js)

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=7502, show_error=True)