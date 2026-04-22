"""
向量匹配引擎
基于ChromaDB的语义相似度搜索
"""

from typing import List, Dict

from ..data.vector_index import VectorIndex
from .base import EngineABC, MatchResult
from ..utils.logging import get_engine_logger

logger = get_engine_logger()


class VectorEngine(EngineABC):
    """
    向量匹配引擎

    特点：
    - 基于语义相似度的向量搜索
    - 支持多专业 Collection 筛选
    - 适合模糊/语义匹配
    """

    def __init__(self, vector_index: VectorIndex = None):
        """
        初始化向量匹配引擎

        Args:
            vector_index: 向量索引实例
        """
        self.vector_index = vector_index or VectorIndex()

    @property
    def name(self) -> str:
        return "vector"

    def match(self, work_content: str, context: Dict = None) -> List[MatchResult]:
        """
        向量匹配

        Args:
            work_content: 工作内容描述
            context: 上下文（可选），可包含 profession 进行筛选

        Returns:
            List[MatchResult]: 匹配结果列表
        """
        if not work_content:
            return []

        profession = None
        if context:
            profession = context.get('profession')

        logger.debug(f"向量匹配: {work_content[:30]}..., profession={profession}")

        try:
            # 搜索向量索引
            results = self.vector_index.search(
                query=work_content,
                top_k=5,
                profession=profession
            )

            match_results = []
            for item in results:
                score = item.get('score', 0)

                # 根据向量距离判断置信度（距离越小越相似）
                # ChromaDB 距离是余弦距离，0为完全相同，2为完全相反
                if score < 0.3:
                    confidence = "high"
                    need_confirm = False
                elif score < 0.5:
                    confidence = "medium"
                    need_confirm = False
                else:
                    confidence = "low"
                    need_confirm = True

                result = MatchResult(
                    code=item.get('code', ''),
                    name=item.get('name', ''),
                    unit=item.get('unit', ''),
                    confidence=confidence,
                    note=f"向量相似度 {1-score:.2f}",
                    engine=self.name,
                    score=1 - score,  # 转换为相似度
                    prefix=self._extract_prefix(item.get('code', '')),
                    need_confirm=need_confirm
                )
                match_results.append(result)

            logger.debug(f"向量匹配结果: {len(match_results)} 条")

            return match_results

        except Exception as e:
            logger.error(f"向量匹配异常: {e}")
            return []

    def _extract_prefix(self, code: str) -> str:
        """提取前缀"""
        if not code:
            return ""
        parts = code.split('-')
        if len(parts) >= 2:
            return f"{parts[0]}-{parts[1]}"
        return parts[0]
