"""
定额文件加载器
功能：读取并解析河南省通用安装工程预算定额2016.txt
"""

import re
from pathlib import Path
from typing import List, Dict


class QuotaLoader:
    """定额文件加载器"""

    # 定额文件路径
    QUOTA_FILE = Path(__file__).parent.parent.parent / "河南省通用安装工程预算定额2016.txt"

    def __init__(self, quota_file: str = None):
        """
        初始化定额加载器

        Args:
            quota_file: 定额文件路径，默认使用项目根目录的定额文件
        """
        if quota_file:
            self.quota_file = Path(quota_file)
        else:
            self.quota_file = self.QUOTA_FILE

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
                            "section": current_section
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
        # 定额编号格式: 章节-小节-序号 (如 1-1-1, 12-3-45)
        pattern = r'^\d+-\d+-\d+$'
        return bool(re.match(pattern, code))

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
