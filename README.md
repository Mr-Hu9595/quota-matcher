# Quota Matcher - 工程量清单智能定额匹配工具

An intelligent engineering bill matching tool that automatically matches construction quantity lists (工程量清单) with quota/subsistence codes from the **Henan Province 2016 Installation Engineering Budget Quota (河南省2016安装工程预算定额)**.

---

## 项目目的

本工具实现**工程量清单到定额**的自动化匹配流程：

```text
工程量清单（Excel/Word/PDF）
       ↓
   智能解析 → 提取工作内容和工程量
       ↓
   语义理解 → AI 语义分析工作内容
       ↓
   规则兜底 → 标准化条目精确匹配
       ↓
   单位换算 → 转换为定额标准单位
       ↓
广联达Excel（可直接导入）
```

**核心价值**：
- **格式通用** - 自动识别不同公司、不同格式的清单
- **语义匹配** - 充分理解工作内容，智能匹配正确定额（结合 AI 与规则库）
- **单位自换** - 自动将清单单位转换为定额标准单位

---

## 项目结构与三层分离架构

项目采用严格的**三层分离架构**，确保业务逻辑、匹配引擎和数据存储互不干扰：

```text
quota-matcher/
├── db/                          # 数据库目录
│   ├── 河南省通用安装工程预算定额2016.txt
│   └── quota.db                 # SQLite 定额数据库 (约37,821条)
├── 规则库/
│   ├── rules.db                 # SQLite 规则数据库
│   ├── 定额匹配规则库.json
│   └── 河南省安装工程定额匹配规则.md
├── src/                         # 源代码
│   ├── data/                    # 【数据层】只做数据CRUD，接口标准化
│   │   ├── quota_db.py          # 定额数据库操作
│   │   └── rule_db.py           # 规则数据库操作
│   ├── engine/                  # 【引擎层】可插拔的纯逻辑匹配接口
│   │   ├── base.py              # 抽象基类 EngineABC + MatchResult
│   │   ├── rule_engine.py       # 规则精确匹配
│   │   ├── chat_engine.py       # MiniMax Chat API 语义匹配
│   │   ├── hybrid_engine.py     # 混合匹配引擎 (规则优先 + Chat 辅助)
│   │   └── spec_parser.py       # 规格参数解析器 (DN/功率/截面/芯数等)
│   ├── business/                # 【业务层】流程编排
│   │   └── quota_matcher.py     # 主流程编排，不碰数据
│   ├── cli/                     # CLI 接口 (自然语言驱动入口)
│   │   └── cli.py
│   ├── file_parser.py           # 文件解析器 (Excel/Word/PDF)
│   ├── quantity_extractor.py    # 工程量提取
│   ├── unit_converter.py        # 单位换算工具
│   └── quota_matcher.py         # 旧版主入口点（向后兼容）
├── scripts/                     # 工具脚本
├── tests/                       # 测试代码
├── requirements.txt             # Python 依赖
├── skill.json                   # Claude Code skill 配置
├── README.md                    # 本文件
└── CLAUDE.md                    # Claude Code 上下文
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量 (可选，推荐用于语义匹配)

使用 AI 语义匹配需要配置 MiniMax API Key：

```bash
# Windows (PowerShell)
$env:MINIMAX_API_KEY="your_api_key_here"

# Linux / macOS
export MINIMAX_API_KEY="your_api_key_here"
```

### 3. 使用自然语言 CLI

```bash
# 处理 Excel 清单并指定输出
python src/cli/cli.py process "path/to/bill.xlsx" -o "path/to/output.xlsx"

# 快捷查询定额
python src/cli/cli.py query --keyword "电力电缆"
python src/cli/cli.py query --prefix "4-9"

# 学习新规则
python src/cli/cli.py learn --code "4-9-999" --name "测试规则" --unit "10m" --keywords "电力电缆,测试"

# 确认规则（自学习）
python src/cli/cli.py confirm --code "4-9-159"

# 查看统计信息
python src/cli/cli.py stats
```

> **注意**: 旧版本的入口 `python -m src.quota_matcher` 仍然可用，但推荐使用新的 CLI 工具。

---

## 核心模块与匹配策略

### FileParser & QuantityExtractor - 解析与提取
- 识别文件格式（Excel/Word/PDF），自动识别列结构（名称/规格/数量/单位）。
- 支持**显性工程量**（直接读取表格数据）和**隐性工程量**（正则解析描述文本）。
- 结合 `SpecParser` 提取具体的型号、规格参数（DN、功率、截面、芯数等）。

### Matcher - 定额匹配引擎 (HybridEngine)
**匹配策略**（规则精确匹配优先，MiniMax AI 语义理解为辅）：
1. **规则匹配** (`RuleEngine`)：关键词精确匹配，解析规格参数，命中多个关键词则判定为高置信度。
2. **Chat 辅助** (`ChatEngine`)：利用 MiniMax M2.7 大模型进行语义相似度理解，处理模糊/非标准表述变体。
3. **综合排序**：规则命中分数 × 0.7 + Chat 模型分数 × 0.3。
4. 返回综合评估置信度：`high` / `medium` / `low` / 待人工确认。

### UnitConverter - 单位换算
自动将清单单位转换为定额标准单位：
- 钢材（角钢、槽钢、工字钢）：米 → 千克 (kg)
- 电缆（电力/控制）：米 → 100米 (100m)
- 计算与定额单位匹配的最终工程量。

---

## 输出格式

生成的 Excel 文件可直接导入广联达预算软件，包含以下核心列：

| 序号 | 定额编号 | 定额名称 | 单位 | 工程量表达式 | 工程量 | 匹配方式 | 备注 |
|------|----------|----------|------|-------------|--------|----------|------|
| 1 | 4-9-165 | 室内敷设电力电缆 铜芯... | 100m | 500 | 5 | 精确匹配 | YJV-4×240+1×120 |

**工程量表达式与定额单位的关系**：
- **工程量表达式列**：识别到的原始工程量（如 500 表示 500米）。
- **工程量列**：表达式 ÷ 定额单位倍数（如 500 ÷ 100 = 5）。

---

## Claude Code 智能集成

当在 Trae / Claude Code 等智能工具中使用时，你可以直接使用自然语言：
- "为xx清单匹配定额"
- "做一下x清单预算"
- "清单定额匹配"
- "工程量清单套定额"
- "这份清单套一下定额"

AI 助手将自动读取工作流规范并执行全自动解析、定额匹配、甚至利用 MCP 工具联网查询主材价格的闭环操作。

---

## Python API 调用示例

如果你想在代码中集成该工具：

```python
from src.business.quota_matcher import QuotaMatcherBusiness

# 初始化业务层（将自动初始化 HybridEngine 和 SQLite 数据库）
business = QuotaMatcherBusiness()

# 处理清单文件
output_file = business.process(
    input_file="D:/清单.xlsx", 
    output_file="D:/结果.xlsx"
)
print(f"处理完成，结果已保存至: {output_file}")
```

---

## License

MIT

## Contributing

Issues and pull requests welcome!
