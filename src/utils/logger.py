import logging
import sys
from pathlib import Path

def setup_logger(name: str = "HTML2MD", log_level: str = "INFO", log_file: str = None):
    """
    配置全局 Logger
    :param name: Logger 名称
    :param log_level: 日志等级 (DEBUG, INFO, WARNING, ERROR)
    :param log_file: 日志文件路径 (如果为 None 则不输出到文件)
    """
    logger = logging.getLogger(name)
    
    # 将字符串等级转换为 logging 常量
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    
    # 防止重复添加 handler (避免日志重复打印)
    if logger.handlers:
        return logger

    # 定义日志格式
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%H:%M:%S'
    )

    # 1. 控制台输出 Handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # 2. 文件输出 Handler (如果指定了文件路径)
    if log_file:
        try:
            log_path = Path(log_file)
            # 确保日志文件夹存在
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: 无法创建日志文件 {log_file}: {e}")

    return logger