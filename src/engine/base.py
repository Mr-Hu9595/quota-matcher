"""
匹配引擎抽象基类
定义引擎接口规范
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class MatchResult:
    """匹配结果"""
    code: str
    name: str
    unit: str
    confidence: str  # high, medium, low
    note: str = ""
    engine: str = ""
    score: float = 0.0
    prefix: str = ""
    need_confirm: bool = False

    def to_dict(self) -> Dict:
        return {
            'code': self.code,
            'name': self.name,
            'unit': self.unit,
            'confidence': self.confidence,
            'note': self.note,
            'engine': self.engine,
            'score': self.score,
            'prefix': self.prefix,
            'need_confirm': self.need_confirm
        }


class EngineABC(ABC):
    """
    匹配引擎抽象基类

    所有匹配引擎必须实现：
    - name: 引擎名称
    - match(): 单条匹配
    - batch_match(): 批量匹配（可选，默认逐条处理）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        pass

    @abstractmethod
    def match(self, work_content: str, context: Dict = None) -> List[MatchResult]:
        """
        匹配工作内容

        Args:
            work_content: 工作内容描述
            context: 上下文（可选），包含 quantity, unit 等信息

        Returns:
            List[MatchResult]: 匹配结果列表，按置信度降序
        """
        pass

    def batch_match(self, items: List[Dict]) -> List[Dict]:
        """
        批量匹配（默认逐条处理）

        Args:
            items: 清单项目列表，每项包含 name, quantity, unit 等

        Returns:
            List[Dict]: 匹配结果列表，保留原始字段
        """
        from ..utils.logging import get_engine_logger, MatchLog

        logger = get_engine_logger()
        logger.info(f"{self.name} 批量匹配开始: {len(items)} 项")

        MatchLog.log_batch_start(len(items))

        results = []
        high = medium = low = 0

        for i, item in enumerate(items):
            work_content = item.get('name', '')

            try:
                matches = self.match(work_content, item)

                if matches:
                    best = matches[0]
                    results.append(self._to_result_dict(best, item))

                    if best.confidence == 'high':
                        high += 1
                    elif best.confidence == 'medium':
                        medium += 1
                    else:
                        low += 1

                    # 记录匹配日志
                    MatchLog.log(
                        item_name=work_content,
                        code=best.code,
                        confidence=best.confidence,
                        engine=self.name,
                        note=best.note
                    )
                else:
                    results.append(self._to_empty_result(item))
                    low += 1
                    MatchLog.log(
                        item_name=work_content,
                        code="",
                        confidence="low",
                        engine=self.name,
                        note="无匹配"
                    )

            except Exception as e:
                logger.error(f"匹配异常: {work_content[:30]}... - {e}")
                results.append(self._to_error_result(item, str(e)))
                low += 1

        MatchLog.log_batch_end(
            success=len(results),
            failed=0,
            high=high,
            medium=medium,
            low=low
        )

        logger.info(f"{self.name} 批量匹配完成: high={high}, medium={medium}, low={low}")

        return results

    def _to_result_dict(self, result: MatchResult, item: Dict) -> Dict:
        """将 MatchResult 转为结果字典"""
        return {
            'code': result.code,
            'name': result.name,
            'unit': result.unit,
            'confidence': result.confidence,
            'note': result.note,
            'engine': result.engine or self.name,
            'need_confirm': result.need_confirm,
            'original_name': item.get('name', ''),
            'original_quantity': item.get('quantity'),
            'original_unit': item.get('unit', ''),
        }

    def _to_empty_result(self, item: Dict) -> Dict:
        """空结果"""
        return {
            'code': '',
            'name': f"{item.get('name', '')}（待人工确认）",
            'unit': item.get('unit', ''),
            'confidence': 'low',
            'note': '未找到匹配规则',
            'engine': self.name,
            'need_confirm': True,
            'original_name': item.get('name', ''),
            'original_quantity': item.get('quantity'),
            'original_unit': item.get('unit', ''),
        }

    def _to_error_result(self, item: Dict, error: str) -> Dict:
        """错误结果"""
        return {
            'code': '',
            'name': f"{item.get('name', '')}（匹配异常）",
            'unit': item.get('unit', ''),
            'confidence': 'low',
            'note': f'匹配异常: {error}',
            'engine': self.name,
            'need_confirm': True,
            'original_name': item.get('name', ''),
            'original_quantity': item.get('quantity'),
            'original_unit': item.get('unit', ''),
        }
