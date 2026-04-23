# -*- coding: utf-8 -*-
"""
混合匹配引擎
规则优先 + Chat 辅助（基于 MiniMax M2.7 大模型）
"""

from typing import List, Dict

from ..data.rule_db import RuleDB
from ..data.quota_db import QuotaDB
from .base import EngineABC, MatchResult
from .rule_engine import RuleEngine
from .chat_engine import ChatEngine
from ..utils.logging import get_engine_logger

logger = get_engine_logger()


class HybridEngine(EngineABC):
    """
    混合匹配引擎

    匹配策略：
    1. 规则匹配（高权重 0.7）：精确关键词匹配
    2. Chat 匹配（低权重 0.3）：MiniMax M2.7 语义理解
    3. 综合排序返回
    """

    def __init__(self, rule_db: RuleDB = None, quota_db: QuotaDB = None, api_key: str = None):
        """
        初始化混合匹配引擎

        Args:
            rule_db: 规则数据库
            quota_db: 定额数据库（用于 Chat 引擎候选检索）
            api_key: MiniMax API Key
        """
        self.rule_engine = RuleEngine(rule_db)
        self.chat_engine = ChatEngine(quota_db=quota_db, api_key=api_key)

    @property
    def name(self) -> str:
        return "hybrid"

    def match(self, work_content: str, context: Dict = None) -> List[MatchResult]:
        """
        混合匹配

        Args:
            work_content: 工作内容描述
            context: 上下文（可选）

        Returns:
            List[MatchResult]: 综合排序后的匹配结果
        """
        if not work_content:
            return []

        logger.debug(f"混合匹配: {work_content[:30]}...")

        # 1. 规则匹配
        rule_matches = self.rule_engine.match(work_content, context)
        rule_score_map = {m.code: m for m in rule_matches}
        rule_hit_map = {m.code: m.score for m in rule_matches}

        # 2. Chat 搜索
        chat_matches = self.chat_engine.match(work_content, context)
        chat_score_map = {m.code: m for m in chat_matches}

        # 3. 合并结果
        seen_codes = set()
        combined = []

        # 优先排列规则高命中
        for code, rule_result in rule_score_map.items():
            if code in seen_codes:
                continue
            seen_codes.add(code)

            chat_result = chat_score_map.get(code)
            chat_score = chat_result.score if chat_result else 0
            rule_score = rule_result.score

            # 综合分数 = 规则命中 * 0.7 + Chat分数 * 0.3
            combined_score = rule_score * 0.7 + chat_score * 0.3

            # 更新置信度
            if rule_score >= 2:
                confidence = "high"
                need_confirm = False
            elif rule_score >= 1:
                confidence = "medium"
                need_confirm = False
            elif chat_score > 0.5:
                confidence = "medium"
                need_confirm = False
            else:
                confidence = "low"
                need_confirm = True

            result = MatchResult(
                code=code,
                name=rule_result.name,
                unit=rule_result.unit,
                confidence=confidence,
                note=f"规则{int(rule_score)}个, Chat匹配{chat_result.note if chat_result else ''}",
                engine=self.name,
                score=combined_score,
                prefix=rule_result.prefix,
                need_confirm=need_confirm
            )
            combined.append(result)

        # 添加纯 Chat 匹配（规则未命中但 Chat 高置信度）
        for code, chat_result in chat_score_map.items():
            if code in seen_codes:
                continue
            seen_codes.add(code)

            if chat_result.score >= 0.8:
                combined.append(MatchResult(
                    code=code,
                    name=chat_result.name,
                    unit=chat_result.unit,
                    confidence="medium" if chat_result.score >= 0.9 else "low",
                    note=f"纯Chat匹配: {chat_result.note}",
                    engine=self.name,
                    score=chat_result.score * 0.3,
                    prefix=chat_result.prefix,
                    need_confirm=True
                ))

        # 4. 按综合分数排序
        combined.sort(key=lambda x: x.score, reverse=True)

        logger.debug(f"混合匹配结果: {len(combined)} 条, 最高分={combined[0].score if combined else 0}")

        return combined[:5]

    def learn(self, code: str, name: str, unit: str, keywords: List[str]):
        """学习新规则"""
        self.rule_engine.learn(code, name, unit, keywords)

    def confirm(self, code: str):
        """确认规则使用"""
        self.rule_engine.confirm(code)
