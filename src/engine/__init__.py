"""
引擎层 - 纯逻辑接口，接口稳定，不含数据操作
"""

from .base import EngineABC, MatchResult
from .rule_engine import RuleEngine
from .vector_engine import VectorEngine
from .hybrid_engine import HybridEngine

__all__ = ['EngineABC', 'MatchResult', 'RuleEngine', 'VectorEngine', 'HybridEngine']
