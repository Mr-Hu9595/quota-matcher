"""
规则匹配引擎
基于规则库的精确匹配，支持自学习扩展
"""

from typing import List, Dict

from ..data.rule_db import RuleDB
from .base import EngineABC, MatchResult
from ..utils.logging import get_engine_logger

logger = get_engine_logger()


class RuleEngine(EngineABC):
    """
    规则匹配引擎

    特点：
    - 基于规则库的精确关键词匹配
    - 支持自学习扩展（用户确认后自动学习新规则）
    - 响应速度快，适合批量处理
    """

    def __init__(self, rule_db: RuleDB = None):
        """
        初始化规则匹配引擎

        Args:
            rule_db: 规则数据库实例
        """
        self.rule_db = rule_db or RuleDB()

    @property
    def name(self) -> str:
        return "rule"

    def match(self, work_content: str, context: Dict = None) -> List[MatchResult]:
        """
        规则匹配

        Args:
            work_content: 工作内容描述
            context: 上下文（可选）

        Returns:
            List[MatchResult]: 匹配结果列表
        """
        if not work_content:
            return []

        logger.debug(f"规则匹配: {work_content[:30]}...")

        # 关键词匹配
        matches = self.rule_db.match_by_keywords(work_content, top_k=5)

        results = []
        for rule, hits in matches:
            # 根据命中数判断置信度
            if hits >= 2:
                confidence = "high"
                need_confirm = False
            elif hits >= 1:
                confidence = "medium"
                need_confirm = False
            else:
                confidence = "low"
                need_confirm = True

            result = MatchResult(
                code=rule.code,
                name=rule.name,
                unit=rule.unit,
                confidence=confidence,
                note=f"关键词命中 {int(hits)} 个",
                engine=self.name,
                score=float(hits),
                prefix=rule.prefix,
                need_confirm=need_confirm
            )
            results.append(result)

        logger.debug(f"规则匹配结果: {len(results)} 条, 最高命中={results[0].score if results else 0}")

        return results

    def learn(self, code: str, name: str, unit: str, keywords: List[str]):
        """
        学习新规则

        Args:
            code: 定额编号
            name: 定额名称
            unit: 单位
            keywords: 关键词列表
        """
        logger.info(f"学习新规则: code={code}, name={name}")
        self.rule_db.add_rule(code, name, unit, keywords)

    def confirm(self, code: str):
        """
        确认规则使用

        Args:
            code: 定额编号
        """
        logger.info(f"确认规则: code={code}")
        self.rule_db.confirm_rule(code)
