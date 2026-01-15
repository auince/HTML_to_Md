# HTML_to_Md

# HTML2MD  - 智能网页转 Markdown 工具

**HTML2MD** 是一个基于大语言模型（默认使用DeepSeek）构建的智能文档转换工具。它专为处理Website-downloader下载的“离线网页”设计，能够将杂乱的 HTML 源码转换为干净、结构化且图片完整的 Markdown 文档，便于后续RAG或其他用途的使用。

## ✨ 核心功能

* **智能递归扫描**：自动遍历文件夹，识别 `.html` 文件及其关联的资源文件夹（如 `_files`）。
* **本地资源重建**：自动提取 HTML 中的本地图片，去重、重命名并移动到统一的 `assets` 目录，修复 Markdown 中的图片引用路径。
* **智能降噪**：在发送给 LLM 之前，使用算法预处理移除广告、脚本、导航栏等 60%+ 的无用代码，节省 Token 成本。
* **LLM 语义转换**：利用 DeepSeek 大模型精准识别文档结构，保留表格、代码块（含语言标识）、LaTeX 公式和引用。
* **并发加速**：支持多线程并行处理，大幅提升批量转换效率。

## 📂 项目结构

```text
HTML2MD/
├── config/
│   ├── settings.yaml      # 主配置文件 (路径、API Key、并发数)
│   └── prompt.yaml        # LLM 系统提示词
├── data/
│   ├── input/             # [入口] 把下载的网页文件夹放这里
│   └── output/            # [出口] 生成的 MD 文档和 assets 图片
├── src/
│   ├── agent/             # 核心逻辑 (工作流、状态管理)
│   ├── llm/               # 大模型接口 (Client, Parser)
│   ├── tools/             # 工具箱 (扫描、清洗、图片搬运)
│   ├── utils/             # 通用工具 (日志)
│   └── main.py            # 程序入口
├── logs/                  # 运行日志
├── requirements.txt       # 依赖列表
└── README.md              # 说明文档

```

## 🚀 快速开始

### 1. 环境准备

确保已安装 Python 3.8 或更高版本。

```bash
# 克隆或下载项目后，安装依赖
pip install openai beautifulsoup4 pyyaml

```

### 2. 配置 API Key

你可以通过环境变量设置 DeepSeek API Key（推荐），或直接修改配置文件。

**方式 A：环境变量 (推荐)**

* Windows (PowerShell): `$env:DEEPSEEK_API_KEY="sk-你的key"`
* Linux/Mac: `export DEEPSEEK_API_KEY="sk-你的key"`

**方式 B：配置文件**
修改 `config/settings.yaml`：

```yaml
llm:
  api_key: "sk-你的key"  # 注意不要将含 Key 的文件上传到公开仓库

```

### 3. 准备数据

将你从浏览器下载的网页（通常包含 `.html` 文件和同名的 `_files` 文件夹）放入 **`data/input`** 目录中。支持多层子文件夹结构。

### 4. 运行转换

```bash
python src/main.py

```

程序启动后，你将在控制台看到并行处理的进度条。完成后，请前往 `data/output` 查看结果。

## ⚙️ 配置说明 (`config/settings.yaml`)

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `app.input_dir` | 输入文件夹路径 | `data/input` |
| `app.output_dir` | 输出文件夹路径 | `data/output` |
| `llm.model_name` | 使用的模型名称 | `deepseek-chat` |
| `llm.max_tokens` | 单次输出最大长度 | `4096` |
| `processing.max_workers` | **并发线程数** (根据机器性能调整) | `5` |

## 🛠️ 工作流原理

1. **Scanner**: 扫描 `input` 目录，将 `xxx.html` 与 `xxx_files` 文件夹配对。
2. **Asset Manager**:
* 解析 HTML 中的 `src` 路径（处理 URL 编码）。
* 将图片复制到 `output/assets`，并使用 MD5 哈希重命名以去重。
* 计算 Markdown 文件到 `assets` 的相对路径（如 `../../assets/img.png`）。


3. **Cleaner**: 移除 `<script>`, `<style>`, `<nav>` 等无关标签，清洗 DOM 树。
4. **LLM Client**: 将清洗后的 HTML 发送给 DeepSeek，执行 "HTML to Markdown" 转换指令。
5. **Output**: 将结果保存为 `.md` 文件，保持原有的文件夹层级结构。

## ❓ 常见问题

**Q: 图片在 Markdown 里不显示？**
A: 请确保原网页的 `_files` 文件夹完整。Agent 会自动处理相对路径，生成的 Markdown 无论在任何层级，图片引用路径都会自动修正为指向 `assets` 文件夹。

**Q: 处理速度太慢？**
A: 这是 IO 密集型任务。请在 `settings.yaml` 中调大 `max_workers`（例如设为 10），这取决于你的 API Rate Limit。

**Q: 报错 `NoneType object has no attribute get`？**
A: 检查 `config/prompt.yaml` 文件是否为空。如果是空的，请填入默认提示词。

---

**License**: MIT