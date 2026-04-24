# -*- coding: utf-8 -*-
"""
规则匹配引擎
基于规则库的精确匹配，支持规格参数区间匹配和自学习扩展
"""

import re
from typing import List, Dict, Optional, Tuple

from ..data.rule_db import RuleDB, QuotaRule
from ..data.quota_db import QuotaDB
from .base import EngineABC, MatchResult
from .spec_parser import SpecParser, SpecParams
from ..utils.logging import get_engine_logger

logger = get_engine_logger()


class RuleEngine(EngineABC):
    """
    规则匹配引擎

    特点：
    - 基于规则库的精确关键词匹配
    - 支持规格参数区间匹配（DN、功率、截面、芯数等）
    - 支持前缀过滤和自学习扩展
    - 当规则库匹配不好时，从定额数据库直接搜索
    - 响应速度快，适合批量处理
    """

    def __init__(self, rule_db: RuleDB = None, quota_db: QuotaDB = None):
        """
        初始化规则匹配引擎

        Args:
            rule_db: 规则数据库实例
            quota_db: 定额数据库实例（用于直接搜索）
        """
        self.rule_db = rule_db or RuleDB()
        self.quota_db = quota_db or QuotaDB()

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

        # 1. 解析规格参数
        spec = SpecParser.parse(work_content)
        logger.debug(f"解析规格: {spec}")

        # 2. 前缀筛选 + 规格匹配
        scored = self._spec_match(work_content, spec)

        # 3. 转换为 MatchResult
        results = []
        for rule, score, match_type in scored:
            if score <= 0:
                continue

            # 根据分数和匹配类型判断置信度
            if score >= 0.9 and match_type == 'spec':
                confidence = "high"
                need_confirm = False
                note = f"规格匹配: {match_type}"
            elif score >= 0.6:
                confidence = "medium"
                need_confirm = False
                note = f"规格+关键词: {match_type}"
            elif score >= 0.3:
                confidence = "medium"
                need_confirm = True
                note = f"关键词命中: {match_type}"
            else:
                confidence = "low"
                need_confirm = True
                note = "低置信度"

            result = MatchResult(
                code=rule.code,
                name=rule.name,
                unit=rule.unit,
                confidence=confidence,
                note=note,
                engine=self.name,
                score=score,
                prefix=rule.prefix,
                need_confirm=need_confirm
            )
            results.append(result)

        # 4. 排序返回
        results.sort(key=lambda x: x.score, reverse=True)
        logger.debug(f"规则匹配结果: {len(results)} 条, 最高分={results[0].score if results else 0}")

        return results[:5]

    def _spec_match(self, text: str, spec: SpecParams) -> List[Tuple[QuotaRule, float, str]]:
        """
        规格参数区间匹配

        Args:
            text: 工作内容文本
            spec: 解析后的规格参数

        Returns:
            List of (规则, 分数, 匹配类型)
        """
        # 1. 从规则库获取候选规则
        if spec.prefix:
            rule_candidates = self.rule_db.get_rules(prefix=spec.prefix)
        else:
            rule_candidates = self.rule_db.get_all()

        # 2. 计算规则库中每条规则的匹配分数
        scored = []
        for rule in rule_candidates:
            score, match_type = self._calculate_rule_score(rule, text, spec)
            if score > 0:
                scored.append((rule, score, match_type))

        # 3. 按分数排序
        scored.sort(key=lambda x: x[1], reverse=True)

        # 3. 如果有规格参数，也从定额库直接搜索（包含更多定额条目）
        if spec.prefix:
            logger.debug(f"从定额库搜索 prefix={spec.prefix}")
            quota_results = self._search_quota_db(text, spec)
            if quota_results:
                # 合并结果（去重）
                seen_codes = {s[0].code for s in scored}
                for quota, quota_score, quota_match_type in quota_results:
                    if quota['code'] not in seen_codes:
                        seen_codes.add(quota['code'])
                        # 将 quota dict 转换为 QuotaRule 风格
                        rule_from_quota = QuotaRule(
                            code=quota['code'],
                            name=quota['name'],
                            unit=quota['unit'],
                            prefix=spec.prefix
                        )
                        scored.append((rule_from_quota, quota_score, quota_match_type))

        # 4. 按分数排序
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _search_quota_db(self, text: str, spec: SpecParams) -> List[Tuple[Dict, float, str]]:
        """
        从定额数据库直接搜索匹配

        Args:
            text: 工作内容文本
            spec: 解析后的规格参数

        Returns:
            List of (quota_dict, score, match_type)
        """
        results = []

        # 按前缀搜索定额（扩大搜索范围以包含更多条目）
        quotas = self.quota_db.search_by_prefix(spec.prefix, top_k=200)

        for quota in quotas:
            name = quota.get('name', '')
            code = quota.get('code', '')

            # 解析定额名称中的规格
            quota_specs = SpecParser.parse_spec_from_quota_name(name)
            score = 0.0
            match_type = 'quota_db'

            # DN匹配
            if spec.dn is not None and 'dn' in quota_specs:
                rule_dn = quota_specs['dn']
                if spec.dn <= rule_dn:
                    score = max(score, 0.9 - (rule_dn - spec.dn) / rule_dn * 0.1)
                    match_type = 'dn'

            # 功率匹配
            if spec.power is not None and 'power' in quota_specs:
                rule_power = quota_specs['power']
                if spec.power <= rule_power:
                    s = 0.9 - (rule_power - spec.power) / rule_power * 0.1
                    if s > score:
                        score = s
                        match_type = 'power'

            # 截面匹配
            if spec.cross_section is not None and 'cross_section' in quota_specs:
                rule_cs = quota_specs['cross_section']
                if spec.cross_section <= rule_cs:
                    s = 0.9 - (rule_cs - spec.cross_section) / rule_cs * 0.1
                    if s > score:
                        score = s
                        match_type = 'cross_section'

            # 芯数匹配
            if spec.core_count is not None and 'core_count' in quota_specs:
                rule_core = quota_specs['core_count']
                if spec.core_count <= rule_core:
                    s = 0.9 - (rule_core - spec.core_count) / rule_core * 0.1
                    if s > score:
                        score = s
                        match_type = 'core_count'

            if score > 0:
                results.append((quota, score, match_type))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:10]

    def _calculate_rule_score(self, rule: QuotaRule, text: str, spec: SpecParams) -> Tuple[float, str]:
        """
        计算单条规则的匹配分数

        Returns:
            (分数, 匹配类型)
            - 分数范围 0-1
            - 匹配类型: 'spec', 'keyword', 'combined'
        """
        text_lower = text.lower()
        name_lower = rule.name.lower()

        spec_score = 0.0
        keyword_score = 0.0
        spec_match_type = None  # 记录规格匹配类型

        # 1. 规格参数匹配（高权重）
        if spec.dn is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'dn' in rule_specs:
                rule_dn = rule_specs['dn']
                if spec.dn <= rule_dn:
                    # 选择最接近的上限（DN值最小的那个规则）
                    spec_score = 0.9 - (rule_dn - spec.dn) / rule_dn * 0.1
                    spec_match_type = 'dn'
                    logger.debug(f"DN匹配: 输入{spec.dn} <= 规则{rule_dn}, rule={rule.code}, score={spec_score:.3f}")

        if spec.power is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'power' in rule_specs:
                rule_power = rule_specs['power']
                if spec.power <= rule_power:
                    score = 0.9 - (rule_power - spec.power) / rule_power * 0.1
                    if score > spec_score:
                        spec_score = score
                        spec_match_type = 'power'

        if spec.cross_section is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'cross_section' in rule_specs:
                rule_cs = rule_specs['cross_section']
                if spec.cross_section <= rule_cs:
                    score = 0.9 - (rule_cs - spec.cross_section) / rule_cs * 0.1
                    if score > spec_score:
                        spec_score = score
                        spec_match_type = 'cross_section'

        if spec.core_count is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'core_count' in rule_specs:
                rule_core = rule_specs['core_count']
                if spec.core_count <= rule_core:
                    score = 0.9 - (rule_core - spec.core_count) / rule_core * 0.1
                    if score > spec_score:
                        spec_score = score
                        spec_match_type = 'core_count'

        if spec.bridge_size is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'bridge_size' in rule_specs:
                rule_bs = rule_specs['bridge_size']
                if spec.bridge_size <= rule_bs:
                    score = 0.9 - (rule_bs - spec.bridge_size) / rule_bs * 0.1
                    if score > spec_score:
                        spec_score = score
                        spec_match_type = 'bridge_size'

        if spec.half_perimeter is not None:
            rule_specs = SpecParser.parse_spec_from_quota_name(rule.name)
            if 'half_perimeter' in rule_specs:
                rule_hp = rule_specs['half_perimeter']
                if abs(spec.half_perimeter - rule_hp) < 0.01:
                    score = 0.9
                    if score > spec_score:
                        spec_score = score
                        spec_match_type = 'half_perimeter'

        # 2. 防爆属性修正（不影响spec_score，只作为辅助判断）
        explosion_match = False
        if spec.has_explosion_proof:
            if '防爆' in name_lower or '防爆' in rule.keywords.lower():
                explosion_match = True

        # 3. 关键词命中
        kw_hits = 0
        total_kw = 0

        if rule.keywords:
            keywords = [k.strip().lower() for k in rule.keywords.split(',') if k.strip()]
            total_kw = len(keywords)

            for kw in keywords:
                if len(kw) < 2:
                    continue
                if kw in text_lower:
                    kw_hits += 1
                elif len(kw) > 3:
                    for word in kw.split():
                        if word in text_lower:
                            kw_hits += 0.5
                            break

        if total_kw > 0:
            keyword_score = min(kw_hits / total_kw, 1.0) * 0.5

        # 4. 防爆惩罚：如果需要防爆但规则不匹配，则降分
        if spec.has_explosion_proof and not explosion_match and rule.prefix in ['4-12', '4-14', '4-6']:
            if spec_score > 0:
                spec_score *= 0.5  # 降低50%
                keyword_score *= 0.5

        # 5. 综合评分
        if spec_score > 0 and keyword_score > 0:
            final_score = spec_score * 0.7 + keyword_score * 0.3
            match_type = 'combined'
        elif spec_score > 0:
            final_score = spec_score
            match_type = spec_match_type or 'spec'
        elif keyword_score > 0:
            final_score = keyword_score
            match_type = 'keyword'
        else:
            final_score = 0.0
            match_type = 'none'

        return (final_score, match_type)

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
