"""
定额文件加载器
功能：读取并解析河南省各专业预算定额文件
"""

import re
from pathlib import Path
from typing import List, Dict


class QuotaLoader:
    """定额文件加载器"""

    # 默认定额文件路径
    QUOTA_FILE = Path(__file__).parent.parent / "db" / "河南省通用安装工程预算定额2016.txt"

    # 专业名称映射（文件名 -> 专业名称）
    PROFESSION_MAP = {
        "河南省通用安装工程预算定额2016.txt": "河南省安装工程",
        "河南省市政工程预算定额2016.txt": "河南省市政工程",
        "河南省房屋建筑与装饰工程预算定额2016.txt": "河南省房屋建筑与装饰工程",
        "河南省城市轨道交通工程预算定额2019.txt": "河南省城市轨道交通工程",
        "河南省城市地下综合管廊工程预算定额2019.txt": "河南省城市地下综合管廊工程",
        "河南省绿色建筑工程预算定额2019.txt": "河南省绿色建筑工程",
        "河南省装配式建筑工程预算定额2019.txt": "河南省装配式建筑工程",
        "河南省市政公用设施养护维修预算定额2020.txt": "河南省市政公用设施养护维修",
    }

    # 定额编号格式正则（按专业）
    CODE_PATTERNS = {
        "河南省安装工程": r'^\d+-\d+-\d+$',           # X-X-X (如 4-9-165)
        "河南省市政工程": r'^\d+-\d+-\d+$',           # X-X-X (如 5-3-385)
        "河南省房屋建筑与装饰工程": r'^\d+-\d+$',     # X-XX (如 1-12)
        "河南省城市轨道交通工程": r'^\d+-\d{3}$',    # X-XXX (如 1-001)
        "河南省城市地下综合管廊工程": r'^\d+-\d+-\d+$',  # X-X-X
        "河南省绿色建筑工程": r'^\d+-\d+$',           # X-XX
        "河南省装配式建筑工程": r'^\d+-[A-Za-z0-9]+$',  # X-字母数字 (如 1-HA1)
        "河南省市政公用设施养护维修": r'^\d+-\d+$',   # X-XX
    }

    # 默认编号格式（兼容旧格式）
    DEFAULT_CODE_PATTERN = r'^\d+-\d+(\-\d+)?$'

    def __init__(self, quota_file: str = None, profession: str = None):
        """
        初始化定额加载器

        Args:
            quota_file: 定额文件路径，默认使用项目根目录的定额文件
            profession: 专业名称（如"安装"、"市政"等），如果未提供则根据文件名自动检测
        """
        if quota_file:
            self.quota_file = Path(quota_file)
        else:
            self.quota_file = self.QUOTA_FILE

        # 确定专业名称
        if profession:
            self.profession = profession
        else:
            self.profession = self._detect_profession()

    def _detect_profession(self) -> str:
        """根据文件名自动检测专业名称"""
        filename = self.quota_file.name
        return self.PROFESSION_MAP.get(filename, "河南省安装工程")

    def get_profession(self) -> str:
        """获取当前加载器对应的专业名称"""
        return self.profession

    def load(self) -> List[Dict]:
        """
        加载定额数据

        Returns:
            List[Dict]: 定额数据列表
            每项包含: code(定额编号), name(项目名称), unit(单位), price(基价)
        """
        if not self.quota_file.exists():
            raise FileNotFoundError(f"定额文件不存在: {self.quota_file}")

        quotas = []
        current_chapter = ""
        current_section = ""

        with open(self.quota_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # 检测章节标题
                if line.startswith('第') and '章' in line:
                    current_chapter = line
                    continue
                elif line.startswith('第') and '节' in line:
                    current_section = line
                    continue
                elif '第' in line and ('册' in line or '章' in line):
                    current_chapter = line
                    current_section = ""
                    continue

                # 解析定额行: 编号\t名称\t单位\t价格
                parts = line.split('\t')
                if len(parts) >= 4:
                    code = parts[0].strip()
                    name = parts[1].strip()
                    unit = parts[2].strip()

                    # 验证是否为有效定额编号 (格式如 1-1-1)
                    if self._is_valid_code(code):
                        try:
                            price = float(parts[3].strip())
                        except ValueError:
                            price = 0.0

                        quotas.append({
                            "code": code,
                            "name": name,
                            "unit": unit,
                            "price": price,
                            "chapter": current_chapter,
                            "section": current_section,
                            "profession": self.profession,
                            "source_file": str(self.quota_file)
                        })

        return quotas

    def _is_valid_code(self, code: str) -> bool:
        """
        验证是否为有效的定额编号格式

        Args:
            code: 定额编号

        Returns:
            bool: 是否有效
        """
        if not code:
            return False

        # 先尝试按专业精确匹配
        if self.profession in self.CODE_PATTERNS:
            pattern = self.CODE_PATTERNS[self.profession]
            if re.match(pattern, code):
                return True

        # 回退到默认格式检查
        return bool(re.match(self.DEFAULT_CODE_PATTERN, code))

    def search(self, keyword: str, quotas: List[Dict] = None) -> List[Dict]:
        """
        根据关键词搜索定额

        Args:
            keyword: 搜索关键词
            quotas: 定额列表，默认加载全部

        Returns:
            List[Dict]: 匹配的定额列表
        """
        if quotas is None:
            quotas = self.load()

        keyword = keyword.lower()
        results = []

        for quota in quotas:
            if keyword in quota["name"].lower():
                results.append(quota)

        return results

    def get_by_code(self, code: str, quotas: List[Dict] = None) -> Dict:
        """
        根据编号获取定额

        Args:
            code: 定额编号
            quotas: 定额列表，默认加载全部

        Returns:
            Dict: 定额信息，未找到返回None
        """
        if quotas is None:
            quotas = self.load()

        for quota in quotas:
            if quota["code"] == code:
                return quota

        return None

    def batch_by_chapter(self, quotas: List[Dict] = None) -> Dict[str, List[Dict]]:
        """
        按章节分组定额

        Args:
            quotas: 定额列表，默认加载全部

        Returns:
            Dict[str, List[Dict]]: 章节 -> 定额列表
        """
        if quotas is None:
            quotas = self.load()

        chapters = {}
        for quota in quotas:
            chapter = quota.get("chapter", "未分类")
            if chapter not in chapters:
                chapters[chapter] = []
            chapters[chapter].append(quota)

        return chapters


if __name__ == "__main__":
    # 测试代码
    loader = QuotaLoader()
    quotas = loader.load()
    print(f"共加载 {len(quotas)} 条定额")

    if quotas:
        print("\n前5条定额:")
        for q in quotas[:5]:
            print(f"  {q['code']}\t{q['name']}\t{q['unit']}\t{q['price']}")
