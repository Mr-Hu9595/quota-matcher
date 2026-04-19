# Quota Matcher - 工程量清单智能定额匹配工具

An intelligent engineering bill matching tool that automatically matches construction quantity lists (工程量清单) with quota/subsistence codes from the **Henan Province 2016 Installation Engineering Budget Quota (河南省2016安装工程预算定额)**.

---

## 项目进度与任务清单 (2026-04-19)

### 已完成

- [x] **本地规则匹配引擎** (`local_matcher.py`)
  - MATERIAL_QUOTA_MAP 精确映射表（涵盖 100+ 常见材料/设备）
  - 电力电缆按最大单芯截面匹配规则
  - 控制电缆按芯数匹配规则
  - 角钢/槽钢等金属结构件区分制作(4-7-5)和安装(4-7-6)
  - 钢管 DN 规格精确匹配

- [x] **工程量清单解析** (`file_parser.py`)
  - Excel/Word 多格式支持
  - 智能规格型号识别
  - 多行条目合并

- [x] **辅料配比计算** (`quota_matcher.py`)
  - 电信：摄像头 → 防爆接线箱 + 防爆挠性管
  - 电气：防爆灯 → 电力电缆头 + 接线盒

- [x] **向量搜索模块** (`vector_store.py`)
  - ChromaDB + SQLite 双存储架构
  - MiniMax Embedding API 集成（代码完成，待额度）

### 进行中

- [ ] **向量索引构建** (因 MiniMax API 余额不足暂停)
  - 已加载 16,881 条定额数据到 `quota.db`
  - 待续：在高配计算机上完成向量索引构建

### 待办事项

1. **向量搜索增强**
   - 使用本地 Embedding 模型（如 sentence-transformers）构建索引
   - 推荐模型：`all-MiniLM-L6-v2`（轻量，80MB）或 `paraphrase-multilingual-MiniLM-L12-v2`（中文支持）

2. **定额匹配规则完善**
   - 持续从实际项目中发现并修复规则遗漏的条目
   - 完善规格型号提取逻辑

3. **测试覆盖**
   - 更多真实清单格式适配
   - 边界 case 处理

---



## Features

- **Multi-format Support**: Automatically parses Excel (.xlsx/.xls) and Word (.docx) engineering bills
- **Smart Column Detection**: Intelligently recognizes column names across different companies (项目名称, 设备名称, 材料名称, etc.)
- **Local Keyword Matching**: High-coverage direct matching using built-in MATERIAL_QUOTA_MAP for common materials and equipment
- **AI Semantic Enhancement** (optional): Uses MiniMax API for semantic understanding when local matching is uncertain
- **Automatic Unit Conversion**:
  - Steel products (angle steel, channel steel, I-beam): meters → kg
  - Power/control cables: meters → 100m
- **Quota Rules Compliance**: Follows official quota matching rules (电力电缆 by max single-core cross-section, 控制电缆 by core count)

## Supported Quota Categories

| Category | Examples |
|----------|----------|
| Steel Conduits | 镀锌钢管, 热镀锌钢管, 防爆钢管, PVC管 |
| Cable Laying | 电力电缆, 控制电缆, 直埋电缆, 光缆, 网线 |
| Bridge/Tray | 桥架, 槽式桥架, 梯式桥架 |
| Junction Boxes | 接线盒, 开关盒, 穿线盒 |
| Electrical Equipment | 配电箱, 配电柜, UPS, 蓄电池 |
| Motors | 异步电动机, 防爆电动机 |
| Lighting | 路灯, 防爆灯, LED灯 |
| Surveillance | 摄像机, 硬盘录像机, 交换机 |
| Fire Alarm | 感烟探测器, 火灾报警控制器 |
| Grounding | 避雷网, 接地母线, 等电位连接 |
| Ducts/Flexible | 金属软管, 挠性管, 防爆胶泥 |

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

- `openpyxl >= 3.0.0` - Excel read/write
- `python-docx >= 0.8.11` - Word read/write
- `requests >= 2.28.0` - HTTP requests (for AI matching)

### Optional: AI Enhancement

Set MiniMax API key for semantic matching (significantly improves accuracy for ambiguous items):

```bash
# Linux/Mac
export MINIMAX_API_KEY=sk-cp-your-key-here

# Windows (CMD)
set MINIMAX_API_KEY=sk-cp-your-key-here

# Windows (PowerShell)
$env:MINIMAX_API_KEY="sk-cp-your-key-here"
```

Get your API key at: https://platform.minimaxi.com/

## Usage

### Quick Start

```bash
# Process Excel bill
python quota_matcher.py "path/to/bill.xlsx"

# Process Word bill
python quota_matcher.py "path/to/bill.docx"

# Specify output path
python quota_matcher.py "input.xlsx" -o "output.xlsx"
```

### Claude Code Integration

When installed as a Claude Code skill, it triggers automatically on keywords:

- "为xx清单匹配定额"
- "做一下x清单预算"
- "清单定额匹配"
- "工程量清单套定额"
- "这份清单套一下定额"

### Standalone Python Usage

```python
from quota_loader import QuotaLoader
from local_matcher import LocalMatcher

# Load quota data
loader = QuotaLoader()
quotas = loader.load()

# Create matcher (use_websearch=False for local-only)
matcher = LocalMatcher(quotas, use_websearch=False)

# Match a single item
result = matcher.match("电力电缆4×25+1×16", quantity=100, unit="m")
print(result)
# {'code': '4-9-161', 'name': '室内敷设电力电缆 铜芯...', 'unit': '100m', 'confidence': 'high', ...}

# Batch match
items = [
    {"name": "镀锌钢管DN25", "quantity": 50, "unit": "m"},
    {"name": "控制电缆10×1.5", "quantity": 200, "unit": "m"},
]
results = matcher.batch_match(items)
```

## Output Format

Generated Excel with columns:

| 列名 | 说明 |
|------|------|
| 序号 | Row number |
| 施工内容 | Original item name from bill |
| 定额编号 | Matched quota code |
| 定额名称 | Quota item name |
| 单位 | Quota standard unit |
| 工程量 | Matched quantity |
| 匹配方式 | 精确匹配/模糊匹配/待人工确认 |
| 备注 | Match notes, unit conversion info |

## Quota Matching Rules

### Power Cables (电力电缆)

Match by **maximum single-core cross-section**:

| Cable | Rule | Example |
|-------|------|---------|
| 4×25+1×16 | max core = 25mm² | → 4-9-161 (≤35mm²) |
| 4×240+1×120 | max core = 240mm² | → 4-9-165 (≤240mm²) |

### Control Cables (控制电缆)

Match by **total core count**:

| Cable | Rule | Example |
|-------|------|---------|
| 10×1.5 | 10 cores | → 4-9-311 (≤14芯) |
| 24×1.5 | 24 cores | → 4-9-312 (≤24芯) |

### Coefficient Notes

Quota items are priced for standard conditions. When actual conditions differ, apply coefficients:

- **5-core power cable laying**: ×1.3 (base quota is 3-core)
- **6-core power cable laying**: ×1.6 (base quota is 3-core)
- **Copper cable terminal (vs aluminum)**: ×1.2
- **5-core cable terminal (vs 3-core)**: ×1.2

These coefficients are applied manually during billing, not automatically.

## File Structure

```
quota-matcher/
├── skill.json              # Claude Code skill config
├── quota_matcher.py        # Main entry point
├── quota_loader.py         # Quota file loader
├── local_matcher.py        # Local keyword matching
├── minimax_matcher.py      # AI semantic matching
├── file_parser.py          # Excel/Word parser
├── column_identifier.py    # Column name detection
├── unit_converter.py       # Unit conversion
├── vector_store.py         # Vector database (ChromaDB + SQLite)
├── doc_to_docx.py          # .doc to .docx converter
├── quantity_extractor.py   # Engineering quantity extraction
├── requirements.txt        # Python dependencies
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

### 在新机器上继续开发

1. **克隆仓库**
   ```bash
   git clone https://github.com/Mr-Hu9595/quota-matcher.git
   cd quota-matcher
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **安装向量模型（可选，用于本地向量搜索）**
   ```bash
   pip install sentence-transformers
   ```

4. **构建向量索引**（可选）
   ```python
   import os
   from quota_loader import QuotaLoader
   from vector_store import VectorStore

   # 使用本地模型（推荐）
   vs = VectorStore(embedding_model="local")
   vs.build_index(quotas)
   ```

## Quota Data File

The tool requires the quota data file: `河南省通用安装工程预算定额2016.txt`

Place the quota file in the parent directory of the project:

```
your-project/
├── quota-matcher/          # This project
└── 河南省通用安装工程预算定额2016.txt
```

The quota file format (tab-separated):

```
1-1-1    台式及仪表机床 设备重量0.3t以内    台    518.97
1-1-2    台式及仪表机床 设备重量0.5t以内    台    672.15
...
```

## License

MIT

## Contributing

Issues and pull requests welcome!
