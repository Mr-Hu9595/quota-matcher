# 工程量识别模块 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现工程量清单智能识别模块，支持有附表按附表提取、无附表时规则+AI混合解析描述语义

**Architecture:**
- 新增 `quantity_extractor.py` 模块，包含3个主类：`QuantityExtractor`（协调者）、`StructuredTableExtractor`（附表提取）、`DescriptiveExtractor`（描述提取）
- 复用现有 `file_parser.py` 的解析能力和 `minimax_matcher.py` 的AI调用能力
- 在 `quota_matcher.py` 的 `process()` 方法中集成工程量识别流程

**Tech Stack:** Python 3.11, regex, MiniMax API

---

## File Structure

```
skills/quota-matcher/
├── quantity_extractor.py    # 新增：工程量提取主模块
├── tests/
│   └── test_quantity_extractor.py  # 新增：测试文件
├── file_parser.py           # 修改：复用表格解析能力
├── quota_matcher.py         # 修改：集成工程量识别
└── minimax_matcher.py       # 复用：AI调用能力
```

---

## Task 1: 创建 quantity_extractor.py 基础框架

**Files:**
- Create: `skills/quota-matcher/quantity_extractor.py`
- Test: `skills/quota-matcher/tests/test_quantity_extractor.py`

- [ ] **Step 1: 创建测试文件**

```python
# skills/quota-matcher/tests/test_quantity_extractor.py
import pytest
from quantity_extractor import QuantityExtractor, StructuredTableExtractor, DescriptiveExtractor

class TestQuantityExtractor:
    """QuantityExtractor主入口测试"""

    def test_extract_with_table_source(self):
        """有附表来源的数据应该标记source='table'"""
        items = [
            {"name": "热镀锌钢管 DN80", "quantity": 100, "unit": "米", "source": "table", "spec": "DN80", "confidence": "high"}
        ]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        assert len(result) == 1
        assert result[0]["source"] == "table"

    def test_extract_without_table_source(self):
        """无附表来源的数据应该使用DescriptiveExtractor处理"""
        items = [
            {"name": "电力电缆 YJV-4×240+1×120", "quantity": 500, "unit": "米"}
        ]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        # 规则解析应该能匹配电缆描述
        assert len(result) >= 1

    def test_enhance_item_fields(self):
        """每条记录应该包含增强字段：spec, source, confidence, extraction_note"""
        items = [{"name": "测试项目", "quantity": 10, "unit": "个"}]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        item = result[0]
        assert "spec" in item
        assert "source" in item
        assert "confidence" in item
        assert "extraction_note" in item


class TestStructuredTableExtractor:
    """StructuredTableExtractor附表提取测试"""

    def test_extract_pipe_spec_and_quantity(self):
        """穿线管：提取规格和数量"""
        data = {"spec": "DN80", "quantity": 100, "unit": "米"}
        extractor = StructuredTableExtractor()
        result = extractor.extract(data)
        assert result["name"] == "热镀锌钢管 DN80"
        assert result["quantity"] == 100
        assert result["source"] == "table"

    def test_extract_junction_box(self):
        """接线盒：提取型号和数量"""
        data = {"name": "防爆接线盒", "quantity": 20, "unit": "个"}
        extractor = StructuredTableExtractor()
        result = extractor.extract(data)
        assert result["name"] == "防爆接线盒"
        assert result["source"] == "table"


class TestDescriptiveExtractor:
    """DescriptiveExtractor描述提取测试"""

    def test_rule_cable_pattern(self):
        """电缆描述规则匹配"""
        text = "电力电缆 YJV-4×240+1×120 共计500米"
        extractor = DescriptiveExtractor()
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "YJV" in item["name"]
        assert item["quantity"] == 500

    def test_rule_pole_pattern(self):
        """立柱描述规则匹配"""
        text = "3.5米摄像头立柱 10套"
        extractor = DescriptiveExtractor()
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "3.5米" in item["name"]

    def test_expression_parsing(self):
        """表达式解析：1+2、≈3.5、约100"""
        extractor = DescriptiveExtractor()
        assert extractor._parse_quantity("1+2") == 3.0
        assert extractor._parse_quantity("≈3.5") == 3.5
        assert extractor._parse_quantity("约100") == 100.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /d/claude\ code && python -m pytest skills/quota-matcher/tests/test_quantity_extractor.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 创建基础框架**

```python
# skills/quota-matcher/quantity_extractor.py
"""
工程量智能识别模块
功能：有附表按附表提取工程量，无附表时规则+AI混合解析描述语义
"""

import re
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class QuantityExtractor:
    """工程量提取主入口"""

    def __init__(self):
        self.table_extractor = StructuredTableExtractor()
        self.descriptive_extractor = DescriptiveExtractor()

    def extract(self, items: List[Dict]) -> List[Dict]:
        """
        提取工程量信息

        Args:
            items: 原始清单项目列表，每项包含 name, quantity, unit

        Returns:
            List[Dict]: 增强后的项目列表
        """
        results = []

        for item in items:
            source = item.get("source", "")

            if source == "table":
                # 有附表来源，使用StructuredTableExtractor
                enhanced = self.table_extractor.extract(item)
            else:
                # 无附表来源，使用DescriptiveExtractor处理描述
                enhanced = self.descriptive_extractor.extract(item)

            results.append(enhanced)

        return results


class StructuredTableExtractor:
    """从附表明细表提取工程量"""

    def extract(self, data: Dict) -> Dict:
        """
        从附表数据提取工程量

        Args:
            data: 原始数据，包含name, quantity, unit等

        Returns:
            Dict: 增强后的数据
        """
        name = data.get("name", "")
        quantity = data.get("quantity", 0)
        unit = data.get("unit", "项")

        # 提取规格
        spec = self._extract_spec(name)

        return {
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "spec": spec,
            "source": "table",
            "confidence": "high",
            "extraction_note": "从附表明细提取"
        }

    def _extract_spec(self, name: str) -> str:
        """从名称中提取规格型号"""
        # 常见的规格模式
        patterns = [
            r'(DN\d+)',           # DN80
            r'(\d+×\d+[\+\d]*)',  # 4×240+1×120
            r'(YJV[^-]+)',        # YJV-4×240
            r'(\d+mm²)',          # 4mm²
            r'(∠\d+[*×\d]+)',    # ∠40*40*4
        ]

        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)

        return ""


class DescriptiveExtractor:
    """从描述文字智能解析工程量（规则+AI混合）"""

    def __init__(self):
        self.api_key = None  # 延迟初始化
        self._patterns = self._init_patterns()

    def _init_patterns(self) -> List[Dict]:
        """初始化正则表达式模式库"""
        return [
            # 电力电缆：YJV-4×240+1×120 500米
            {
                "pattern": r'(YJV[^-]*[-]?\d+×\d+[\+\d]*)\s*(?:共计|共|合计)?\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "电力电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 控制电缆：KJV-10×1.5 200米
            {
                "pattern": r'(KJV[^-]*[-]?\d+×\d+[\+\d]*)\s*(?:共计|共|合计)?\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "控制电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 接地跨接线：4mm²接地跨接黄绿双色线 100米
            {
                "pattern": r'(\d+mm²)\s*接地跨接.*?(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "{spec}接地跨接黄绿双色线",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 钢管：DN80热镀锌钢管 150米
            {
                "pattern": r'(DN\d+)\s*热镀锌钢管\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌钢管 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 槽钢：10#热镀锌槽钢 50米
            {
                "pattern": r'(10#)\s*热镀锌槽钢\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌槽钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 角钢：∠40*40*4热镀锌角钢 30米
            {
                "pattern": r'(∠\d+[*×\d]+)\s*热镀锌角钢\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌角钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 摄像头立柱：3.5米摄像头立柱 10套
            {
                "pattern": r'(\d+\.?\d*)\s*米\s*摄像头立柱\s*(\d+(?:\.\d+)?)\s*(套|个|台)',
                "name_template": "摄像头立柱 高度{height}米",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2,
                "height_capture": True
            },
        ]

    def extract(self, item: Dict) -> Dict:
        """
        从清单项目提取工程量

        Args:
            item: 原始数据，包含name, quantity, unit

        Returns:
            Dict: 增强后的数据
        """
        name = item.get("name", "")
        quantity = item.get("quantity")
        unit = item.get("unit", "项")

        # 尝试用规则解析
        rule_result = self._try_rule_pattern(name)

        if rule_result:
            rule_result["source"] = "rule"
            rule_result["extraction_note"] = "规则匹配提取"
            return rule_result

        # 规则无法解析，返回原始数据并标记low confidence
        return {
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "spec": "",
            "source": "unparsed",
            "confidence": "low",
            "extraction_note": "规则无法解析，需人工确认"
        }

    def extract_from_text(self, text: str) -> List[Dict]:
        """
        从描述文字提取工程量

        Args:
            text: 描述文字

        Returns:
            List[Dict]: 提取的工程量列表
        """
        results = []

        for pattern_def in self._patterns:
            match = re.search(pattern_def["pattern"], text)
            if match:
                spec = match.group(pattern_def["spec_group"])
                qty = float(match.group(pattern_def["qty_group"]))
                unit = pattern_def["unit"]

                # 特殊处理立柱高度
                name = pattern_def["name_template"]
                if pattern_def.get("height_capture"):
                    name = name.format(height=spec)
                else:
                    name = name.format(spec=spec)

                results.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "spec": spec,
                    "source": "rule",
                    "confidence": "high",
                    "extraction_note": "规则精确匹配"
                })

        return results

    def _try_rule_pattern(self, name: str) -> Optional[Dict]:
        """尝试用规则模式匹配"""
        for pattern_def in self._patterns:
            match = re.search(pattern_def["pattern"], name)
            if match:
                spec = match.group(pattern_def["spec_group"])
                qty = match.group(pattern_def["qty_group"])
                unit = pattern_def["unit"]

                name_template = pattern_def["name_template"]
                if pattern_def.get("height_capture"):
                    item_name = name_template.format(height=spec)
                else:
                    item_name = name_template.format(spec=spec)

                return {
                    "name": item_name,
                    "quantity": float(qty),
                    "unit": unit,
                    "spec": spec,
                    "confidence": "high"
                }

        return None

    def _parse_quantity(self, qty_text: str) -> Optional[float]:
        """
        解析数量表达式

        Args:
            qty_text: 数量文本，如 "1+2"、"≈3.5"、"约100"

        Returns:
            float: 解析后的数值
        """
        # 清理文本
        clean = qty_text.replace("≈", "").replace("约", "").replace(" ", "").strip()

        try:
            return float(clean)
        except ValueError:
            # 尝试解析表达式
            if "+" in clean:
                parts = clean.split("+")
                try:
                    return sum(float(p) for p in parts)
                except ValueError:
                    pass

        return None
```

- [ ] **Step 4: 运行测试确认基础框架通过**

Run: `cd /d/claude\ code && python -m pytest skills/quota-matcher/tests/test_quantity_extractor.py::TestDescriptiveExtractor::test_expression_parsing -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
cd /d/claude\ code && git add skills/quota-matcher/quantity_extractor.py skills/quota-matcher/tests/test_quantity_extractor.py && git commit -m "$(cat <<'EOF'
feat: 添加工程量识别模块基础框架

- QuantityExtractor: 主入口，协调附表/描述两种处理方式
- StructuredTableExtractor: 从附表明细提取工程量
- DescriptiveExtractor: 规则解析 + AI兜底

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: 扩展规则模式库

**Files:**
- Modify: `skills/quota-matcher/quantity_extractor.py`

- [ ] **Step 1: 添加更多规则模式和测试**

```python
# 在TestDescriptiveExtractor类中添加

def test_rule_pipe_pattern(self):
    """钢管描述规则匹配"""
    extractor = DescriptiveExtractor()
    text = "DN80热镀锌钢管 150米"
    result = extractor.extract_from_text(text)
    assert len(result) >= 1
    item = result[0]
    assert "DN80" in item["name"]
    assert item["quantity"] == 150

def test_rule_steel_angle_pattern(self):
    """角钢描述规则匹配"""
    extractor = DescriptiveExtractor()
    text = "∠40*40*4热镀锌角钢 30米"
    result = extractor.extract_from_text(text)
    assert len(result) >= 1
    item = result[0]
    assert "∠40" in item["name"]

def test_rule_steel_channel_pattern(self):
    """槽钢描述规则匹配"""
    extractor = DescriptiveExtractor()
    text = "10#热镀锌槽钢 50米"
    result = extractor.extract_from_text(text)
    assert len(result) >= 1
    item = result[0]
    assert "10#" in item["name"]
```

- [ ] **Step 2: 运行测试**

Run: `cd /d/claude\ code && python -m pytest skills/quota-matcher/tests/test_quantity_extractor.py::TestDescriptiveExtractor -v`
Expected: 新测试应该通过

- [ ] **Step 3: 扩展规则模式库**

在 `_init_patterns` 方法中添加更多模式：

```python
# 添加以下模式定义到patterns列表中

# 防爆接线盒
{
    "pattern": r'防爆接线盒\s*(\d+(?:\.\d+)?)\s*(个)',
    "name_template": "防爆接线盒",
    "unit": "个",
    "spec_group": 1,
    "qty_group": 1
},
# 三防接线盒
{
    "pattern": r'三防接线盒\s*(\d+(?:\.\d+)?)\s*(个)',
    "name_template": "三防接线盒",
    "unit": "个",
    "spec_group": 1,
    "qty_group": 1
},
# 防爆活接头
{
    "pattern": r'防爆活接头\s*(\d+(?:\.\d+)?)\s*(个)',
    "name_template": "防爆活接头",
    "unit": "个",
    "spec_group": 1,
    "qty_group": 1
},
# 钢板
{
    "pattern": r'(\d+[*×\d]+\s*mm)\s*钢板\s*(\d+(?:\.\d+)?)\s*(块|吨)',
    "name_template": "钢板 {spec}",
    "unit": "块",
    "spec_group": 1,
    "qty_group": 2
},
```

- [ ] **Step 4: 验证新模式**

Run: `cd /d/claude\ code && python -c "
from quantity_extractor import DescriptiveExtractor
extractor = DescriptiveExtractor()

# 测试防爆接线盒
text = '防爆接线盒 20个'
result = extractor.extract_from_text(text)
print(f'防爆接线盒: {result}')

# 测试钢板
text = '200*200*8mm钢板 15块'
result = extractor.extract_from_text(text)
print(f'钢板: {result}')
"`
Expected: 正确提取工程量

- [ ] **Step 5: 提交**

```bash
git add skills/quota-matcher/quantity_extractor.py && git commit -m "$(cat <<'EOF'
feat: 扩展工程量提取规则模式库

新增模式：
- 防爆/三防接线盒
- 防爆活接头
- 钢板

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: 集成AI语义解析（兜底）

**Files:**
- Modify: `skills/quota-matcher/quantity_extractor.py`

- [ ] **Step 1: 添加AISemanticParser类**

```python
class AISemanticParser:
    """AI语义解析器（规则无法匹配时的兜底）"""

    API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    SYSTEM_PROMPT = """你是一位资深预算工程师，精通工程量清单解析。

任务：从工程描述中提取工程量信息。

输入格式：工程描述文本
输出格式：JSON数组

```json
{
  "items": [
    {
      "name": "项目名称（需包含规格型号）",
      "quantity": 数值,
      "unit": "单位",
      "spec": "规格型号（如有）",
      "extraction_note": "提取说明"
    }
  ]
}
```

规则：
- 只提取有明确数量描述的项目
- quantity只返回数字
- 无法提取时返回空数组"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")

    def parse(self, text: str) -> List[Dict]:
        """
        使用AI解析描述文本

        Args:
            text: 描述文本

        Returns:
            List[Dict]: 提取的工程量列表
        """
        if not self.api_key:
            return []

        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "MiniMax-M2",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"从以下描述中提取工程量：{text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 512
        }

        try:
            response = requests.post(self.API_URL, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_response(content)
        except Exception as e:
            print(f"AI解析失败: {e}")

        return []

    def _parse_response(self, content: str) -> List[Dict]:
        """解析AI响应"""
        import json
        try:
            data = json.loads(content)
            return data.get("items", [])
        except:
            # 尝试提取JSON
            match = re.search(r'\[[^\]]+\]', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return []
```

- [ ] **Step 2: 在DescriptiveExtractor中集成AI调用**

修改 `DescriptiveExtractor.__init__` 添加ai_parser延迟初始化：

```python
def __init__(self, api_key: str = None):
    self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
    self._patterns = self._init_patterns()
    self._ai_parser = None

@property
def ai_parser(self):
    if self._ai_parser is None and self.api_key:
        self._ai_parser = AISemanticParser(self.api_key)
    return self._ai_parser
```

修改 `extract` 方法添加AI兜底：

```python
def extract(self, item: Dict) -> Dict:
    name = item.get("name", "")
    quantity = item.get("quantity")
    unit = item.get("unit", "项")

    # 尝试用规则解析
    rule_result = self._try_rule_pattern(name)

    if rule_result:
        rule_result["source"] = "rule"
        rule_result["extraction_note"] = "规则匹配提取"
        return rule_result

    # 规则无法解析，尝试AI解析
    if self.ai_parser:
        ai_results = self.ai_parser.parse(name)
        if ai_results:
            result = ai_results[0]
            result["source"] = "ai"
            result["confidence"] = "medium"
            result["extraction_note"] = "AI语义解析"
            return result

    # 无法解析，返回原始数据并标记low confidence
    return {
        "name": name,
        "quantity": quantity,
        "unit": unit,
        "spec": "",
        "source": "unparsed",
        "confidence": "low",
        "extraction_note": "无法解析，需人工确认"
    }
```

- [ ] **Step 3: 提交**

```bash
git add skills/quota-matcher/quantity_extractor.py && git commit -m "$(cat <<'EOF'
feat: 集成AI语义解析作为规则兜底

当规则无法匹配时，自动调用AI进行语义解析提取工程量

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: 集成到quota_matcher.py主流程

**Files:**
- Modify: `skills/quota-matcher/quota_matcher.py`

- [ ] **Step 1: 添加导入和初始化**

在文件开头添加：
```python
from quantity_extractor import QuantityExtractor
```

修改 `QuotaMatcher.__init__`：
```python
def __init__(self, use_local: bool = False, use_vector: bool = False):
    # ... existing init code ...
    self.quantity_extractor = QuantityExtractor()
```

- [ ] **Step 2: 在process方法中集成工程量识别**

找到解析完成后的位置（约第98-106行），在 `print(f"解析到 {len(parse_result.items)} 个工程量项目")` 后添加：

```python
# 2.5 工程量识别（新增）
print("\n[2.5/5] 正在识别工程量...")
for item in parse_result.items:
    # 设置默认source（如果来自附表会由StructuredTableExtractor处理）
    if "source" not in item:
        item["source"] = item.get("sheet", "")  # sheet包含"附表"则source为table

enhanced_items = self.quantity_extractor.extract(parse_result.items)
print(f"工程量识别完成，{len(enhanced_items)} 项")

# 3. AI匹配（使用增强后的数据）
print("\n[3/5] 正在AI匹配定额（此过程需要联网）...")
results = self.matcher.batch_match(enhanced_items)
```

同时更新后续步骤的编号（[3/4] → [4/5]，[4/4] → [5/5]）

- [ ] **Step 3: 运行测试验证集成**

使用实际清单文件测试：
```bash
cd /d/claude\ code
python -c "
import sys
sys.path.insert(0, 'skills/quota-matcher')
from quota_matcher import QuotaMatcher
# 测试导入是否成功
print('QuotaMatcher with QuantityExtractor imported successfully')
"
```

- [ ] **Step 4: 提交**

```bash
git add skills/quota-matcher/quota_matcher.py && git commit -m "$(cat <<'EOF'
feat: 集成工程量识别到主流程

在解析完成后、定额匹配前，增加工程量识别步骤

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: 输出字段增强验证

**Files:**
- Test: 使用实际清单文件验证

- [ ] **Step 1: 验证增强字段输出**

修改 `_write_output` 方法以使用新的增强字段：
- 添加 `spec` 列（如输出Excel需要）
- `source` 用于日志/备注
- `confidence` 用于标注解析质量

Run: `cd /d/claude\ code && python -c "
import sys
sys.path.insert(0, 'skills/quota-matcher')
from file_parser import FileParser
from quantity_extractor import QuantityExtractor

# 找一个测试文件
import glob
files = glob.glob('projects/**/*.xlsx', recursive=True)
if files:
    parser = FileParser()
    result = parser.parse(files[0])
    print(f'解析到 {len(result.items)} 项')
    
    extractor = QuantityExtractor()
    enhanced = extractor.extract(result.items)
    
    if enhanced:
        item = enhanced[0]
        print(f'增强字段验证:')
        print(f'  spec: {item.get(\"spec\", \"N/A\")}')
        print(f'  source: {item.get(\"source\", \"N/A\")}')
        print(f'  confidence: {item.get(\"confidence\", \"N/A\")}')
        print(f'  extraction_note: {item.get(\"extraction_note\", \"N/A\")}')
"
```

- [ ] **Step 2: 提交**

```bash
git commit -m "$(cat <<'EOF'
test: 验证工程量识别模块输出字段

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Verification Checklist

- [ ] 所有测试通过：`pytest skills/quota-matcher/tests/test_quantity_extractor.py -v`
- [ ] 规则模式覆盖常见工程量描述
- [ ] AI兜底在规则无法匹配时正常调用
- [ ] 集成到主流程后原有功能不受影响
- [ ] 增强字段（spec, source, confidence, extraction_note）正确输出