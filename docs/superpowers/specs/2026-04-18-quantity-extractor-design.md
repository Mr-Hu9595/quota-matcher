# 工程量清单识别模块设计

**日期**: 2026-04-18
**项目**: quota-matcher (工程量清单匹配河南省2016定额)

---

## 1. 概述

目标：在现有工程量清单解析基础上，增强**工程量识别**能力。对于有明确附表的情况按附表提取；对于没有附表只有描述的情况，通过规则+AI混合方式理解描述语义并提取工程量。

---

## 2. 模块结构

### 2.1 新增文件

**`quantity_extractor.py`** - 工程量提取主模块

| 类 | 职责 |
|---|---|
| `QuantityExtractor` | 主入口，协调附表提取和描述提取两种方式 |
| `StructuredTableExtractor` | 从Word/Excel附表明细表提取工程量 |
| `DescriptiveExtractor` | 从描述文字智能解析工程量（规则+AI混合） |

### 2.2 现有文件改动

| 文件 | 改动 |
|---|---|
| `file_parser.py` | 复用其表格解析能力 |
| `quota_matcher.py` | 在解析后、定额匹配前，调用 `QuantityExtractor` 识别工程量 |

---

## 3. 数据流

```
file_parser.parse()
    ↓
ParseResult (items: [{name, quantity, unit}])
    ↓
QuantityExtractor.extract()
    ├─ 有附表 → StructuredTableExtractor
    └─ 无附表 → DescriptiveExtractor (规则优先，AI兜底)
    ↓
EnhancedParseResult (items: [{name, quantity, unit, spec, source, confidence}])
    ↓
matcher.batch_match()  ← 现有流程不变
    ↓
QuotaMatchResult → Excel输出
```

---

## 4. StructuredTableExtractor（附表提取）

### 4.1 输入来源

| 来源 | 格式 | 处理方法 |
|---|---|---|
| Word附表1 | 穿线管和跨接线明细 | `_parse_table_pipe` |
| Word附表2 | 接线盒及活接头明细 | `_parse_table_junction_box` |
| Word附表3 | 槽钢、角钢明细 | `_parse_table_steel` |
| Word附表4 | 监控立柱明细 | `_parse_table_pole` |
| Excel标准表格 | 表一~表四格式 | `ColumnIdentifier` 识别 |

### 4.2 提取内容

- **穿线管**: 规格 + 穿线管数量
- **跨接线**: 4mm²接地跨接黄绿双色线 数量
- **接线盒/活接头**: 型号 + 数量
- **槽钢/角钢**: 材质 + 长度
- **监控立柱**: 安装高度 + 材质 + 数量

---

## 5. DescriptiveExtractor（描述提取）

### 5.1 规则层（RuleBasedParser）

使用正则表达式匹配标准工程描述格式：

| 模式类型 | 正则示例 | 提取内容 |
|---|---|---|
| 电力电缆 | `YJV-4×240\+1×120\s*(\d+)\s*米` | 规格型号 + 长度 |
| 控制电缆 | `KJV-10×1.5\s*(\d+)\s*米` | 芯数×截面积 + 长度 |
| 接地线 | `4mm²接地跨接.*?(\d+)\s*米` | 截面积 + 长度 |
| 钢管 | `DN80\s*热镀锌钢管\s*(\d+)\s*米` | 规格 + 长度 |
| 角钢/槽钢 | `10#.*?(\d+)\s*米` | 型号 + 长度 |
| 摄像头立柱 | `(\d+\.?\d*)米\s*摄像头立柱\s*(\d+)\s*个` | 高度 + 数量 |

### 5.2 AI层（AISemanticParser）

**触发条件**: 规则无法匹配时

**Prompt模板**:
```
从以下工程描述中提取工程量信息，返回JSON格式数组：

描述：{原文}

要求：
- name: 项目名称（需包含规格型号）
- quantity: 数值（只返回数字）
- unit: 单位
- spec: 规格型号（如有）
- extraction_note: 简要说明提取依据
```

**返回格式**:
```json
{
  "items": [
    {
      "name": "电力电缆 YJV-4×240+1×120",
      "quantity": 500,
      "unit": "米",
      "spec": "4×240+1×120",
      "extraction_note": "从描述'YJV-4×240+1×120 共计500米'提取"
    }
  ]
}
```

---

## 6. 输出增强

每条工程量记录增加以下字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `spec` | str | 规格型号（从描述解析得出） |
| `source` | str | 数据来源：`excel`/`table`/`word_reason`/`ai` |
| `confidence` | str | 解析置信度：`high`/`medium`/`low` |
| `extraction_note` | str | 提取说明 |

### 置信度判定

| 置信度 | 条件 |
|---|---|
| `high` | 附表提取 / 规则精确匹配 |
| `medium` | 规则模糊匹配 |
| `low` | AI解析 / 无法解析需要人工确认 |

---

## 7. 错误处理

| 场景 | 处理方式 |
|---|---|
| 无法解析的描述 | 标记 `confidence='low'`，原样输出，让人工确认 |
| AI调用失败 | 回退到规则层，规则也无法处理则标记待确认 |
| 附表格式识别失败 | 回退到通用表格解析 |

---

## 8. 实现计划

### Phase 1: 基础框架
- [x] 创建 `quantity_extractor.py` 模块
- [x] 实现 `QuantityExtractor` 主入口
- [x] 实现 `StructuredTableExtractor` 复用现有WordParser逻辑

### Phase 2: 规则解析
- [ ] 实现 `DescriptiveExtractor` 规则层
- [ ] 定义常用正则表达式模式库
- [ ] 支持表达式解析（`1+2`、`≈3.5`）

### Phase 3: AI集成
- [ ] 实现 `AISemanticParser`
- [ ] 集成到MiniMax API
- [ ] 规则无法匹配时调用AI

### Phase 4: 流程整合
- [ ] 在 `quota_matcher.py` 中集成工程量识别
- [ ] 测试完整流程
- [ ] 输出结果验证

---

## 9. 测试验证

以实际清单文件验证：
- Excel标准格式：提取正确性
- Word附表格式：提取完整性
- 描述性文字：规则覆盖率和AI兜底效果
