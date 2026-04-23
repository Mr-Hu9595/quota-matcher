# -*- coding: utf-8 -*-
"""
工程量智能识别模块
功能：有附表按附表提取工程量，无附表时规则+AI混合解析描述语义
"""

import re
import os
from typing import List, Dict, Optional
from abc import ABC, abstractmethod


class QuantityExtractor:
    """工程量提取主入口"""

    def __init__(self, api_key: str = None):
        self.table_extractor = StructuredTableExtractor()
        self.descriptive_extractor = DescriptiveExtractor(api_key)

    def extract(self, items: List[Dict]) -> List[Dict]:
        """
        提取工程量信息

        Args:
            items: 原始清单项目列表，每项包含 name, quantity, unit

        Returns:
            List[Dict]: 增强后的项目列表
        """
        results = []

        for item in items:
            source = item.get("source", "")

            if source == "table":
                # 有附表来源，使用StructuredTableExtractor
                enhanced = self.table_extractor.extract(item)
            else:
                # 无附表来源，使用DescriptiveExtractor处理描述
                enhanced = self.descriptive_extractor.extract(item)

            results.append(enhanced)

        return results


class StructuredTableExtractor:
    """从附表明细表提取工程量"""

    def extract(self, data: Dict) -> Dict:
        """
        从附表数据提取工程量

        Args:
            data: 原始数据，包含name, quantity, unit等

        Returns:
            Dict: 增强后的数据
        """
        name = data.get("name", "")
        quantity = data.get("quantity", 0)
        unit = data.get("unit", "项")

        # 提取规格
        spec = self._extract_spec(name)

        return {
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "spec": spec,
            "source": "table",
            "confidence": "high",
            "extraction_note": "从附表明细提取"
        }

    def _extract_spec(self, name: str) -> str:
        """从名称中提取规格型号"""
        # 常见的规格模式
        patterns = [
            r'(DN\d+)',           # DN80
            r'(\d+×\d+(\+\d+×\d+)*)',  # 4×240+1×120
            r'(YJV[^-]+)',        # YJV-4×240
            r'(\d+mm²)',          # 4mm²
            r'(∠\d+[*×\d]+)',    # ∠40*40*4
        ]

        for pattern in patterns:
            match = re.search(pattern, name)
            if match:
                return match.group(1)

        return ""


class DescriptiveExtractor:
    """从描述文字智能解析工程量（规则+AI混合）"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        self._patterns = self._init_patterns()
        self._ai_parser = None

    @property
    def ai_parser(self):
        if self._ai_parser is None and self.api_key:
            self._ai_parser = AISemanticParser(self.api_key)
        return self._ai_parser

    def _init_patterns(self) -> List[Dict]:
        """初始化正则表达式模式库 - 基于广联达Excel样板扩展"""
        return [
            # ========== 电力电缆 ==========
            # 电力电缆：YJV-4×240+1×120 500米 或 YJV-4×240+1×120（无数量）
            {
                "pattern": r'(YJV[^-]*[-]?\d+×\d+(\+\d+×\d+)*)(?:\s+(?:共计|共|合计)?\s*(\d+(?:\.\d+)?)\s*(米|m))?',
                "name_template": "电力电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 3
            },
            # 电力电缆简短表达：3*70+1*35 500米
            {
                "pattern": r'(\d+×\d+(\+\d+×\d+)*)\s*电力电缆\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "电力电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 3
            },
            # 电力电缆仅规格+数量：4*10 200米
            {
                "pattern": r'(\d+×\d+(\+\d+×\d+)?)\s+(\d+(?:\.\d+)?)\s*(?:米|m)',
                "name_template": "电力电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 3
            },
            # ========== 控制电缆 ==========
            # 控制电缆：KJV-10×1.5 200米 或 KJV-10×1.5（无数量）
            {
                "pattern": r'(KJV[^-]*[-]?\d+×\d+(\+\d+×\d+)*)(?:\s+(?:共计|共|合计)?\s*(\d+(?:\.\d+)?)\s*(米|m))?',
                "name_template": "控制电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 3
            },
            # 控制电缆简短表达：10*1.5 200米
            {
                "pattern": r'(\d+×\d+(\+\d+×\d+)*)\s*(?:控制电缆)?\s*(\d+(?:\.\d+)?)\s*(?:米|m)',
                "name_template": "控制电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 控制电缆芯数规格：电缆芯数≤6芯
            {
                "pattern": r'(电缆芯数≤?\d+芯)\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "控制电缆 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 接地跨接线 ==========
            # 接地跨接线：4mm²接地跨接黄绿双色线 100米
            {
                "pattern": r'(\d+mm²)\s*接地跨接.*?(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "{spec}接地跨接黄绿双色线",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 钢管 ==========
            # 热镀锌钢管 DN80 150米
            {
                "pattern": r'(DN\d+)\s*热镀锌钢管\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌钢管 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # DN50热镀锌钢管 100米
            {
                "pattern": r'(DN\d+)\s*(\d+(?:\.\d+)?)\s*(?:米|m)',
                "name_template": "热镀锌钢管 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 镀锌钢管敷设 DN≤50
            {
                "pattern": r'镀锌钢管敷设\s*(DN≤?\d+)\s*(\d+(?:\.\d+)?)\s*(10m|米|m)',
                "name_template": "镀锌钢管敷设 {spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 防爆钢管敷设 DN≤25
            {
                "pattern": r'防爆钢管敷设\s*(DN≤?\d+)\s*(\d+(?:\.\d+)?)\s*(10m|米|m)',
                "name_template": "防爆钢管敷设 {spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 镀锌钢管 暗配 DN≤20
            {
                "pattern": r'(DN≤?\d+)\s*镀锌钢管.*?(\d+(?:\.\d+)?)\s*(10m|米|m)',
                "name_template": "镀锌钢管 {spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 桥架 ==========
            # 钢制梯式桥架安装 宽+高≤800mm
            {
                "pattern": r'(宽\+高≤\d+mm)\s*桥架.*?(\d+(?:\.\d+)?)\s*(10m|米|m)',
                "name_template": "钢制梯式桥架安装 {spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 桥架支撑架制作
            {
                "pattern": r'(电缆桥架支撑架制作)\s*(\d+(?:\.\d+)?)\s*(kg|个|套)',
                "name_template": "{spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 槽钢 ==========
            # 10#热镀锌槽钢 50米
            {
                "pattern": r'(10#)\s*热镀锌槽钢\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌槽钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 槽钢 10# 30米
            {
                "pattern": r'(10#)\s*槽钢\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "槽钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 角钢 ==========
            # ∠40*40*4热镀锌角钢 30米
            {
                "pattern": r'(∠\d+[*×\d]+)\s*热镀锌角钢\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "热镀锌角钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # 角钢 ∠40×40×4 50米
            {
                "pattern": r'(∠\d+[×*]\d+[×*]\d+)\s*(\d+(?:\.\d+)?)\s*(米|m)',
                "name_template": "角钢 {spec}",
                "unit": "米",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 摄像头立柱 ==========
            # 3.5米摄像头立柱 10套
            {
                "pattern": r'(\d+\.?\d*)\s*米\s*摄像头立柱\s*(\d+(?:\.\d+)?)\s*(套|个|台)',
                "name_template": "摄像头立柱 高度{height}米",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2,
                "height_capture": True
            },
            # 摄像头立柱 高度3.5m 10套
            {
                "pattern": r'摄像头立柱\s*高度?(\d+\.?\d*)\s*(?:米|m)?\s*(\d+(?:\.\d+)?)\s*(套|个|台)',
                "name_template": "摄像头立柱 高度{height}米",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2,
                "height_capture": True
            },
            # ========== 防爆接线盒 ==========
            {
                "pattern": r'防爆接线盒\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "防爆接线盒",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 1
            },
            # 明装防爆接线盒安装
            {
                "pattern": r'明装防爆接线盒安装\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "明装防爆接线盒安装",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 1
            },
            # ========== 三防接线盒 ==========
            {
                "pattern": r'三防接线盒\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "三防接线盒",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 1
            },
            # ========== 防爆活接头 ==========
            {
                "pattern": r'防爆活接头\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "防爆活接头",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 1
            },
            # ========== 钢板 ==========
            # 200*200*8mm钢板 15块
            {
                "pattern": r'(\d+[*×]\d+[*×]\d+mm)\s*钢板\s*(\d+(?:\.\d+)?)\s*(块|吨)',
                "name_template": "钢板 {spec}",
                "unit": "块",
                "spec_group": 1,
                "qty_group": 2
            },
            # 普通钢板 δ=8mm
            {
                "pattern": r'普通钢板\s*δ?=?(\d+mm)\s*(\d+(?:\.\d+)?)\s*(kg|吨|t)',
                "name_template": "普通钢板 δ={spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 铁构件 ==========
            # 一般铁构件制作
            {
                "pattern": r'(一般铁构件制作|一般铁构件安装)\s*(\d+(?:\.\d+)?)\s*(kg|个)',
                "name_template": "{spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # 电缆桥架支撑架
            {
                "pattern": r'(电缆桥架支撑架)\s*(\d+(?:\.\d+)?)\s*(kg|套)',
                "name_template": "{spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # 基础槽钢制作、安装
            {
                "pattern": r'(基础槽钢制作|基础槽钢安装)\s*(\d+(?:\.\d+)?)\s*(m|米)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 接地系统 ==========
            # 接地极(板)制作与安装 圆钢接地极
            {
                "pattern": r'接地极.*?(圆钢接地极|接地极板)\s*(\d+(?:\.\d+)?)\s*(根|个)',
                "name_template": "接地极制作与安装 {spec}",
                "unit": "根",
                "spec_group": 2,
                "qty_group": 2
            },
            # 接地母线敷设
            {
                "pattern": r'(户内接地母线敷设|户外接地母线敷设)\s*(\d+(?:\.\d+)?)\s*(m|米)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 接地模块安装
            {
                "pattern": r'接地模块安装\s*(\d+(?:\.\d+)?)\s*(个|套)',
                "name_template": "接地模块安装",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 1
            },
            # 接地系统测试
            {
                "pattern": r'接地系统测试\s*(\d+(?:\.\d+)?)\s*(系统|次)',
                "name_template": "接地系统测试",
                "unit": "系统",
                "spec_group": 1,
                "qty_group": 1
            },
            # 铜接地绞线敷设
            {
                "pattern": r'(户外铜接地绞线敷设)\s*(\d+(?:\.\d+)?)\s*(m|米)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 电缆终端头 ==========
            # 电力电缆终端头制作安装 1kV以下室内干包式铜芯电力电缆 4*10
            {
                "pattern": r'(电力电缆终端头制作安装.*?(?:4\*\d+|截面≤\d+mm\d*))\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # 电力电缆终端头 10kV室内热(冷)缩式
            {
                "pattern": r'(电力电缆终端头制作安装.*?热[冷]缩式.*?(?:截面≤?\d+mm\d*)?)\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # 控制电缆终端头制作安装
            {
                "pattern": r'(控制电缆终端头制作安装.*?芯数≤?\d+)\s*(\d+(?:\.\d+)?)\s*(个)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 电机检查/调试 ==========
            # 交流异步电动机检查接线 功率≤13kW
            {
                "pattern": r'(交流异步电动机检查接线.*?功率≤?\d+[kK]?W)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 交流防爆电动机检查接线
            {
                "pattern": r'(交流防爆电动机检查接线.*?(?:功率≤?\d+[kK]?W)?)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 交流同步电动机检查接线
            {
                "pattern": r'(交流同步电动机检查接线)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 大中型电动机检查接线
            {
                "pattern": r'(大中型电动机检查接线.*?重量≤?\d+t)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 电动机负载调试
            {
                "pattern": r'(交流异步电动机负载调试.*?功率≤?\d+[kK]?W)\s*(\d+(?:\.\d+)?)\s*(台|系统)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 变频调速电动机负载调试
            {
                "pattern": r'(交流变频调速电动机负载调试)\s*(\d+(?:\.\d+)?)\s*(台|系统)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 配电箱/柜 ==========
            # 成套配电箱安装 半周长0.5m
            {
                "pattern": r'(成套配电箱安装.*?半周长\d+\.?\d*m)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 低压成套配电柜安装
            {
                "pattern": r'(低压成套配电柜安装)\s*(\d+(?:\.\d+)?)\s*(台|面)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 落地式配电箱安装
            {
                "pattern": r'(成套配电箱安装.*?落地式)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== UPS/蓄电池 ==========
            # UPS安装 三相不间断电源 ≤100kV·A
            {
                "pattern": r'(UPS安装.*?(?:容量|功率)≤?\d+[kK]?V·A)\s*(\d+(?:\.\d+)?)\s*(台|套)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # 密封式铅酸蓄电池安装
            {
                "pattern": r'(密封式铅酸蓄电池安装.*?容量≤?\d+[A·]?h)\s*(\d+(?:\.\d+)?)\s*(个|组|套)',
                "name_template": "{spec}",
                "unit": "组",
                "spec_group": 1,
                "qty_group": 2
            },
            # 蓄电池组充放电
            {
                "pattern": r'(蓄电池组充放电.*?电压≤?\d+V.*?容量≤?\d+[A·]?h)\s*(\d+(?:\.\d+)?)\s*(组|次)',
                "name_template": "{spec}",
                "unit": "组",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 路灯 ==========
            # 防爆路灯安装
            {
                "pattern": r'(防爆路灯安装.*?臂长[<>]?\d+\.?\d*m)\s*(\d+(?:\.\d+)?)\s*(套|个)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # 单臂悬挑灯架路灯安装
            {
                "pattern": r'(单臂悬挑灯架路灯安装.*?臂长[<>]?\d+\.?\d*m)\s*(\d+(?:\.\d+)?)\s*(套|个)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # 高杆灯架路灯安装
            {
                "pattern": r'(高杆灯架路灯安装.*?灯高≤?\d+m.*?灯火数≤?\d+火)\s*(\d+(?:\.\d+)?)\s*(套|个)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # 路灯金属杆安装 单杆 杆长≤10m
            {
                "pattern": r'(路灯金属杆安装.*?杆长≤?\d+m)\s*(\d+(?:\.\d+)?)\s*(根|套)',
                "name_template": "{spec}",
                "unit": "根",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 照明灯具 ==========
            # 密封灯具安装 防爆灯 弯杆式
            {
                "pattern": r'(密封灯具安装.*?(?:防爆灯|弯杆式|吸顶式))\s*(\d+(?:\.\d+)?)\s*(套|个)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # 标志、诱导装饰灯具安装
            {
                "pattern": r'(标志、诱导装饰灯具安装.*?(?:墙壁式|吊杆式|嵌入式))\s*(\d+(?:\.\d+)?)\s*(套|个)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 穿线/布线 ==========
            # 穿照明线 铜芯 导线截面≤2.5mm2
            {
                "pattern": r'(穿照明线.*?导线截面≤?\d+\.?\d*mm2)\s*(\d+(?:\.\d+)?)\s*(m|米|100m)',
                "name_template": "{spec}",
                "unit": "100m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 压铜接线端子
            {
                "pattern": r'(压铜接线端子.*?导线截面≤?\d+mm2)\s*(\d+(?:\.\d+)?)\s*(个|套)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 电缆防火 ==========
            # 防火包安装
            {
                "pattern": r'(防火包安装)\s*(\d+(?:\.\d+)?)\s*(个|处|m|米)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # 防火堵料
            {
                "pattern": r'(防火堵料)\s*(\d+(?:\.\d+)?)\s*(kg|处|m|米)',
                "name_template": "{spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # 防火涂料
            {
                "pattern": r'(防火涂料)\s*(\d+(?:\.\d+)?)\s*(kg|m|米)',
                "name_template": "{spec}",
                "unit": "kg",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 自动投入装置 ==========
            # 备用电源自动投入装置
            {
                "pattern": r'(备用电源自动投入装置|自动投入装置系统调试)\s*(\d+(?:\.\d+)?)\s*(套|系统)',
                "name_template": "{spec}",
                "unit": "套",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 不间断电源调试 ==========
            {
                "pattern": r'(不间断电源.*?容量≤?\d+[kK]?V·A)\s*(\d+(?:\.\d+)?)\s*(系统|套)',
                "name_template": "{spec}",
                "unit": "系统",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 阀门检查接线 ==========
            # 多通电动阀
            {
                "pattern": r'(阀门检查接线.*?(?:多通电动阀|电动阀))\s*(\d+(?:\.\d+)?)\s*(个|台)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 避雷装置 ==========
            # 避雷引下线敷设 断接卡子制作安装
            {
                "pattern": r'(避雷引下线敷设.*?断接卡子制作安装)\s*(\d+(?:\.\d+)?)\s*(个|套)',
                "name_template": "{spec}",
                "unit": "个",
                "spec_group": 1,
                "qty_group": 2
            },
            # 避雷网安装
            {
                "pattern": r'(避雷网安装.*?(?:沿折板支架敷设|平屋顶))\s*(\d+(?:\.\d+)?)\s*(m|米|套)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 等电位连接 ==========
            # 等电位连接 地网600*600(mm2)
            {
                "pattern": r'(等电位连接.*?地网\d+[*×]\d+\(?mm2\)?)\s*(\d+(?:\.\d+)?)\s*(m2|平方米|处)',
                "name_template": "{spec}",
                "unit": "m2",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 电动葫芦 ==========
            {
                "pattern": r'(电动葫芦电气安装.*?起重量≤?\d+t)\s*(\d+(?:\.\d+)?)\s*(台|套)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 励磁屏 ==========
            {
                "pattern": r'(励磁、灭磁、充电馈线屏安装.*?(?:蓄电池屏|柜))\s*(\d+(?:\.\d+)?)\s*(台|面|套)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 刚性阻燃管/半硬质塑料管 ==========
            # 刚性阻燃管敷设 外径50mm
            {
                "pattern": r'(刚性阻燃管敷设.*?外径\d+mm)\s*(\d+(?:\.\d+)?)\s*(10m|m)',
                "name_template": "{spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # 半硬质塑料管敷设 外径50mm
            {
                "pattern": r'(半硬质塑料管敷设.*?外径\d+mm)\s*(\d+(?:\.\d+)?)\s*(10m|m)',
                "name_template": "{spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 直埋式电力电缆 ==========
            {
                "pattern": r'(直埋式电力电缆敷设.*?截面≤?\d+mm2)\s*(\d+(?:\.\d+)?)\s*(10m|m)',
                "name_template": "{spec}",
                "unit": "10m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 地下钢管铺设 ==========
            {
                "pattern": r'(地下敷设.*?钢管铺设.*?直径≤?\d+mm)\s*(\d+(?:\.\d+)?)\s*(m|米)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 沟槽挖填/铺砂盖砖 ==========
            {
                "pattern": r'(沟槽挖填.*?|铺砂、盖砖.*?)\s*(\d+(?:\.\d+)?)\s*(m|米|处)',
                "name_template": "{spec}",
                "unit": "m",
                "spec_group": 1,
                "qty_group": 2
            },
            # ========== 微电机 ==========
            {
                "pattern": r'(微型电机、变频机组检查接线.*?微型电机)\s*(\d+(?:\.\d+)?)\s*(台)',
                "name_template": "{spec}",
                "unit": "台",
                "spec_group": 1,
                "qty_group": 2
            },
        ]

    def extract(self, item: Dict) -> Dict:
        """
        从清单项目提取工程量

        Args:
            item: 原始数据，包含name, quantity, unit

        Returns:
            Dict: 增强后的数据
        """
        name = item.get("name", "")
        quantity = item.get("quantity")
        unit = item.get("unit", "项")

        # 尝试用规则解析（传入已有数量以支持名称中无数量的情况）
        rule_result = self._try_rule_pattern(name, quantity)

        if rule_result:
            rule_result["source"] = "rule"
            rule_result["extraction_note"] = "规则匹配提取"
            return rule_result

        # 规则无法解析，尝试AI解析
        if self.ai_parser:
            ai_results = self.ai_parser.parse(name)
            if ai_results:
                result = ai_results[0]
                result["source"] = "ai"
                result["confidence"] = "medium"
                result["extraction_note"] = "AI语义解析"
                return result

        # 无法解析，返回原始数据并标记low confidence
        return {
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "spec": "",
            "source": "unparsed",
            "confidence": "low",
            "extraction_note": "规则无法解析，需人工确认"
        }

    def extract_from_text(self, text: str) -> List[Dict]:
        """
        从描述文字提取工程量

        Args:
            text: 描述文字

        Returns:
            List[Dict]: 提取的工程量列表
        """
        results = []

        for pattern_def in self._patterns:
            match = re.search(pattern_def["pattern"], text)
            if match:
                spec = match.group(pattern_def["spec_group"])
                qty = float(match.group(pattern_def["qty_group"]))
                unit = pattern_def["unit"]

                # 特殊处理立柱高度
                name = pattern_def["name_template"]
                if pattern_def.get("height_capture"):
                    name = name.format(height=spec)
                else:
                    name = name.format(spec=spec)

                results.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "spec": spec,
                    "source": "rule",
                    "confidence": "high",
                    "extraction_note": "规则精确匹配"
                })

        return results

    def _try_rule_pattern(self, name: str, existing_qty: float = None) -> Optional[Dict]:
        """尝试用规则模式匹配

        Args:
            name: 项目名称
            existing_qty: 已有的数量（从清单解析获得），如果有则优先使用

        Returns:
            Optional[Dict]: 匹配结果或None
        """
        for pattern_def in self._patterns:
            match = re.search(pattern_def["pattern"], name)
            if match:
                spec = match.group(pattern_def["spec_group"])
                unit = pattern_def["unit"]

                # 尝试获取数量
                qty = None
                if pattern_def["qty_group"] <= match.lastindex:
                    qty_str = match.group(pattern_def["qty_group"])
                    if qty_str:
                        qty = float(qty_str)

                # 如果数量为空但有已有数量，使用已有数量
                if qty is None and existing_qty is not None:
                    qty = existing_qty

                # 如果仍然没有数量，跳过此模式
                if qty is None:
                    continue

                name_template = pattern_def["name_template"]
                if pattern_def.get("height_capture"):
                    item_name = name_template.format(height=spec)
                else:
                    item_name = name_template.format(spec=spec)

                return {
                    "name": item_name,
                    "quantity": float(qty),
                    "unit": unit,
                    "spec": spec,
                    "confidence": "high"
                }

        return None

    def _parse_quantity(self, qty_text: str) -> Optional[float]:
        """
        解析数量表达式

        Args:
            qty_text: 数量文本，如 "1+2"、"≈3.5"、"约100"

        Returns:
            float: 解析后的数值
        """
        # 清理文本
        clean = qty_text.replace("≈", "").replace("约", "").replace(" ", "").strip()

        try:
            return float(clean)
        except ValueError:
            # 尝试解析表达式
            if "+" in clean:
                parts = clean.split("+")
                try:
                    return sum(float(p) for p in parts)
                except ValueError:
                    pass

        return None


class AISemanticParser:
    """AI语义解析器（规则无法匹配时的兜底）"""

    API_URL = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    SYSTEM_PROMPT = """你是一位资深预算工程师，精通工程量清单解析。

任务：从工程描述中提取工程量信息。

输入格式：工程描述文本
输出格式：JSON数组

```json
{
  "items": [
    {
      "name": "项目名称（需包含规格型号）",
      "quantity": 数值,
      "unit": "单位",
      "spec": "规格型号（如有）",
      "extraction_note": "提取说明"
    }
  ]
}
```

规则：
- 只提取有明确数量描述的项目
- quantity只返回数字
- 无法提取时返回空数组"""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")

    def parse(self, text: str) -> List[Dict]:
        """
        使用AI解析描述文本

        Args:
            text: 描述文本

        Returns:
            List[Dict]: 提取的工程量列表
        """
        if not self.api_key:
            return []

        import requests
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "MiniMax-M2",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"从以下描述中提取工程量：{text}"}
            ],
            "temperature": 0.3,
            "max_tokens": 512
        }

        try:
            response = requests.post(self.API_URL, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_response(content)
        except Exception as e:
            print(f"AI解析失败: {e}")

        return []

    def _parse_response(self, content: str) -> List[Dict]:
        """解析AI响应"""
        import json
        try:
            data = json.loads(content)
            return data.get("items", [])
        except:
            # 尝试提取JSON
            match = re.search(r'\[[^\]]+\]', content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except:
                    pass
        return []
