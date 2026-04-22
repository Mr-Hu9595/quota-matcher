"""
混合匹配引擎
规则优先 + 向量辅助
"""

from typing import List, Dict

from ..data.rule_db import RuleDB
from ..data.vector_index import VectorIndex
from .base import EngineABC, MatchResult
from .rule_engine import RuleEngine
from .vector_engine import VectorEngine
from ..utils.logging import get_engine_logger

logger = get_engine_logger()


class HybridEngine(EngineABC):
    """
    混合匹配引擎

    匹配策略：
    1. 规则匹配（高权重 0.7）：精确关键词匹配
    2. 向量匹配（低权重 0.3）：语义相似度
    3. 综合排序返回
    """

    def __init__(self, rule_db: RuleDB = None, vector_index: VectorIndex = None):
        """
        初始化混合匹配引擎

        Args:
            rule_db: 规则数据库
            vector_index: 向量索引
        """
        self.rule_engine = RuleEngine(rule_db)
        self.vector_engine = VectorEngine(vector_index)

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

        # 2. 向量搜索
        vector_matches = self.vector_engine.match(work_content, context)
        vector_score_map = {m.code: m for m in vector_matches}

        # 3. 合并结果
        seen_codes = set()
        combined = []

        # 优先排列规则高命中
        for code, rule_result in rule_score_map.items():
            if code in seen_codes:
                continue
            seen_codes.add(code)

            vec_result = vector_score_map.get(code)
            vec_score = vec_result.score if vec_result else 0
            rule_score = rule_result.score

            # 综合分数 = 规则命中 * 0.7 + 向量分数 * 0.3
            combined_score = rule_score * 0.7 + vec_score * 0.3

            # 更新置信度
            if rule_score >= 2:
                confidence = "high"
                need_confirm = False
            elif rule_score >= 1:
                confidence = "medium"
                need_confirm = False
            elif vec_score > 0.5:
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
                note=f"规则命中{int(rule_score)}个, 向量相似度{vec_score:.2f}",
                engine=self.name,
                score=combined_score,
                prefix=rule_result.prefix,
                need_confirm=need_confirm
            )
            combined.append(result)

        # 添加纯向量匹配（规则未命中但向量高相似度）
        for code, vec_result in vector_score_map.items():
            if code in seen_codes:
                continue
            seen_codes.add(code)

            # 只有向量相似度高时才添加
            if vec_result.score >= 0.5:
                combined.append(MatchResult(
                    code=code,
                    name=vec_result.name,
                    unit=vec_result.unit,
                    confidence="medium" if vec_result.score >= 0.7 else "low",
                    note=f"纯向量相似度{vec_result.score:.2f}",
                    engine=self.name,
                    score=vec_result.score * 0.3,  # 纯向量权重
                    prefix=vec_result.prefix,
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
