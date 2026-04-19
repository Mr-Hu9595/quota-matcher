"""
MiniMax AI API 匹配模块
功能：调用MiniMax API进行定额语义匹配，支持联网搜索理解工作内容
"""

import os
import json
import requests
from typing import List, Dict, Optional
from pathlib import Path

from unit_converter import UnitConverter


class MiniMaxMatcher:
    """MiniMax AI语义匹配器"""

    API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    SYSTEM_PROMPT = """你是一位资深预算工程师，精通河南省2016安装工程预算定额。

任务：根据工程清单项目名称，从给定的定额列表中选择一个真实存在的定额编号。

**绝对禁止：编造、推测、创造任何不存在的定额编号！**

返回格式（JSON）：
```json
{"code": "定额编号", "name": "定额项目名称", "confidence": "high/medium/low"}
```

匹配规则：
1. 从给定列表中选择最匹配的一项
2. code必须是给定列表中存在的编号（格式：数字-数字-数字）
3. 选择整体语义最接近的，不要只看字面匹配
4. 如果给定列表中没有合适的，选择一个最接近的并在confidence中标明low

示例：
- 给定列表包含：1-1-1(台式及仪表机床)、5-1-1(监测监控设备安装)
- 清单项目：监测监控设备安装
- 正确返回：{"code": "5-1-1", "name": "监测监控设备安装", "confidence": "high"}"""

    def __init__(self, quota_data: List[Dict], api_key: str = None, vector_store=None):
        """
        初始化AI匹配器

        Args:
            quota_data: 定额数据库
            api_key: MiniMax API密钥，默认从环境变量读取
            vector_store: 向量存储模块，用于向量搜索预筛选
        """
        self.quota_data = quota_data
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        self.vector_store = vector_store

        if not self.api_key:
            raise ValueError("未设置MiniMax API密钥，请设置环境变量 MINIMAX_API_KEY")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

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
            Dict: 匹配结果
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
            result = self._call_minimax(prompt)
            result = self._parse_response(result)

            # 验证code是否存在，如果不存在但name有效，从相关定额中找一个
            if not result.get("code") or result.get("code") not in self.all_codes:
                relevant = self._find_relevant_quotas(item_name)
                if relevant:
                    # 选择第一个作为最接近的
                    fallback = relevant[0]
                    result["code"] = fallback["code"]
                    result["name"] = fallback["name"]
                    result["unit"] = fallback["unit"]
                    result["confidence"] = "low"
                    result["note"] = "AI未返回有效定额，使用最相关定额"
                    result["need_confirm"] = True

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

        # 添加定额列表（优先使用向量搜索，否则用关键词搜索）
        if self.vector_store:
            relevant_quotas = self._vector_search_relevant(item_name)
        else:
            relevant_quotas = self._find_relevant_quotas(item_name)

        for q in relevant_quotas[:50]:  # 限制数量
            prompt += f"- {q['code']}: {q['name']} ({q['unit']})\n"

        prompt += "\n请返回JSON格式的匹配结果。"

        return prompt

    def _vector_search_relevant(self, item_name: str) -> List[Dict]:
        """
        使用向量搜索查找相关定额

        Args:
            item_name: 查询文本

        Returns:
            相关定额列表
        """
        try:
            results = self.vector_store.search(item_name, top_k=80, api_key=self.api_key)
            if results:
                print(f"  向量搜索返回 {len(results)} 个候选")
                return results
        except Exception as e:
            print(f"  向量搜索失败，回退到关键词搜索: {e}")

        # 回退到关键词搜索
        return self._find_relevant_quotas(item_name)

    def _find_relevant_quotas(self, item_name: str) -> List[Dict]:
        """查找相关的定额"""
        keywords = self._extract_keywords(item_name)

        relevant = []
        item_lower = item_name.lower()

        # 更宽松的匹配策略
        import re

        for q in self.quota_data:
            name_lower = q["name"].lower()
            score = 0

            # 1. 关键词匹配
            for kw in keywords:
                if len(kw) >= 2:
                    if kw in name_lower:
                        score += 2
                    elif kw[0] in name_lower or kw[-1] in name_lower:
                        score += 0.5
                elif len(kw) == 1:
                    if kw in name_lower:
                        score += 0.3

            # 2. 数字规格匹配
            item_specs = set(re.findall(r'\d+', item_name))
            name_specs = set(re.findall(r'\d+', name_lower))
            if item_specs and name_specs:
                common = item_specs & name_specs
                if common:
                    score += len(common) * 1.0

            # 3. 包含"表"、"仪"、"控"等关键工程字符
            engineering_chars = ['表', '仪', '控', '阀', '管', '线', '电', '机', '泵', '箱']
            for char in engineering_chars:
                if char in item_lower and char in name_lower:
                    score += 0.5

            if score > 0:
                relevant.append((q, score))

        # 按分数排序
        relevant.sort(key=lambda x: x[1], reverse=True)

        # 如果相关定额少于15个，扩大搜索
        if len(relevant) < 15:
            # 找包含任何单个汉字的定额
            for q in self.quota_data:
                name_lower = q["name"].lower()
                for char in item_lower:
                    if '\u4e00' <= char <= '\u9fff' and char in name_lower and len(char) == 1:
                        relevant.append((q, 0.1))

            # 去重并重新排序
            seen = set()
            unique_relevant = []
            for q, score in relevant:
                if q['code'] not in seen:
                    seen.add(q['code'])
                    unique_relevant.append((q, score))
            unique_relevant.sort(key=lambda x: x[1], reverse=True)
            relevant = unique_relevant

        result = [q for q, score in relevant[:80]]

        # 如果相关定额仍然太少（<10），返回一些常见定额作为参考
        if len(result) < 10:
            # 返回包含"安装"的最常见定额
            count = 0
            for q in self.quota_data:
                if '安装' in q['name']:
                    result.append(q)
                    count += 1
                    if count >= 30:
                        break

        return result if result else self.quota_data[:50]

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 减少停用词，只去除最常见的无意义词
        stopwords = ["安装", "共计", "含", "等", "规格"]
        text = text.lower()

        for sw in stopwords:
            text = text.replace(sw, "")

        import re
        # 按常见分隔符分割，但保留所有有意义的内容
        tokens = re.split(r'[\s,，、*×().。、]+', text)
        # 只过滤纯单字符
        words = [t.strip() for t in tokens if len(t.strip()) >= 2]

        return words

    def _call_minimax(self, prompt: str) -> Dict:
        """调用MiniMax API"""
        # 构建请求数据
        data = {
            "model": "MiniMax-M2.7",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1024
        }

        try:
            response = requests.post(
                self.API_URL,
                headers=self.headers,
                json=data,
                timeout=120
            )

            if response.status_code != 200:
                raise Exception(f"API错误: {response.status_code} - {response.text}")

            result = response.json()
            return result

        except requests.exceptions.Timeout:
            raise Exception("API请求超时，请检查网络连接")
        except requests.exceptions.RequestException as e:
            raise Exception(f"API请求失败: {str(e)}")

    def _web_search(self, query: str) -> str:
        """执行联网搜索"""
        # MiniMax的web_search需要单独调用
        search_url = "https://api.minimax.chat/v1/search"

        search_data = {
            "model": " MiniMax-Search",
            "query": query,
            "search_result_return_length": 3
        }

        try:
            response = requests.post(
                search_url,
                headers=self.headers,
                json=search_data,
                timeout=60
            )

            if response.status_code != 200:
                return f"搜索失败: {response.status_code}"

            result = response.json()

            if "data" in result and len(result["data"]) > 0:
                search_results = []
                for item in result["data"]:
                    text = item.get("text", "")
                    search_results.append(text[:500])  # 限制长度
                return "\n\n".join(search_results)

            return "未找到搜索结果"

        except Exception as e:
            return f"搜索异常: {str(e)}"

    def _parse_response(self, result: Dict) -> Dict:
        """解析MiniMax API响应"""
        try:
            import re

            # 从MiniMax响应中提取content
            content = ""
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                message = choice.get("message", {})
                content = message.get("content", "")

            if not content:
                return {
                    "code": "",
                    "name": "",
                    "unit": "",
                    "confidence": "low",
                    "note": "AI响应为空",
                    "need_confirm": True
                }

            # 尝试解析content中的JSON
            parsed = None
            try:
                parsed = json.loads(content)
                if isinstance(parsed, dict):
                    if "code" not in parsed:
                        parsed["code"] = ""
            except json.JSONDecodeError:
                pass

            # 如果解析失败，尝试从content中提取JSON
            if parsed is None:
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    try:
                        parsed = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass

            # 验证code是否存在于定额库
            if parsed and "code" in parsed:
                code = parsed["code"]
                # 检查code格式是否正确（应该是数字-数字-数字）
                if not re.match(r'^\d+-\d+-\d+$', code):
                    parsed["code"] = ""
                    parsed["note"] = (parsed.get("note", "") + "; 定额编号格式错误").strip()
                    parsed["need_confirm"] = True
                elif code not in self.all_codes:
                    parsed["code"] = ""
                    parsed["note"] = (parsed.get("note", "") + "; 定额编号不存在于定额库").strip()
                    parsed["need_confirm"] = True
            else:
                # 无法解析JSON
                return self._fallback_parse(content)

            return parsed

        except Exception as e:
            return {
                "code": "",
                "name": "",
                "unit": "",
                "confidence": "low",
                "note": f"解析响应异常: {str(e)}",
                "need_confirm": True
            }

    def _fallback_parse(self, text: str) -> Dict:
        """从非JSON格式的文本中解析"""
        import re

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
    print("MiniMaxMatcher 已初始化（测试需要API密钥）")
