# -*- coding: utf-8 -*-
# skills/quota-matcher/tests/test_quantity_extractor.py
import pytest
import sys
sys.path.insert(0, "src")
from quantity_extractor import QuantityExtractor, StructuredTableExtractor, DescriptiveExtractor


class TestQuantityExtractor:
    """QuantityExtractor主入口测试"""

    def test_extract_with_table_source(self):
        """有附表来源的数据应该标记source='table'"""
        items = [
            {"name": "热镀锌钢管 DN80", "quantity": 100, "unit": "米", "source": "table", "spec": "DN80", "confidence": "high"}
        ]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        assert len(result) == 1
        assert result[0]["source"] == "table"

    def test_extract_without_table_source(self):
        """无附表来源的数据应该使用DescriptiveExtractor处理"""
        items = [
            {"name": "电力电缆 YJV-4×240+1×120", "quantity": 500, "unit": "米"}
        ]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        # 规则解析应该能匹配电缆描述
        assert len(result) >= 1

    def test_enhance_item_fields(self):
        """每条记录应该包含增强字段：spec, source, confidence, extraction_note"""
        items = [{"name": "测试项目", "quantity": 10, "unit": "个"}]
        extractor = QuantityExtractor()
        result = extractor.extract(items)
        item = result[0]
        assert "spec" in item
        assert "source" in item
        assert "confidence" in item
        assert "extraction_note" in item


class TestStructuredTableExtractor:
    """StructuredTableExtractor附表提取测试"""

    def test_extract_pipe_spec_and_quantity(self):
        """穿线管：提取规格和数量"""
        data = {"name": "热镀锌钢管 DN80", "quantity": 100, "unit": "米"}
        extractor = StructuredTableExtractor()
        result = extractor.extract(data)
        assert result["name"] == "热镀锌钢管 DN80"
        assert result["quantity"] == 100
        assert result["source"] == "table"
        assert result["spec"] == "DN80"

    def test_extract_junction_box(self):
        """接线盒：提取型号和数量"""
        data = {"name": "防爆接线盒", "quantity": 20, "unit": "个"}
        extractor = StructuredTableExtractor()
        result = extractor.extract(data)
        assert result["name"] == "防爆接线盒"
        assert result["source"] == "table"


class TestDescriptiveExtractor:
    """DescriptiveExtractor描述提取测试"""

    def test_rule_cable_pattern(self):
        """电缆描述规则匹配"""
        text = "电力电缆 YJV-4×240+1×120 共计500米"
        extractor = DescriptiveExtractor()
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "YJV" in item["name"]
        assert item["quantity"] == 500

    def test_rule_pole_pattern(self):
        """立柱描述规则匹配"""
        text = "3.5米摄像头立柱 10套"
        extractor = DescriptiveExtractor()
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "3.5米" in item["name"]

    def test_expression_parsing(self):
        """表达式解析：1+2、≈3.5、约100"""
        extractor = DescriptiveExtractor()
        assert extractor._parse_quantity("1+2") == 3.0
        assert extractor._parse_quantity("≈3.5") == 3.5
        assert extractor._parse_quantity("约100") == 100.0

    def test_rule_pipe_pattern(self):
        """钢管描述规则匹配"""
        extractor = DescriptiveExtractor()
        text = "DN80热镀锌钢管 150米"
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "DN80" in item["name"]
        assert item["quantity"] == 150

    def test_rule_steel_angle_pattern(self):
        """角钢描述规则匹配"""
        extractor = DescriptiveExtractor()
        text = "∠40*40*4热镀锌角钢 30米"
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "∠40" in item["name"]

    def test_rule_steel_channel_pattern(self):
        """槽钢描述规则匹配"""
        extractor = DescriptiveExtractor()
        text = "10#热镀锌槽钢 50米"
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "10#" in item["name"]

    def test_rule_junction_box_pattern(self):
        """防爆接线盒规则匹配"""
        extractor = DescriptiveExtractor()
        text = "防爆接线盒 20个"
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "防爆接线盒" in item["name"]
        assert item["quantity"] == 20

    def test_rule_steel_plate_pattern(self):
        """钢板规则匹配"""
        extractor = DescriptiveExtractor()
        text = "200*200*8mm钢板 15块"
        result = extractor.extract_from_text(text)
        assert len(result) >= 1
        item = result[0]
        assert "钢板" in item["name"]
