# CLAUDE.md - Quota Matcher 项目上下文

## 语言
项目过程中使用中文和用户交流

## 项目概述

**项目名称**: Quota Matcher - 工程量清单智能定额匹配工具

**核心目标**: 自动解析工程量清单（Excel/Word/PDF），智能匹配河南省2016安装工程预算定额，输出广联达可直接导入的 Excel 格式。

**用户**: 预算工程师，使用广联达软件进行工程造价

**输出目标**: 生成包含定额编号、项目名称、工程量表达式、单位的 Excel，可直接导入广联达预算软件。

---

## 业务流程

```
工程量清单 → 智能解析 → 语义匹配定额 → 单位换算 → 广联达Excel
```

1. **工程量解析**: 解析不同公司的清单格式（Excel/Word/PDF），提取显性和隐性工程量
2. **定额匹配**: 语义理解工作内容，从定额数据库匹配正确定额
3. **单位换算**: 自动将清单单位转换为定额标准单位
4. **输出**: 生成广联达兼容格式

---

## 技术架构

### 三层分离架构

```
┌─────────────────────────────────────────────────────────────────┐
│                   自然语言接口 (CLI / Claude Code)               │
│  用户: "处理这份工程量清单" / "添加一条新规则" / "查询4-9开头的定额"  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      业务层 (Business)                           │
│  quota_matcher.py  ← 只管流程编排，不碰数据                      │
│  • process_workflow()    文件解析 → 工程量识别 → 匹配 → 输出    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                   匹配引擎层 (Matching Engine)                     │
│  纯逻辑接口，接口稳定，不含数据操作                               │
│                                                                 │
│  engine/base.py          ← EngineABC 抽象基类                    │
│  engine/rule_engine.py   ← 规则库精确匹配                        │
│  engine/chat_engine.py   ← MiniMax Chat API 语义匹配             │
│  engine/hybrid_engine.py ← 规则优先 + Chat 辅助                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      数据层 (Data)                                │
│  只做数据CRUD，不含任何业务逻辑，接口标准化                        │
│                                                                 │
│  data/quota_db.py        ← 定额数据库 (SQLite)                   │
│  data/rule_db.py         ← 规则数据库 (SQLite)                   │
└─────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
quota-matcher/
├── src/                          # 源代码
│   ├── data/                     # 数据层（稳定）
│   │   ├── quota_db.py          # 定额数据库 (SQLite)
│   │   └── rule_db.py           # 规则数据库 (SQLite)
│   ├── engine/                   # 引擎层（可插拔）
│   │   ├── base.py              # 抽象基类 EngineABC + MatchResult
│   │   ├── rule_engine.py       # 规则精确匹配
│   │   ├── chat_engine.py       # MiniMax Chat API 语义匹配
│   │   └── hybrid_engine.py      # 规则优先 + Chat 辅助
│   ├── business/                 # 业务层
│   │   └── quota_matcher.py     # 主流程编排
│   ├── cli/                      # CLI接口
│   │   └── cli.py               # 自然语言驱动入口
│   ├── utils/                    # 工具
│   │   └── logging.py           # 统一日志
│   ├── quota_matcher.py         # 主入口（兼容）
│   ├── file_parser.py            # 文件解析
│   ├── quantity_extractor.py     # 工程量提取
│   ├── unit_converter.py         # 单位换算
│   ├── quota_matcher.py         # 主入口（兼容）
│   ├── chm_parser.py            # CHM帮助文件解析
│   ├── column_identifier.py     # 列标识器
│   ├── doc_to_docx.py           # Word转换
│   └── quota_loader.py          # 定额加载器
├── db/                          # 数据库目录
│   ├── quota.db                 # SQLite 定额数据库 (37,821条)
│   └── 定额/                    # TXT原始定额文件
├── scripts/                     # 工具脚本
├── 规则库/                      # 规则库文件 (55条规则)
│   ├── rules.db                 # SQLite 规则数据库
│   ├── 定额匹配规则库.json      # JSON格式规则
│   └── 河南省安装工程定额匹配规则.md
├── 规则样板/                    # 广联达输出格式样板
├── logs/                        # 日志目录
└── CLAUDE.md                    # 本文件
```

### 数据层接口（稳定不变）

```python
# 定额数据库
quota_db.get_by_code(code)       # 按编号查
quota_db.search_by_prefix(prefix)  # 按前缀查
quota_db.search_by_keyword(kw)   # 按关键词查

# 规则数据库
rule_db.get_rules(prefix)         # 获取规则
rule_db.add_rule(code, name, unit, keywords)  # 添加规则
rule_db.confirm_rule(code)       # 确认使用（自学习）
```

### 引擎层接口（可插拔）

```python
# 引擎基类
engine.match(work_content, context)  # 单条匹配
engine.batch_match(items)            # 批量匹配

# 可用引擎
RuleEngine      # 纯规则匹配
ChatEngine      # MiniMax Chat API 语义匹配
HybridEngine    # 混合匹配（规则优先 + Chat 辅助，默认）
```

### 数据查询 vs 引擎匹配

**原则**：简单查询用数据层接口，引擎只做匹配

- `quota_db.search_by_keyword('配电箱')` → 直接搜定额
- `quota_db.search_by_prefix('4-9')` → 按章节前缀搜
- `rule_db.get_rules(prefix='4-9')` → 查规则库

**引擎的职责**：
- 接收工作内容描述
- 解析规格参数（DN/功率/截面/芯数/桥架/半周长）
- 综合评分排序返回 MatchResult

**不要做的事**：看到"无匹配"就改引擎代码。先验证数据层接口是否已满足需求。

---

## 日志功能

日志目录: `logs/`

| 文件 | 说明 |
|------|------|
| business.log | 业务流程日志 |
| engine.log | 引擎调试日志 |
| data.log | 数据层日志 |
| match.log | 匹配操作详细日志 |
| api.log | API调用日志 |

日志等级: DEBUG < INFO < WARNING < ERROR

---

## 自然语言驱动 (Claude Code)

通过 CLI 接口用自然语言控制程序：

```bash
# 处理工程量清单
python src/cli/cli.py process "D:\清单.xlsx" -o "D:\结果.xlsx"

# 查询定额
python src/cli/cli.py query --keyword "电力电缆"
python src/cli/cli.py query --prefix "4-9"

# 学习新规则
python src/cli/cli.py learn --code "4-9-999" --name "测试" --unit "10m" --keywords "电力电缆,测试"

# 确认规则（自学习）
python src/cli/cli.py confirm --code "4-9-159"

# 统计信息
python src/cli/cli.py stats
```

---

## 匹配策略

**核心原则**: 规则精确匹配优先，MiniMax AI 语义理解为辅

### 匹配流程（HybridEngine）

1. **规则匹配**: 关键词精确匹配，命中多个关键词则高置信度
2. **Chat 辅助**: MiniMax M2.7 大模型语义理解，从候选定额中选择最优
3. **综合排序**: 规则命中 × 0.7 + Chat 分数 × 0.3
4. **置信度评估**: high/medium/low/待人工确认

### 规则匹配（高优先级）

`rule_engine.py` 用于：
- 标准化条目精确匹配（已知映射）
- 电力电缆按最大单芯截面选择定额
- 控制电缆按芯数选择定额
- 钢管按 DN 规格精确匹配

### Chat 匹配（MiniMax API）

`chat_engine.py` 用于：
- 语义相似度理解
- 模糊/非标准表述匹配
- 跨表述变体识别
- 需要配置 `MINIMAX_API_KEY` 或 `MINIMAX_CHAT_API_KEY` 环境变量

---

## 关键文件说明

| 文件 | 职责 | 关键类/函数 |
|------|------|-------------|
| `cli/cli.py` | 自然语言驱动入口 | `QuotaCLI` |
| `business/quota_matcher.py` | 主流程编排 | `QuotaMatcherBusiness.process()` |
| `data/quota_db.py` | 定额数据库 | `QuotaDB` |
| `data/rule_db.py` | 规则数据库 | `RuleDB` |
| `engine/base.py` | 引擎抽象基类 | `EngineABC`, `MatchResult` |
| `engine/rule_engine.py` | 规则精确匹配 | `RuleEngine` |
| `engine/chat_engine.py` | MiniMax API 语义匹配 | `ChatEngine` |
| `engine/hybrid_engine.py` | 混合匹配引擎 | `HybridEngine` |
| `file_parser.py` | 文件解析 | `FileParser.parse()` |
| `quantity_extractor.py` | 工程量提取 | `QuantityExtractor.extract()` |
| `unit_converter.py` | 单位换算 | `UnitConverter.convert()` |

---

## 单位换算规则

| 类型 | 清单单位 | 定额单位 | 说明 |
|------|----------|----------|------|
| 角钢/槽钢/工字钢 | 米 | kg | 按理论重量表换算 |
| 电力电缆 | 米 | 100m | 500米 → 表达式500，工程量5 |
| 控制电缆 | 米 | 100m | 同上 |

---

## 广联达输出格式

**列定义**：
- **序号**: 行号
- **定额编号**: 如 4-9-165
- **定额名称**: 如 室内敷设电力电缆 铜芯
- **单位**: 定额标准单位，如 100m
- **工程量表达式**: 识别到的原始工程量，或换算成kg/ton后的工程量
- **工程量**: 表达式 ÷ 定额单位倍数
- **匹配方式**: 精确匹配/模糊匹配/待人工确认
- **备注**: 原始规格型号等

**示例**：
| 序号 | 定额编号 | 定额名称 | 单位 | 工程量表达式 | 工程量 | 匹配方式 | 备注 |
|------|----------|----------|------|-------------|--------|----------|------|
| 1 | 4-9-165 | 室内敷设电力电缆 铜芯... | 100m | 500 | 5 | 精确匹配 | YJV-4×240+1×120 |

---

## 数据库状态

| 数据库 | 数量 | 说明 |
|--------|------|------|
| db/quota.db quotas | 37,821 | 8个专业定额 |
| 规则库/rules.db rules | 55 | 匹配规则库 |

---

## 扩展计划

### 短期
- [x] 完善 README 和 CLAUDE.md
- [x] 三层架构重构（数据层/引擎层/业务层分离）
- [x] 日志功能
- [x] CLI自然语言接口
- [ ] 优化通用匹配规则

### 中期
- [ ] 支持 PDF 格式解析
- [ ] 丰富规则库
- [ ] 完善单位换算规则

### 长期
- [ ] 支持其他省份定额
- [ ] 批量处理多份清单
- [ ] 预算审核辅助

---

## 参考资料

- [河南省2016安装工程预算定额](src/河南省通用安装工程预算定额2016.txt)
- [广联达服务新干线](https://www.fwxgx.com/) - 定额详情参考网站
- [广联达预算软件](https://www.glodon.com/)
- [工程样板（广联达输出格式）](规则样板/3万吨年CHDM(1,4-环己烷二甲醇)项目/) - 电气/电信预算表，含定额编号示例
