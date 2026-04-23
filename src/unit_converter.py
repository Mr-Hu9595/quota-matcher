# -*- coding: utf-8 -*-
"""
单位转换模块
功能：识别并转换清单单位与定额单位之间的差异，特别是钢材类
"""

import re
from typing import Dict, Optional, Tuple


class UnitConverter:
    """单位转换器"""

    # 钢材理论重量表 (kg/m) - 常见规格
    # 格式: "边宽1*边宽2*厚度": 理论重量(kg/m)
    STEEL_WEIGHT_TABLE = {
        # 等边角钢
        "20*20*3": 0.889,
        "20*20*4": 1.145,
        "25*25*3": 1.124,
        "25*25*4": 1.459,
        "30*30*3": 1.373,
        "30*30*4": 1.786,
        "40*40*3": 1.852,
        "40*40*4": 2.422,
        "40*40*5": 2.967,
        "50*50*4": 3.059,
        "50*50*5": 3.770,
        "50*50*6": 4.465,
        "63*63*5": 4.822,
        "63*63*6": 5.721,
        "70*70*5": 5.397,
        "70*70*6": 6.406,
        "75*75*5": 5.818,
        "75*75*6": 6.905,
        "75*75*7": 7.976,
        "75*75*8": 9.030,
        "80*80*6": 7.376,
        "80*80*8": 9.658,
        "90*90*6": 8.350,
        "90*90*8": 10.946,
        "100*100*6": 9.366,
        "100*100*8": 12.276,

        # 不等边角钢
        "30*20*3": 1.121,
        "30*20*4": 1.458,
        "50*32*4": 2.431,
        "63*40*5": 3.570,
        "75*50*5": 4.808,
        "100*63*6": 7.550,

        # 普通槽钢
        "50*37*4.5": 5.44,
        "63*40*4.8": 6.63,
        "80*43*5.0": 8.04,
        "100*48*5.3": 10.00,
        "120*53*5.5": 12.06,

        # 工字钢
        "100*68*4.5": 11.26,
        "126*74*5.0": 14.22,
        "140*80*5.5": 16.89,
        "160*88*6.0": 20.51,
        "180*94*6.5": 24.14,
    }

    # 扁钢理论重量 (kg/m) - 宽度*厚度
    FLAT_STEEL_WEIGHT = {
        "20*3": 0.47,
        "20*4": 0.63,
        "25*3": 0.59,
        "25*4": 0.79,
        "30*3": 0.71,
        "30*4": 0.94,
        "40*3": 0.94,
        "40*4": 1.26,
        "50*4": 1.57,
        "50*5": 1.96,
    }

    # 需要转换为定额单位的钢材类型关键词
    STEEL_KEYWORDS = ["角钢", "槽钢", "工字钢", "扁钢", "钢板", "钢材"]

    # 需要从米转换为kg的关键词
    METERS_TO_KG_KEYWORDS = ["角钢", "槽钢", "工字钢", "扁钢"]

    # 需要从米转换为100m的关键词（电线电缆）
    METERS_TO_100M_KEYWORDS = ["电线", "电缆", "导线", "网线"]

    @classmethod
    def needs_conversion(cls, item_name: str, unit: str) -> bool:
        """
        判断是否需要进行单位转换

        Args:
            item_name: 项目名称
            unit: 清单单位

        Returns:
            bool: 是否需要转换
        """
        # 检查是否为钢材类
        for keyword in cls.STEEL_KEYWORDS:
            if keyword in item_name:
                return True

        # 检查电线电缆类（米转换为100m）
        if unit in ["米", "m"] and any(k in item_name for k in cls.METERS_TO_100M_KEYWORDS):
            return True

        return False

    @classmethod
    def get_conversion_type(cls, item_name: str) -> str:
        """
        获取转换类型

        Args:
            item_name: 项目名称

        Returns:
            str: "steel_kg" / "cable_100m" / "none"
        """
        for keyword in cls.METERS_TO_KG_KEYWORDS:
            if keyword in item_name:
                return "steel_kg"

        for keyword in cls.METERS_TO_100M_KEYWORDS:
            if keyword in item_name:
                return "cable_100m"

        return "none"

    @classmethod
    def convert_steel_meters_to_kg(cls, item_name: str, meters: float) -> Tuple[float, str]:
        """
        将钢材米数转换为kg

        Args:
            item_name: 项目名称（含规格如"50*50*5角钢"）
            meters: 米数

        Returns:
            Tuple[float, str]: (转换后数量, 说明信息)
        """
        spec = cls._extract_steel_spec(item_name)

        if spec and spec in cls.STEEL_WEIGHT_TABLE:
            weight_per_meter = cls.STEEL_WEIGHT_TABLE[spec]
            total_kg = meters * weight_per_meter
            return total_kg, f"{spec}理论重量{weight_per_meter}kg/m"

        # 尝试匹配扁钢
        flat_spec = cls._extract_flat_spec(item_name)
        if flat_spec and flat_spec in cls.FLAT_STEEL_WEIGHT:
            weight_per_meter = cls.FLAT_STEEL_WEIGHT[flat_spec]
            total_kg = meters * weight_per_meter
            return total_kg, f"扁钢{flat_spec}理论重量{weight_per_meter}kg/m"

        # 无法匹配规格，返回估算
        # 默认按角钢估算约3.77kg/m
        default_weight = 3.77
        total_kg = meters * default_weight
        return total_kg, f"按默认角钢估算约{default_weight}kg/m（需人工确认规格）"

    @classmethod
    def convert_cable_meters_to_100m(cls, meters: float) -> Tuple[float, str]:
        """
        将电线电缆米数转换为定额单位（100m）

        Args:
            meters: 米数

        Returns:
            Tuple[float, str]: (转换后数量, 说明信息)
        """
        result = meters / 100
        return result, f"{meters}m ÷ 100 = {result:.2f}100m"

    @classmethod
    def _extract_steel_spec(cls, item_name: str) -> Optional[str]:
        """
        从项目名称中提取钢材规格

        Args:
            item_name: 项目名称

        Returns:
            str: 规格字符串如"50*50*5"，未找到返回None
        """
        # 匹配 数字*数字*数字 格式
        patterns = [
            r'(\d+\.?\d*)\*(\d+\.?\d*)\*(\d+\.?\d*)',  # 50*50*5
            r'(\d+\.?\d*)\s*×\s*(\d+\.?\d*)\s*×\s*(\d+\.?\d*)',  # 50×50×5
        ]

        for pattern in patterns:
            match = re.search(pattern, item_name)
            if match:
                groups = match.groups()
                return f"{groups[0]}*{groups[1]}*{groups[2]}"

        return None

    @classmethod
    def _extract_flat_spec(cls, item_name: str) -> Optional[str]:
        """
        从项目名称中提取扁钢规格

        Args:
            item_name: 项目名称

        Returns:
            str: 规格字符串如"20*3"，未找到返回None
        """
        # 匹配 数字*数字 格式（扁钢）
        pattern = r'(\d+\.?\d*)\s*[×*]\s*(\d+\.?\d*)\s*(?=扁钢|$)'
        match = re.search(pattern, item_name)
        if match:
            return f"{match.group(1)}*{match.group(2)}"
        return None

    @classmethod
    def convert(cls, item_name: str, quantity: float, unit: str) -> Tuple[float, str, str]:
        """
        执行单位转换

        Args:
            item_name: 项目名称
            quantity: 原始数量
            unit: 原始单位

        Returns:
            Tuple[float, str, str]: (转换后数量, 转换后单位, 说明信息)
        """
        conversion_type = cls.get_conversion_type(item_name)

        if conversion_type == "steel_kg":
            converted_qty, note = cls.convert_steel_meters_to_kg(item_name, quantity)
            return converted_qty, "kg", note

        elif conversion_type == "cable_100m":
            converted_qty, note = cls.convert_cable_meters_to_100m(quantity)
            return converted_qty, "100m", note

        else:
            # 无需转换
            return quantity, unit, ""


if __name__ == "__main__":
    # 测试代码
    converter = UnitConverter()

    # 测试角钢转换
    qty, unit, note = converter.convert("50*50*5角钢", 100, "米")
    print(f"50*50*5角钢 100米 -> {qty} {unit}, 说明: {note}")

    # 测试电线转换
    qty, unit, note = converter.convert("电力电缆", 350, "米")
    print(f"电力电缆 350米 -> {qty} {unit}, 说明: {note}")

    # 测试不需要转换的
    qty, unit, note = converter.convert("安装阀门", 5, "台")
    print(f"安装阀门 5台 -> {qty} {unit}, 说明: {note}")
