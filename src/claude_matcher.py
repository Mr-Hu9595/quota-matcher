"""
AI语义匹配模块
功能：调用Claude API进行定额语义匹配，支持联网搜索理解工作内容
"""

import os
import json
from typing import List, Dict, Optional
from pathlib import Path

try:
    from anthropic import Anthropic, APIError
except ImportError:
    Anthropic = None
    APIError = None

from unit_converter import UnitConverter


class ClaudeMatcher:
    """Claude AI语义匹配器"""

    SYSTEM_PROMPT = """你是一位资深预算工程师，精通河南省2016安装工程预算定额。

你需要根据工程清单项目名称，从给定的定额列表中选择最匹配的一项。

分析步骤：
1. 理解清单项目的工作内容，必要时联网搜索具体施工工艺和定额子目
2. 识别隐含工作内容（如除锈、刷漆、防腐、保温等）
3. 判断清单单位与定额单位是否一致
4. 如需单位转换（如钢材米→kg），在备注中说明

返回格式（JSON）：
{
    "code": "定额编号",
    "name": "定额项目名称",
    "unit": "定额单位",
    "confidence": "high/medium/low",
    "note": "备注说明（如单位转换、匹配理由等）",
    "need_confirm": true/false
}

重要规则：
1. 必须返回一个最可能的定额，即使不确定也要猜测
2. 如果匹配不确定（confidence为medium或low），设置need_confirm为true
3. code必须是在给定定额列表中存在的编号
4. 如果无法匹配，返回code为空，need_confirm为true"""

    def __init__(self, quota_data: List[Dict], api_key: str = None):
        """
        初始化AI匹配器

        Args:
            quota_data: 定额数据库
            api_key: Claude API密钥，默认从环境变量读取
        """
        if Anthropic is None:
            raise ImportError("请安装 anthropic: pip install anthropic")

        self.quota_data = quota_data
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

        # 将定额数据按章节分组，便于查找
        self.quotas_by_chapter = self._group_by_chapter()
        self.all_codes = [q["code"] for q in quota_data]

    def _group_by_chapter(self) -> Dict[str, List[Dict]]:
        """按章节分组定额"""
        chapters = {}
        for q in self.quota_data:
            chapter = q.get("chapter", "未分类")
            if chapter not in chapters:
                chapters[chapter] = []
            chapters[chapter].append(q)
        return chapters

    def match(self, item_name: str, quantity: float = None, unit: str = None) -> Dict:
        """
        匹配单个清单项目

        Args:
            item_name: 清单项目名称
            quantity: 工程量（可选）
            unit: 单位（可选）

        Returns:
            Dict: 匹配结果 {
                "code": "定额编号",
                "name": "定额项目名称",
                "unit": "定额单位",
                "confidence": "high/medium/low",
                "note": "备注",
                "need_confirm": true/false
            }
        """
        # 检查是否需要单位转换
        if unit and UnitConverter.needs_conversion(item_name, unit):
            converted_qty, new_unit, note = UnitConverter.convert(item_name, quantity, unit)
            unit_note = f"单位转换: {quantity}{unit} → {converted_qty}{new_unit}, {note}"
        else:
            converted_qty = quantity
            new_unit = unit
            unit_note = ""

        # 构建提示词
        prompt = self._build_prompt(item_name, converted_qty, new_unit)

        try:
            response = self._call_claude(prompt)
            result = self._parse_response(response)

            # 添加单位转换备注
            if unit_note and result.get("note"):
                result["note"] = f"{unit_note}; {result['note']}"
            elif unit_note:
                result["note"] = unit_note

            # 检查匹配不确定时，添加待人工确认标注到项目名称
            if result.get("need_confirm"):
                original_name = result.get("name", item_name)
                if "（待人工确认）" not in original_name:
                    result["name"] = f"{original_name}（待人工确认）"

            return result

        except Exception as e:
            # API调用失败时返回错误状态
            return {
                "code": "",
                "name": f"{item_name}（待人工确认）",
                "unit": unit or "",
                "confidence": "low",
                "note": f"AI匹配失败: {str(e)}",
                "need_confirm": True
            }

    def batch_match(self, items: List[Dict], batch_size: int = 5) -> List[Dict]:
        """
        批量匹配清单项目

        Args:
            items: 清单项目列表，每项包含 name, quantity, unit
            batch_size: 每批处理数量

        Returns:
            List[Dict]: 匹配结果列表
        """
        results = []

        for i, item in enumerate(items):
            print(f"正在匹配 [{i+1}/{len(items)}]: {item.get('name', '')[:30]}...")

            result = self.match(
                item_name=item.get("name", ""),
                quantity=item.get("quantity"),
                unit=item.get("unit")
            )

            # 保留原始数据
            result["original_name"] = item.get("name")
            result["original_quantity"] = item.get("quantity")
            result["original_unit"] = item.get("unit")

            results.append(result)

        return results

    def _build_prompt(self, item_name: str, quantity: float, unit: str) -> str:
        """构建提示词"""
        prompt = f"""工程清单项目：{item_name}
工程量：{quantity} {unit if unit else "项"}

请从以下定额列表中选择最匹配的一项（必须使用列表中的定额编号）：

"""

        # 添加定额列表（按相关性添加，可能需要先过滤）
        # 为了减少token，只添加相关的定额
        relevant_quotas = self._find_relevant_quotas(item_name)

        for q in relevant_quotas[:50]:  # 限制数量
            prompt += f"- {q['code']}: {q['name']} ({q['unit']})\n"

        prompt += "\n请返回JSON格式的匹配结果。"

        return prompt

    def _find_relevant_quotas(self, item_name: str) -> List[Dict]:
        """
        查找相关的定额

        Args:
            item_name: 项目名称

        Returns:
            List[Dict]: 相关定额列表
        """
        # 简单的关键词匹配来过滤
        keywords = self._extract_keywords(item_name)

        if not keywords:
            return self.quota_data[:100]  # 返回前100条作为参考

        relevant = []
        item_lower = item_name.lower()

        for q in self.quota_data:
            name_lower = q["name"].lower()
            # 检查是否有共同关键词
            if any(kw in name_lower for kw in keywords):
                relevant.append(q)

        # 如果找到相关定额，返回它们
        if relevant:
            return relevant

        # 否则返回包含相同词的定额
        for q in self.quota_data:
            name_lower = q["name"].lower()
            if any(kw in item_lower for kw in keywords if len(kw) > 1):
                relevant.append(q)

        return relevant[:100] if relevant else self.quota_data[:100]

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 去除常见词
        stopwords = ["安装", "制作", "施工", "设备", "材料", "共计", "含", "等", "规格"]
        text = text.lower()

        # 提取长度>=2的词组
        words = []
        for sw in stopwords:
            text = text.replace(sw, "")

        # 简单分词（按空格和特殊字符）
        import re
        tokens = re.split(r'[\s,，、*×().]+', text)
        words = [t for t in tokens if len(t) >= 2]

        return words

    def _call_claude(self, prompt: str) -> str:
        """调用Claude API"""
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            tools=[{"name": "web_search", "type": "search"}]
        )

        return response.content[0].text

    def _parse_response(self, response_text: str) -> Dict:
        """解析API响应"""
        try:
            # 尝试提取JSON
            import re

            # 查找JSON块
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
            else:
                # 尝试直接解析
                result = json.loads(response_text)

            # 验证必需字段
            if "code" not in result:
                result["code"] = ""

            return result

        except json.JSONDecodeError as e:
            # 解析失败，尝试从文本中提取
            return self._fallback_parse(response_text)

    def _fallback_parse(self, text: str) -> Dict:
        """从非JSON格式的文本中解析"""
        import re

        # 尝试匹配 "编号: xxx" 或 "code: xxx" 格式
        code_match = re.search(r'编号[：:]\s*(\d+-\d+-\d+)', text)
        name_match = re.search(r'名称[：:]\s*(.+?)(?:\n|$)', text)
        unit_match = re.search(r'单位[：:]\s*(\S+)', text)

        result = {
            "code": code_match.group(1) if code_match else "",
            "name": name_match.group(1).strip() if name_match else "",
            "unit": unit_match.group(1) if unit_match else "",
            "confidence": "low",
            "note": "AI响应格式异常，请人工确认",
            "need_confirm": True
        }

        return result


if __name__ == "__main__":
    # 测试代码（需要设置ANTHROPIC_API_KEY环境变量）
    # 测试时使用模拟数据

    test_quotas = [
        {"code": "1-1-1", "name": "台式及仪表机床 设备重量0.3t以内", "unit": "台", "price": 518.97},
        {"code": "1-1-2", "name": "台式及仪表机床 设备重量0.7t以内", "unit": "台", "price": 988.28},
        {"code": "1-2-1", "name": "车床安装 设备重量2.0t以内", "unit": "台", "price": 2333.47},
    ]

    print("ClaudeMatcher 已初始化（测试需要API密钥）")
    print(f"示例定额数量: {len(test_quotas)}")
