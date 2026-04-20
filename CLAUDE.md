# CLAUDE.md - Quota Matcher 项目上下文

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
2. **定额匹配**: 语义理解工作内容，从向量数据库匹配正确定额
3. **单位换算**: 自动将清单单位转换为定额标准单位
4. **输出**: 生成广联达兼容格式

---

## 技术架构

### 目录结构

```
quota-matcher/
├── db/                           # 数据库（定额原文、SQLite、向量数据）
├── src/                          # 源代码
│   ├── quota_matcher.py          # 主入口
│   ├── quota_loader.py           # 定额加载
│   ├── local_matcher.py          # 规则匹配
│   ├── minimax_matcher.py        # AI语义匹配
│   ├── vector_store.py           # 向量存储
│   ├── file_parser.py            # 文件解析
│   ├── column_identifier.py      # 列名识别
│   ├── unit_converter.py         # 单位换算
│   └── quantity_extractor.py     # 工程量提取
├── scripts/                      # 工具脚本
└── tests/                        # 测试
```

### 核心数据流

```
输入文件 (Excel/Word)
         │
         ▼
    FileParser.parse()
         │
         ▼
    QuantityExtractor.extract()
         │
         ▼
    Matcher.match()  ◄─────────── VectorStore.search()
         │                        │
         │                        └── QuotaLoader.load()
         ▼
    UnitConverter.convert()
         │
         ▼
    输出 Excel
```

---

## 匹配策略

**核心原则**: 语义理解为主，规则匹配为辅

### 匹配流程

1. **语义理解**: 充分理解工作内容（名称、规格、型号）
2. **向量搜索**: 从向量数据库检索相似定额
3. **规则兜底**: 标准化条目走规则精确匹配
4. **置信度评估**: 高/中/低/待人工确认

### 规则匹配（兜底）

`local_matcher.py` 中的 `MATERIAL_QUOTA_MAP` 用于：
- 标准化条目精确匹配（已知映射）
- 电力电缆按最大单芯截面选择定额
- 控制电缆按芯数选择定额
- 钢管按 DN 规格精确匹配

### 语义搜索（主渠道）

`vector_store.py` 用于：
- 语义相似度计算
- 模糊/非标准表述匹配
- 跨表述变体识别

---

## 关键文件说明

| 文件 | 职责 | 关键类/函数 |
|------|------|-------------|
| `quota_matcher.py` | 主入口，CLI | `QuotaMatcher.process()` |
| `quota_loader.py` | 加载定额文件 | `QuotaLoader.load()` |
| `local_matcher.py` | 规则匹配 | `LocalMatcher.match()`, `MATERIAL_QUOTA_MAP` |
| `vector_store.py` | 向量存储搜索 | `VectorStore.search()`, `build_index()` |
| `file_parser.py` | 文件解析 | `FileParser.parse()`, `ExcelParser`, `WordParser` |
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

## 扩展计划

### 短期
- [x] 完善 README 和 CLAUDE.md
- [x] 构建向量数据库（已完成，16881 条定额，db/chroma_data + db/quota.db）
- [ ] 优化通用匹配规则

### 中期
- [ ] 支持 PDF 格式解析
- [ ] 丰富 MATERIAL_QUOTA_MAP
- [ ] 完善单位换算规则

### 长期
- [ ] 支持其他省份定额
- [ ] 批量处理多份清单
- [ ] 预算审核辅助

---

## 参考资料

- [河南省2016安装工程预算定额](db/河南省通用安装工程预算定额2016.txt)
- [广联达服务新干线](https://www.fwxgx.com/) - 定额详情参考网站
- [广联达预算软件](https://www.glodon.com/)
- [工程样板（广联达输出格式）](规则样板/3万吨年CHDM(1,4-环己烷二甲醇)项目/) - 电气/电信预算表，含定额编号示例
