# -*- coding: utf-8 -*-
"""
Chat 匹配引擎
基于 MiniMax Chat API 做语义匹配，不依赖向量数据库
"""

import json
import os
import re
import requests
from typing import List, Dict, Optional

from ..data.quota_db import QuotaDB
from .base import EngineABC, MatchResult
from ..utils.logging import get_engine_logger

logger = get_engine_logger()

# MiniMax Chat API 配置 (Anthropic 兼容格式，thinking 和 text 分开)
MINIMAX_API_URL = "https://api.minimaxi.com/anthropic/v1/messages"
DEFAULT_MODEL = "MiniMax-M2.7"


class ChatEngine(EngineABC):
    """
    Chat 匹配引擎

    匹配策略：
    1. 从 quota_db 获取候选定额（按关键词/前缀检索）
    2. 用 MiniMax Chat API 让大模型做最优选择
    3. 不依赖向量数据库和 embedding
    """

    def __init__(self, quota_db: QuotaDB = None, api_key: str = None):
        """
        初始化 Chat 匹配引擎

        Args:
            quota_db: 定额数据库
            api_key: MiniMax API Key（默认从环境变量 MINIMAX_API_KEY 或 MINIMAX_CHAT_API_KEY 获取）
        """
        self.quota_db = quota_db or QuotaDB()
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_CHAT_API_KEY")
        self.model = DEFAULT_MODEL

    @property
    def name(self) -> str:
        return "chat"

    def match(self, work_content: str, context: Dict = None) -> List[MatchResult]:
        """
        Chat 匹配

        Args:
            work_content: 工作内容描述
            context: 上下文（可选）

        Returns:
            List[MatchResult]: 匹配结果列表
        """
        if not work_content:
            return []

        profession = context.get('profession') if context else None
        quantity = context.get('quantity') if context else None
        unit = context.get('unit') if context else None

        logger.debug(f"Chat匹配: {work_content[:30]}...")

        try:
            # 1. 获取候选定额
            candidates = self._get_candidates(work_content, profession)
            if not candidates:
                logger.debug("未找到候选定额")
                return []

            # 2. 调用 Chat API
            best = self._chat_select(work_content, candidates, quantity, unit)
            if best:
                return [best]

            return []

        except Exception as e:
            logger.error(f"Chat匹配异常: {e}")
            return []

    def _get_candidates(self, work_content: str, profession: str = None, top_k: int = 30) -> List[Dict]:
        """
        获取候选定额列表

        策略：
        1. 提取关键词，按关键词搜索
        2. 提取定额前缀（如 4-9），按前缀搜索
        3. 合并去重
        """
        candidates_map = {}

        # 提取潜在关键词
        keywords = []
        parts = re.split(r'[\s,\/、。，]+', work_content)
        for p in parts:
            p = p.strip()
            if len(p) >= 2:
                keywords.append(p)

        # 提取规格型号（如 4*16, DN25, 10A 等）
        specs = re.findall(r'\d+[\*×]\d+|\d+[A-Z]\d*|DN\d+|≤?\d+[mm千伏安安培]+', work_content)
        keywords.extend(specs)

        # 提取定额编号前缀
        prefixes = re.findall(r'\b(\d+-\d+)-\d+\b', work_content)
        prefixes.extend(re.findall(r'\b(\d+-\d+)\b', work_content))

        # 按关键词搜索
        seen_codes = set()
        for kw in keywords[:10]:
            results = self.quota_db.search_by_keyword(kw, top_k=20)
            for r in results:
                code = r.get('code', '')
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    if code not in candidates_map:
                        candidates_map[code] = r

        # 按前缀搜索
        for prefix in set(prefixes[:5]):
            results = self.quota_db.search_by_prefix(prefix)
            for r in results:
                code = r.get('code', '')
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    if code not in candidates_map:
                        candidates_map[code] = r

        candidates = list(candidates_map.values())

        # 如果候选太少，按全量搜索
        if len(candidates) < 5:
            all_results = self.quota_db.get_all()
            for r in all_results[:100]:
                code = r.get('code', '')
                if code and code not in seen_codes:
                    seen_codes.add(code)
                    candidates_map[code] = r
            candidates = list(candidates_map.values())

        logger.debug(f"获取候选定额: {len(candidates)} 条")
        return candidates[:top_k]

    def _build_prompt(self, work_content: str, candidates: List[Dict],
                     quantity: float = None, unit: str = None) -> List[Dict]:
        """构建 Chat API 的消息列表"""

        candidate_lines = []
        for i, c in enumerate(candidates[:20]):
            code = c.get('code', '')
            name = c.get('name', '')
            db_unit = c.get('unit', '')
            candidate_lines.append(f"{i+1}. [{code}] {name}（单位:{db_unit}）")

        candidates_text = '\n'.join(candidate_lines)

        system_prompt = f"""你是一个定额匹配专家。你的任务是根据工作内容从候选定额列表中选择最匹配的定额编号。

工作内容：{work_content}
{'工程量：' + str(quantity) + ' ' + unit if quantity else ''}

候选定额列表：
{candidates_text}

你必须严格按以下JSON格式输出，不要输出任何其他内容：
{{"index":数字,"reason":"简短原因"}}

规则：
- index必须是1-20之间的整数，表示候选定额的序号
- 只输出JSON，不要任何解释、注释或思考过程
- 如果无法判断，猜测最可能的选项

直接输出JSON："""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "直接输出JSON，不要解释。"}
        ]

        return messages

    def _extract_json_from_text(self, text: str) -> Optional[Dict]:
        """从文本中提取 JSON，包含多种降级策略"""
        if not text:
            return None

        text = text.strip()

        # 策略1: 去掉 markdown 代码块
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        # 策略2: 尝试直接解析
        if text.startswith("{"):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass

        # 策略3: 找第一个 { 到最后一个 }
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass

        # 策略4: 尝试从文本中提取 index 数字
        # 匹配 "index": 数字 或 "index":数字 格式
        index_match = re.search(r'["\']?index["\']?\s*[:＝]\s*(\d+)', text, re.IGNORECASE)
        if index_match:
            index = int(index_match.group(1))
            if 1 <= index <= 20:
                # 尝试提取 reason
                reason_match = re.search(r'["\']?reason["\']?\s*[:＝]\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
                reason = reason_match.group(1) if reason_match else "从文本推断"
                logger.info(f"从非JSON文本提取: index={index}, reason={reason[:30]}")
                return {"index": index, "reason": reason}

        return None

    def _chat_select(self, work_content: str, candidates: List[Dict],
                     quantity: float = None, unit: str = None) -> Optional[MatchResult]:
        """
        调用 MiniMax Chat API 选择最优定额
        """
        if not self.api_key:
            logger.warning("MiniMax API Key 未配置，Chat 匹配不可用")
            return None

        if not candidates:
            return None

        messages = self._build_prompt(work_content, candidates, quantity, unit)

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "max_tokens": 512,
                "temperature": 0.1
            }

            response = requests.post(
                MINIMAX_API_URL,
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                logger.error(f"Chat API 失败: HTTP {response.status_code} - {response.text[:200]}")
                return None

            result = response.json()
            base_resp = result.get("base_resp", {})
            status_code = base_resp.get("status_code", 0)

            if status_code != 0:
                logger.error(f"Chat API 失败: status_code={status_code}, msg={base_resp.get('status_msg', '')}")
                return None

            # Anthropic API 格式：content 是内容块数组
            content_blocks = result.get("content", [])
            if not content_blocks:
                logger.error(f"Chat API 无返回内容: {result}")
                return None

            # 分别提取 thinking 和 text 块的内容
            text_parts = []
            thinking_parts = []
            for block in content_blocks:
                if block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif block.get("type") == "thinking":
                    thinking_parts.append(block.get("thinking", ""))

            text_content = "".join(text_parts)
            thinking_content = "".join(thinking_parts)

            logger.debug(f"Chat API text响应: {text_content[:200] if text_content else '(empty)'}")
            logger.debug(f"Chat API thinking响应: {thinking_content[:200] if thinking_content else '(empty)'}")

            # Anthropic 格式：优先从 text 提取 JSON，再从 thinking 提取
            parsed = self._extract_json_from_text(text_content)
            if parsed is None and thinking_content:
                parsed = self._extract_json_from_text(thinking_content)
                if parsed:
                    logger.debug(f"从 thinking 块提取到 JSON")

            if parsed is None:
                sample = (text_content or thinking_content or "")[:200]
                logger.error(f"无法从响应中提取 JSON: {sample}")
                return None

            index_val = parsed.get("index")
            if index_val is None:
                logger.debug(f"JSON 中无 index 字段: {parsed}")
                return None

            try:
                index = int(index_val)
            except (ValueError, TypeError):
                logger.debug(f"index 不是有效数字: {index_val}")
                return None

            reason = str(parsed.get("reason", "") or "")

            if index <= 0 or index > len(candidates):
                logger.debug(f"无效的 index: {index}")
                return None

            selected = candidates[index - 1]

            return MatchResult(
                code=selected.get('code', ''),
                name=selected.get('name', ''),
                unit=selected.get('unit', ''),
                confidence="high",
                note=f"Chat匹配: {reason}",
                engine=self.name,
                score=0.9,
                prefix=self._extract_prefix(selected.get('code', '')),
                need_confirm=False
            )

        except requests.exceptions.Timeout:
            logger.error("Chat API 超时")
            return None
        except Exception as e:
            logger.error(f"Chat API 异常: {e}")
            return None

    def _extract_prefix(self, code: str) -> str:
        """提取前缀"""
        if not code:
            return ""
        parts = code.split('-')
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
        return parts[0] if parts else ""
