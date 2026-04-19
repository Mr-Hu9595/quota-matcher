# Quota Matcher - 工程量清单智能定额匹配工具

An intelligent engineering bill matching tool that automatically matches construction quantity lists (工程量清单) with quota/subsistence codes from the **Henan Province 2016 Installation Engineering Budget Quota (河南省2016安装工程预算定额)**.

---

## 项目目的

本工具实现**工程量清单到定额**的自动化匹配流程：

```
工程量清单（Excel/Word/PDF）
       ↓
   智能解析 → 提取工作内容和工程量
       ↓
   语义理解 → 向量数据库语义搜索
       ↓
   规则兜底 → 标准化条目精确匹配
       ↓
   单位换算 → 转换为定额标准单位
       ↓
广联达Excel（可直接导入）
```

**核心价值**：
- **格式通用** - 自动识别不同公司、不同格式的清单
- **语义匹配** - 充分理解工作内容，智能匹配正确定额
- **单位自换** - 自动将清单单位转换为定额标准单位

---

## 项目结构

```
quota-matcher/
├── db/                                    # 数据库文件夹
│   ├── 河南省通用安装工程预算定额2016.txt   # ⭐ 原始定额数据
│   ├── quota.db                          # SQLite 元数据库
│   └── chroma_data/                      # ChromaDB 向量数据库
│
├── src/                                   # 源代码
│   ├── __init__.py
│   ├── quota_matcher.py                  # 主入口点
│   ├── quota_loader.py                   # 定额文件加载器
│   ├── local_matcher.py                  # 本地规则匹配引擎
│   ├── minimax_matcher.py                # MiniMax AI 语义匹配
│   ├── vector_store.py                   # 向量存储 (ChromaDB + SQLite)
│   ├── file_parser.py                    # Excel/Word 文件解析器
│   ├── column_identifier.py              # 列名智能识别
│   ├── unit_converter.py                 # 单位换算工具
│   ├── quantity_extractor.py             # 工程量提取模块
│   └── claude_matcher.py                 # Claude 集成匹配器
│
├── scripts/                               # 工具脚本
│   ├── build_vector_index.py             # 构建向量索引脚本
│   └── demo.py                           # 演示脚本
│
├── tests/                                # 测试
│   ├── __init__.py
│   └── test_quantity_extractor.py
│
├── docs/                                  # 文档
│   └── superpowers/
│       ├── plans/
│       └── specs/
│
├── .gitignore
├── skill.json                            # Claude Code skill 配置
├── requirements.txt                      # Python 依赖
├── README.md                            # 本文件
└── CLAUDE.md                            # Claude Code 上下文
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 构建向量数据库

首次使用需要构建定额向量数据库：

```bash
# 使用本地模型（推荐，无需 API Key）
python scripts/build_vector_index.py

# 使用 MiniMax API（需要 API Key）
python scripts/build_vector_index.py --api-key YOUR_API_KEY
```

### 3. 使用

```bash
# 处理 Excel 清单
python -m src.quota_matcher "path/to/bill.xlsx"

# 处理 Word 清单
python -m src.quota_matcher "path/to/bill.docx"

# 指定输出路径
python -m src.quota_matcher "input.xlsx" -o "output.xlsx"
```

---

## 核心模块

### FileParser - 多格式文件解析

解析不同公司的工程量清单，支持：
- Excel (.xlsx / .xls)
- Word (.docx)
- 自动识别列结构（项目名称、设备名称、材料名称等）
- 智能合并多行条目

### QuantityExtractor - 工程量提取

从清单中提取工程量，支持：
- **显性工程量**：直接从表格提取
- **隐性工程量**：从描述文本中解析
- **附表明细**：识别并处理附表中的详细规格

### VectorStore - 向量数据库

基于 ChromaDB + SQLite 的向量知识库：
- 定额条目全部向量化存储
- 语义相似度搜索
- 支持本地模型或 API 生成向量

### Matcher - 定额匹配

**匹配策略**（语义为主，规则为辅）：
1. 语义理解工作内容
2. 向量搜索候选定额
3. 规则精确匹配兜底
4. 返回最佳匹配结果

### UnitConverter - 单位换算

自动将清单单位转换为定额标准单位：
- 钢材（角钢、槽钢、工字钢）：米 → 千克
- 电缆（电力/控制）：米 → 100米
- 其他常用单位换算

---

## 定额匹配流程

```
┌─────────────────────────────────────────────────────────────┐
│                     输入：工程量清单                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  FileParser - 解析文件                                        │
│  - 识别文件格式（Excel/Word/PDF）                            │
│  - 识别列结构（名称/规格/数量/单位）                          │
│  - 提取原始工程量数据                                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  QuantityExtractor - 工程量提取                               │
│  - 显性工程量：直接读取表格数据                                │
│  - 隐性工程量：正则解析描述文本                                │
│  - 规格识别：提取型号、规格参数                                │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Matcher - 定额匹配                                           │
│                                                             │
│  ┌─────────────────┐    ┌─────────────────┐                │
│  │  Vector Search   │    │  Rule Matcher   │                │
│  │  (语义搜索)      │    │  (规则兜底)     │                │
│  └────────┬────────┘    └────────┬────────┘                │
│           │                      │                         │
│           └──────────┬───────────┘                         │
│                      ▼                                      │
│            ┌─────────────────┐                             │
│            │  置信度评估      │                             │
│            │  高/中/低/待确认  │                             │
│            └────────┬────────┘                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  UnitConverter - 单位换算                                     │
│  - 清单单位 → 定额标准单位                                    │
│  - 计算与定额单位匹配的工程量                                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  输出：广联达Excel                                            │
│  - 定额编号 / 项目名称 / 工程量 / 单位                         │
│  - 可直接导入广联达预算软件                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 向量数据库说明

### 为什么使用向量搜索？

传统规则匹配的问题：
- 换一份清单格式可能需要修改代码
- 无法处理表述差异但实质相同的工作内容
- 300+ 映射规则难以维护和扩展

向量搜索的优势：
- **语义理解**："安装防爆摄像头" 能匹配 "安装防爆摄像机"
- **零规则维护**：新增定额只需重建索引
- **通用适配**：不同公司的表述习惯都能正确理解

### 构建定额知识库

将河南省2016安装工程预算定额中的每一条定额：
1. 解析工作内容描述
2. 生成语义向量
3. 存储到向量数据库

匹配时，输入工作内容描述，检索最相似的定额。

---

## 输出格式

生成的 Excel 文件可直接导入广联达预算软件：

| 序号 | 定额编号 | 定额名称 | 单位 | 工程量表达式 | 工程量 | 匹配方式 | 备注 |
|------|----------|----------|------|-------------|--------|----------|------|
| 1 | 4-9-165 | 室内敷设电力电缆 铜芯... | 100m | 5 | 500m | 精确匹配 | YJV-4×240+1×120 |

**工程量表达式与定额单位的关系**：
- **工程量表达式列**：填入识别到的原始工程量，或长度单位换算成 kg/ton 后的工程量（如 500 表示识别到 500米）
- **工程量列**：表达式 ÷ 定额单位倍数（如 500 ÷ 100m = 5）

---

## Claude Code 集成

当安装为 Claude Code skill 时，自动识别以下关键词：

- "为xx清单匹配定额"
- "做一下x清单预算"
- "清单定额匹配"
- "工程量清单套定额"
- "这份清单套一下定额"

---

## Python API

```python
from src.quota_loader import QuotaLoader
from src.local_matcher import LocalMatcher

# 加载定额数据
loader = QuotaLoader(quota_file="db/河南省通用安装工程预算定额2016.txt")
quotas = loader.load()

# 创建匹配器
matcher = LocalMatcher(quotas, use_websearch=False)

# 单条匹配
result = matcher.match("电力电缆4×25+1×16", quantity=100, unit="m")
print(result)
# {'code': '4-9-161', 'name': '室内敷设电力电缆 铜芯...', 'unit': '100m', 'confidence': 'high', ...}

# 批量匹配
items = [
    {"name": "镀锌钢管DN25", "quantity": 50, "unit": "m"},
    {"name": "控制电缆10×1.5", "quantity": 200, "unit": "m"},
]
results = matcher.batch_match(items)
```

---

## 开发指南

### 克隆仓库后初始化

```bash
git clone https://github.com/Mr-Hu9595/quota-matcher.git
cd quota-matcher
pip install -r requirements.txt
```

### 运行测试

```bash
python -m pytest tests/ -v
```

### 构建向量索引

```bash
python scripts/build_vector_index.py
```

---

## 依赖

- `openpyxl >= 3.0.0` - Excel 读写
- `python-docx >= 0.8.11` - Word 读写
- `requests >= 2.28.0` - HTTP 请求（用于 AI 匹配）
- `chromadb >= 0.4.0` - 向量数据库（可选）
- `sentence-transformers` - 本地 Embedding 模型（可选）

---

## License

MIT

## Contributing

Issues and pull requests welcome!
