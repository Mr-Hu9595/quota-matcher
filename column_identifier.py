"""
列名智能识别模块
功能：根据预定义的列名变体列表，识别Excel/Wor表格中的关键列
"""

from typing import List, Dict, Optional, Tuple


class ColumnIdentifier:
    """列名智能识别器"""

    # 项目名称列的可能列名
    NAME_COLUMNS = [
        "名称", "项目名称", "设备名称", "材料名称",
        "工作内容", "项目", "设备", "材料",
        "型号", "规格", "规格型号",
        "item_name", "name", "item", "description"
    ]

    # 工程量/数量列的可能列名
    QUANTITY_COLUMNS = [
        "数量", "工程量", "工作量", "计数量",
        "qty", "quantity", "amount", "num"
    ]

    # 单位列的可能列名
    UNIT_COLUMNS = [
        "单位", "计量单位", "工程单位",
        "unit", "uom"
    ]

    # 序号列的可能列名
    SEQ_COLUMNS = [
        "序号", "编号", "no", "num", "serial",
        "index", "id", "seq"
    ]

    # 备注列的可能列名
    REMARK_COLUMNS = [
        "备注", "说明", "施工要求", "remark", "note", "memo"
    ]

    @classmethod
    def find_column_index(cls, headers: List[str]) -> Dict[str, Optional[int]]:
        """
        根据表头查找关键列的索引

        Args:
            headers: 表头列表

        Returns:
            Dict: {
                "name": 列索引或None,
                "quantity": 列索引或None,
                "unit": 列索引或None,
                "seq": 列索引或None,
                "remark": 列索引或None
            }
        """
        result = {
            "name": None,
            "quantity": None,
            "unit": None,
            "seq": None,
            "remark": None
        }

        # 标准化表头为小写，并移除换行符
        normalized_headers = [h.replace('\n', '').replace('\r', '').strip().lower() for h in headers]

        # 查找各类列（每个候选词单独检查）
        result["name"] = cls._find_column(normalized_headers, cls.NAME_COLUMNS)
        result["quantity"] = cls._find_column(normalized_headers, cls.QUANTITY_COLUMNS)
        result["unit"] = cls._find_column(normalized_headers, cls.UNIT_COLUMNS)
        result["seq"] = cls._find_column(normalized_headers, cls.SEQ_COLUMNS)
        result["remark"] = cls._find_column(normalized_headers, cls.REMARK_COLUMNS)

        return result

    @classmethod
    def _find_column(cls, normalized_headers: List[str], candidates: List[str]) -> Optional[int]:
        """
        在表头列表中查找匹配的列索引

        Args:
            normalized_headers: 标准化后的表头列表
            candidates: 候选列名列表

        Returns:
            int: 匹配的列索引，未找到返回None
        """
        candidates_lower = [c.lower() for c in candidates]

        for i, header in enumerate(normalized_headers):
            # 跳过空表头
            if not header:
                continue
            # 支持部分匹配（例如"名称description"匹配"名称"）
            # 检查任一候选词是否出现在表头中
            for candidate in candidates_lower:
                if candidate in header:
                    return i

        return None

    @classmethod
    def extract_columns(cls, row: List[str], column_map: Dict[str, Optional[int]]) -> Dict[str, str]:
        """
        从一行数据中提取各列的值

        Args:
            row: 原始行数据列表
            column_map: 列索引映射

        Returns:
            Dict: 提取后的数据 {"name": "", "quantity": "", "unit": "", ...}
        """
        result = {}

        for key, index in column_map.items():
            if index is not None and index < len(row):
                value = row[index]
                if isinstance(value, str):
                    result[key] = value.strip()
                else:
                    # 处理数值类型
                    result[key] = str(value) if value is not None else ""
            else:
                result[key] = ""

        return result

    @classmethod
    def validate_mapping(cls, column_map: Dict[str, Optional[int]]) -> Tuple[bool, List[str]]:
        """
        验证列映射是否有效

        Args:
            column_map: 列索引映射

        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)
        """
        errors = []

        if column_map.get("name") is None:
            errors.append("未找到项目名称列")

        if column_map.get("quantity") is None:
            errors.append("未找到工程量/数量列")

        # 单位列可能缺失（有些清单不单独列单位）
        # 序号列主要用于验证，不强制要求

        return len(errors) == 0, errors


if __name__ == "__main__":
    # 测试代码
    headers = ["序号", "名称", "数量", "单位", "备注"]
    mapping = ColumnIdentifier.find_column_index(headers)
    print(f"列映射结果: {mapping}")

    valid, errors = ColumnIdentifier.validate_mapping(mapping)
    print(f"验证结果: valid={valid}, errors={errors}")
