# -*- coding: utf-8 -*-
"""
规格参数解析器
从工作内容中提取规格参数：DN、功率、截面、芯数等
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple


@dataclass
class SpecParams:
    """规格参数"""
    prefix: str = ""           # 前缀，如 "4-9", "4-12"
    dn: Optional[int] = None   # DN规格值
    power: Optional[int] = None  # 功率(kW)
    cross_section: Optional[int] = None  # 截面(mm²)
    core_count: Optional[int] = None  # 芯数
    bridge_size: Optional[int] = None  # 桥架宽+高(mm)
    half_perimeter: Optional[float] = None  # 半周长(m)
    has_explosion_proof: bool = False  # 防爆
    cable_type: str = ""  # 电力电缆/控制电缆
    work_type: str = ""  # 工作类型关键词

    def __repr__(self):
        return (f"SpecParams(prefix={self.prefix}, dn={self.dn}, power={self.power}, "
                f"cross_section={self.cross_section}, core_count={self.core_count}, "
                f"explosion_proof={self.has_explosion_proof}, cable_type={self.cable_type})")


class SpecParser:
    """规格参数解析器"""

    # DN规格模式
    DN_PATTERNS = [
        r'DN\s*[≤=<]\s*(\d+)',      # DN≤50, DN≤25
        r'公称直径\s*[≤=<]\s*(\d+)', # 公称直径≤50
        r'DN(\d+)',                   # DN50
        r'φ\s*(\d+)',                # φ50
    ]

    # 功率模式
    POWER_PATTERNS = [
        r'(\d+(?:\.\d+)?)\s*kW',    # 30kW, 13.5kW
        r'功率\s*[≤=<]\s*(\d+)',     # 功率≤30
        r'≤\s*(\d+)\s*kW',           # ≤30kW
    ]

    # 截面模式
    CROSS_SECTION_PATTERNS = [
        r'(\d+)\s*[xX*]\s*(\d+)',    # 4x16, 4X16, 4*16 (not ×)
        r'截面\s*[≤=<]\s*(\d+)',    # 截面≤10mm²
        r'≤\s*(\d+)\s*mm',           # ≤10mm
        r'(\d+)\s*mm',               # 10mm²
    ]

    # 芯数模式
    CORE_COUNT_PATTERNS = [
        r'(\d+)\s*[×\*×]\s*(\d+)',  # 4×16 (可能是芯数×截面)
        r'芯数\s*[≤=<]\s*(\d+)',    # 芯数≤6
        r'(\d+)\s*芯',               # 6芯
    ]

    # 桥架尺寸模式
    BRIDGE_SIZE_PATTERNS = [
        r'宽\s*[+＋]\s*高\s*[≤=<]\s*(\d+)',  # 宽+高≤800mm
    ]

    # 半周长模式
    HALF_PERIMETER_PATTERNS = [
        r'半周长\s*(\d+(?:\.\d+)?)\s*m',  # 半周长2.5m
    ]

    # 前缀模式
    PREFIX_PATTERNS = [
        r'\b(\d+-\d+)-\d+',  # 4-9-159 → 4-9
        r'\b(\d+-\d+)\b',     # 4-9 → 4-9
    ]

    # 防爆关键词
    EXPLOSION_PROOF_KEYWORDS = ['防爆', '防爆型', '防爆式', '防爆设备']

    # 电缆类型关键词
    CABLE_TYPE_KEYWORDS = {
        '电力电缆': ['电力电缆', '电力电缆敷设'],
        '控制电缆': ['控制电缆', '控制电缆敷设'],
    }

    # 工作类型关键词
    WORK_TYPE_KEYWORDS = {
        '桥架': ['桥架', '梯式桥架', '槽式桥架', '托盘'],
        '钢管': ['钢管', '镀锌钢管', '防爆钢管'],
        '电机': ['电动机', '电机', '变频机组'],
        '配电箱': ['配电箱', '操作柱', '接线箱'],
        '灯具': ['灯具', 'LED灯', '防爆灯', '路灯'],
        '终端头': ['终端头', '电缆终端头'],
        '接地': ['接地', '避雷'],
        '调试': ['调试', '负载调试', '系统调试'],
        '电力电缆': ['电力电缆', '电力电缆敷设'],
        '控制电缆': ['控制电缆', '控制电缆敷设'],
    }

    # 工作类型到前缀的映射
    WORK_TYPE_TO_PREFIX = {
        '桥架': '4-9',
        '钢管': '4-12',
        '电机': '4-6',
        '配电箱': '4-2',
        '灯具': '4-14',
        '终端头': '4-9',
        '接地': '4-10',
        '调试': '4-17',
        '电力电缆': '4-9',
        '控制电缆': '4-9',
    }

    @classmethod
    def parse(cls, text: str) -> SpecParams:
        """
        解析工作内容，提取规格参数

        Args:
            text: 工作内容文本

        Returns:
            SpecParams 对象
        """
        text = text.strip()
        spec = SpecParams()

        # 1. 先确定工作类型（用于后续推断前缀）
        spec.work_type = cls._identify_work_type(text)

        # 2. 提取前缀（优先从文本中提取，其次从工作类型推断）
        spec.prefix = cls._extract_prefix(text)
        if not spec.prefix:
            spec.prefix = cls._infer_prefix_from_work_type(spec.work_type)

        # 3. 提取DN规格
        spec.dn = cls._extract_value(text, cls.DN_PATTERNS)

        # 3. 提取功率
        spec.power = cls._extract_value(text, cls.POWER_PATTERNS)

        # 4. 提取截面
        cross_sections = cls._extract_cross_sections(text)
        if cross_sections:
            # 取最大截面（电力电缆选择按最大单芯截面）
            spec.cross_section = max(cross_sections)

        # 5. 提取芯数
        spec.core_count = cls._extract_core_count(text)

        # 6. 提取桥架尺寸
        spec.bridge_size = cls._extract_value(text, cls.BRIDGE_SIZE_PATTERNS)

        # 7. 提取半周长
        spec.half_perimeter = cls._extract_float(text, cls.HALF_PERIMETER_PATTERNS)

        # 8. 检查防爆
        spec.has_explosion_proof = cls._has_keyword(text, cls.EXPLOSION_PROOF_KEYWORDS)

        # 9. 确定电缆类型
        spec.cable_type = cls._identify_cable_type(text)

        return spec

    @classmethod
    def _extract_prefix(cls, text: str) -> str:
        """提取前缀"""
        for pattern in cls.PREFIX_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""

    @classmethod
    def _extract_value(cls, text: str, patterns: List[str]) -> Optional[int]:
        """提取单个数值"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    @classmethod
    def _extract_float(cls, text: str, patterns: List[str]) -> Optional[float]:
        """提取浮点数值"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None

    @classmethod
    def _extract_cross_sections(cls, text: str) -> List[int]:
        """提取所有截面值（可能多个）"""
        sections = []

        # 模式1: 4×16, 4x16, 4*16 格式
        pattern1 = r'(\d+)\s*[xX*]\s*(\d+)'
        for match in re.finditer(pattern1, text):
            try:
                # 两个数都可能是截面，取较大的
                val1, val2 = int(match.group(1)), int(match.group(2))
                # 通常大值是截面，小值是芯数，但4×16中4是芯数16是截面
                # 对于电力电缆如4×16，16是截面
                sections.append(max(val1, val2))
            except ValueError:
                continue

        # 模式2: ≤XXmm²
        pattern2 = r'截面\s*[≤=<]\s*(\d+)'
        for match in re.finditer(pattern2, text):
            try:
                sections.append(int(match.group(1)))
            except ValueError:
                continue

        # 模式3: ≤XXmm
        pattern3 = r'≤\s*(\d+)\s*mm'
        for match in re.finditer(pattern3, text):
            try:
                sections.append(int(match.group(1)))
            except ValueError:
                continue

        return sections

    @classmethod
    def _extract_core_count(cls, text: str) -> Optional[int]:
        """提取芯数"""
        # 对于 "4×16" 格式，需要判断是芯数×截面还是其他
        # 通常电力电缆 "4×16" 表示 4芯 16mm²截面

        # 芯数≤XX
        pattern1 = r'芯数\s*[≤=<]\s*(\d+)'
        match = re.search(pattern1, text)
        if match:
            return int(match.group(1))

        # XX芯
        pattern2 = r'(\d+)\s*芯'
        match = re.search(pattern2, text)
        if match:
            return int(match.group(1))

        # 如果有 "4×16" 格式，4是芯数
        pattern3 = r'^(\d+)\s*[×\*×]'
        match = re.search(pattern3, text)
        if match:
            return int(match.group(1))

        return None

    @classmethod
    def _has_keyword(cls, text: str, keywords: List[str]) -> bool:
        """检查是否包含关键词"""
        return any(kw in text for kw in keywords)

    @classmethod
    def _identify_cable_type(cls, text: str) -> str:
        """识别电缆类型"""
        for cable_type, keywords in cls.CABLE_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return cable_type
        return ""

    @classmethod
    def _identify_work_type(cls, text: str) -> str:
        """识别工作类型"""
        for work_type, keywords in cls.WORK_TYPE_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return work_type
        return ""

    @classmethod
    def _infer_prefix_from_work_type(cls, work_type: str) -> str:
        """从工作类型推断前缀"""
        return cls.WORK_TYPE_TO_PREFIX.get(work_type, "")

    @classmethod
    def parse_spec_from_quota_name(cls, name: str) -> Dict[str, any]:
        """
        从定额名称解析规格参数（用于规则匹配）

        Args:
            name: 定额名称，如 "室内敷设电力电缆 铜芯电力电缆敷设 电缆截面≤10mm2"

        Returns:
            规格参数字典
        """
        result = {}

        # DN规格
        dn_match = re.search(r'DN\s*[≤=<]\s*(\d+)', name)
        if dn_match:
            result['dn'] = int(dn_match.group(1))

        # 功率
        power_match = re.search(r'功率\s*[≤=<]\s*(\d+)', name)
        if power_match:
            result['power'] = int(power_match.group(1))

        # 截面
        cross_match = re.search(r'截面\s*[≤=<]\s*(\d+)', name)
        if cross_match:
            result['cross_section'] = int(cross_match.group(1))

        # 芯数
        core_match = re.search(r'芯数\s*[≤=<]\s*(\d+)', name)
        if core_match:
            result['core_count'] = int(core_match.group(1))

        # 桥架尺寸
        bridge_match = re.search(r'宽\s*[+＋]\s*高\s*[≤=<]\s*(\d+)', name)
        if bridge_match:
            result['bridge_size'] = int(bridge_match.group(1))

        # 半周长
        perimeter_match = re.search(r'半周长\s*(\d+(?:\.\d+)?)', name)
        if perimeter_match:
            result['half_perimeter'] = float(perimeter_match.group(1))

        return result
