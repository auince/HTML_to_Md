import logging
import re
from typing import List, Optional
from bs4 import BeautifulSoup, Comment, Tag

logger = logging.getLogger(__name__)

class HtmlCleaner:
    def __init__(self):
        # 定义需要完全移除的标签（连同内容一起移除）
        # 针对文档类网页：script/style是噪音，form/button通常是交互元素不需要保留
        self.tags_to_remove = [
            'script', 'style', 'noscript', 'iframe', 
            'meta', 'link', 'svg', 'path', 
            'button', 'input', 'form', 'select', 'textarea',
            'nav', 'footer' # 视情况而定，文档页的 footer 通常是版权信息，nav 是目录（已有 TOC）
        ]
        
        # 定义需要保留的属性
        # 我们只保留对 Markdown 语义有帮助的属性，移除 onclick, data-*, style 等
        self.allowed_attributes = {
            'src', 'href', 'alt', 'title', 
            'rowspan', 'colspan', # 表格关键属性
            'class', 'id' # 有时 class 能帮助 LLM 识别 "代码块" 或 "警告框"
        }

    def clean(self, html_content: str) -> str:
        """
        清洗 HTML 内容，移除无用标签和属性
        :param html_content: 原始 HTML 字符串
        :return: 清洗后的 HTML 字符串
        """
        if not html_content:
            return ""

        soup = BeautifulSoup(html_content, 'html.parser')

        # 1. 移除注释 
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()

        # 2. 移除特定的噪音标签及其内容
        for tag_name in self.tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose() # decompose 会连同子节点完全销毁

        # 3. 清理标签属性 (Token 瘦身)
        # 遍历所有 tag，只保留白名单内的属性
        for tag in soup.find_all(True):
            # 获取当前标签的所有属性名
            # list(tag.attrs) 是为了避免在遍历时修改字典报错
            current_attrs = list(tag.attrs.keys())
            for attr in current_attrs:
                if attr not in self.allowed_attributes:
                    del tag[attr]
                
                # 特殊处理：如果 href 是 "javascript:..." 这种，直接移除 href
                if attr == 'href' and isinstance(tag.get('href'), str):
                     if tag['href'].strip().lower().startswith('javascript:'):
                         del tag['href']

        # 4. (可选) 移除空标签
        # 很多网页包含大量的空 div 或 span 用于布局
        for tag in soup.find_all(['div', 'span', 'p']):
            if len(tag.get_text(strip=True)) == 0 and len(tag.find_all('img')) == 0:
                tag.decompose()

        # 5. 简单的文本压缩
        # 这里的 prettify 可能会增加多余换行，我们直接输出 string 
        # 但为了让 LLM 看着舒服，可以做一个简单的正则替换多余空行
        cleaned_html = str(soup)
        
        # 压缩连续的空行，但保留 HTML 结构的可读性
        cleaned_html = re.sub(r'\n\s*\n', '\n', cleaned_html)
        
        logger.debug(f"HTML 清洗完成，长度从 {len(html_content)} 减少到 {len(cleaned_html)}")
        return cleaned_html

# --- 测试代码 ---
if __name__ == "__main__":
    cleaner = HtmlCleaner()
    
    raw_html = """
    <html>
        <head>
            <title>测试页面</title>
            <script>console.log("Analytics code");</script>
            <style>body { color: red; }</style>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>
            <nav>
                <ul><li>Home</li><li>About</li></ul>
            </nav>

            <div class="main-content" style="background: #fff;" data-tracking="123">
                <h1>LLaMA Factory 教程</h1>
                <p>这是正文内容。</p>
                <div class="ad-banner">
                    <script>showAd();</script>
                </div>
                <img src="assets/demo.png" alt="示例图" width="500">
                
                <p>下面是一个表格：</p>
                <table>
                    <tr><td colspan="2">数据</td></tr>
                </table>

                <br><br> <span></span> </div>
            
            <footer>Copyright 2026</footer>
        </body>
    </html>
    """
    
    print("--- 清洗前 ---")
    print(f"长度: {len(raw_html)}")
    
    cleaned = cleaner.clean(raw_html)
    
    print("\n--- 清洗后 ---")
    print(cleaned)
    print(f"长度: {len(cleaned)}")
    
    # 验证逻辑：
    # 1. script, style, link, nav, footer 应该消失
    # 2. div 的 style, data-tracking 属性应该消失，但 class 应该保留
    # 3. img 的 src, alt 应该保留，width 应该消失
    # 4. 空 span 应该消失