import os
import yaml
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from openai import OpenAI, APIError

# 引入解析器
try:
    from src.llm.parser import OutputParser
except ImportError:
    class OutputParser:
        @staticmethod
        def parse_markdown(text): return text.strip()

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, api_key: str, llm_config: Optional[Dict[str, Any]] = None):
        """
        初始化 LLM 客户端
        :param api_key: API Key
        :param llm_config: LLM 配置字典
        """
        if not api_key:
            raise ValueError("API Key 不能为空")

        # 1. 确定项目根目录
        self.project_root = Path(__file__).resolve().parent.parent.parent
        
        # 2. 加载配置
        self.config = llm_config if llm_config else self._load_fallback_settings()
        
        # 3. 提取参数
        self.base_url = self.config.get("api_base", "https://api.deepseek.com")
        self.model_name = self.config.get("model_name", "deepseek-chat")
        self.temperature = self.config.get("temperature", 0.1)
        
        # --- [修改点 1] 提取 max_tokens ---
        # 如果配置文件里没写，默认给 4096，防止长文档被截断
        self.max_tokens = self.config.get("max_tokens", 8192)
        
        logger.info(f"LLM Client 初始化: Model={self.model_name}, MaxTokens={self.max_tokens}")

        # 4. 初始化 OpenAI 客户端
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.base_url
        )
        
        # 5. 加载外部提示词
        self.system_prompt = self._load_system_prompt()

    def _load_fallback_settings(self) -> Dict[str, Any]:
        """如果外部没传配置，尝试自己读 settings.yaml"""
        settings_path = self.project_root / "config" / "settings.yaml"
        if settings_path.exists():
            try:
                with open(settings_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    return data.get("llm", {})
            except Exception as e:
                logger.warning(f"无法读取 settings.yaml: {e}")
        return {}

    def _load_system_prompt(self) -> str:
        """从 config/prompt.yaml 加载系统提示词"""
        prompt_path = self.project_root / "config" / "prompt.yaml"
        default_prompt = "你是一个 HTML 转 Markdown 助手。" 
        
        if not prompt_path.exists():
            return default_prompt

        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data is None: 
                    return default_prompt
                return data.get("html_to_md_system", default_prompt)
        except Exception as e:
            logger.error(f"读取提示词文件失败: {e}")
            return default_prompt

    def convert_html_to_md(self, html_content: str) -> str:
        """
        调用 LLM 将 HTML 转换为 Markdown
        """
        if not html_content or not html_content.strip():
            logger.warning("传入了空的 HTML 内容，跳过 LLM 请求。")
            return ""

        try:
            logger.debug(f"正在发送请求给 {self.model_name} (MaxTokens: {self.max_tokens})...")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"请将以下 HTML 转换为 Markdown:\n\n{html_content}"}
                ],
                temperature=self.temperature,
                # --- [修改点 2] 传入 max_tokens ---
                max_tokens=self.max_tokens,
                stream=False
            )

            raw_content = response.choices[0].message.content
            
            # 使用 Parser 清洗输出
            cleaned_content = OutputParser.parse_markdown(raw_content)
            
            return cleaned_content

        except APIError as e:
            logger.error(f"LLM API 调用失败: {e}")
            return f"> **转换失败**: API Error\n> {str(e)}\n\n\n{html_content}"
        except Exception as e:
            logger.error(f"发生未知错误: {e}")
            return f"> **转换错误**: {str(e)}"

# --- 测试代码 ---
if __name__ == "__main__":
    # 简易测试
    key = os.getenv("DEEPSEEK_API_KEY")
    if key:
        client = LLMClient(api_key=key)
        print(f"提示词预览: {client.system_prompt[:50]}...")
        res = client.convert_html_to_md("<h1>Test</h1><p>Hello</p>")
        print("转换结果:", res)
    else:
        print("请设置 DEEPSEEK_API_KEY 环境变量进行测试")