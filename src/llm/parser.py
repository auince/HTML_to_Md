import re

class OutputParser:
    @staticmethod
    def parse_markdown(text: str) -> str:
        """
        清洗 LLM 返回的文本，去除可能的代码块包裹和多余空白
        """
        if not text:
            return ""

        cleaned_text = text.strip()

        # 1. 去除 ```markdown ... ``` 或 ``` ... ``` 包裹
        # 匹配开头
        if cleaned_text.startswith("```"):
            # 找到第一个换行符，去掉第一行 (```markdown)
            first_newline = cleaned_text.find("\n")
            if first_newline != -1:
                cleaned_text = cleaned_text[first_newline+1:]
        
        # 匹配结尾
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]

        # 2. 去除可能的 "Here is the markdown:" 等废话 (简单规则)
        # 如果前50个字符包含 "Sure" 或 "Here is"，尝试截断（视情况启用，目前保持保守）
        
        return cleaned_text.strip()