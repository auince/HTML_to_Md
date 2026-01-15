import os
import sys
import yaml
import logging
from pathlib import Path

# --- 路径设置 ---
# 获取当前脚本所在目录 (src/)
CURRENT_DIR = Path(__file__).resolve().parent
# 获取项目根目录 (src/ 的上一级)
PROJECT_ROOT = CURRENT_DIR.parent
# 将项目根目录添加到 python path
sys.path.append(str(PROJECT_ROOT))

# --- 模块导入 ---
try:
    from src.agent.workflow import ConversionWorkflow
    from src.utils.logger import setup_logger
except ImportError as e:
    print(f"模块导入错误: {e}")
    print("请确保在项目根目录下运行，或检查目录结构。")
    sys.exit(1)

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

def main():
    # 1. 定位配置文件
    config_path = PROJECT_ROOT / "config" / "settings.yaml"
    config = load_config(config_path)
    
    if not config:
        sys.exit(1)

    # 2. 初始化日志
    log_level = config.get('app', {}).get('log_level', 'INFO')
    # 日志文件存放在 logs 目录下
    log_file = PROJECT_ROOT / "logs" / "agent.log"
    logger = setup_logger(name="HTML2MD", log_level=log_level, log_file=str(log_file))

    logger.info("=== HTML to Markdown Agent 启动 ===")

    # 3. 解析 API Key
    # 优先级: 环境变量 > 配置文件中的 api_key
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        api_key = config.get('llm', {}).get('api_key')
    
    if not api_key:
        logger.error("未找到 API Key！")
        logger.error("请设置环境变量 'DEEPSEEK_API_KEY' 或在 config/settings.yaml 中配置。")
        sys.exit(1)

    # 4. 解析输入输出路径
    # 支持相对路径（相对于项目根目录）或绝对路径
    input_dir_str = config['app']['input_dir']
    output_dir_str = config['app']['output_dir']
    
    # [新增] 读取并发数配置
    max_workers = config.get('processing', {}).get('max_workers', 5)
    input_dir = PROJECT_ROOT / input_dir_str
    output_dir = PROJECT_ROOT / output_dir_str

    if not input_dir.exists():
        logger.error(f"输入目录不存在: {input_dir}")
        logger.info("正在尝试自动创建输入目录...")
        try:
            input_dir.mkdir(parents=True, exist_ok=True)
            logger.info("创建成功，请将 HTML 文件放入该目录后重新运行。")
        except Exception as e:
            logger.error(f"创建目录失败: {e}")
        sys.exit(0)

    # 5. 启动工作流
    logger.info(f"输入目录: {input_dir}")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"使用模型: {config.get('llm', {}).get('model_name', 'deepseek-chat')}")
    try:
        workflow = ConversionWorkflow(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            api_key=api_key,
            llm_config=config.get('llm')
        )
        # [新增] 设置并发数
        workflow.set_max_workers(max_workers)
        
        workflow.run()
    except Exception as e:
        logger.critical(f"程序运行中发生未捕获异常: {e}", exc_info=True)

if __name__ == "__main__":
    main()