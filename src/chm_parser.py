"""
CHM 文件解析器
功能：解压并解析 CHM 格式的章节说明和勘误文件
"""

import os
import subprocess
import tempfile
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from html.parser import HTMLParser
from xml.etree import ElementTree as ET


class ChmParser:
    """CHM 文件解析器"""

    def __init__(self, temp_dir: str = None):
        """
        初始化 CHM 解析器

        Args:
            temp_dir: 临时目录，用于解压 CHM 文件
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self.hh_exe_path = self._find_hh_exe()

    def _find_hh_exe(self) -> Optional[str]:
        """查找 Windows hh.exe 路径"""
        windir = os.environ.get('WINDIR', 'C:\\Windows')
        # 优先尝试 SysWOW64（32位hh.exe在64位系统上）
        syswow64 = os.path.join(windir, 'SysWOW64', 'hh.exe')
        if os.path.exists(syswow64):
            return syswow64
        # 然后尝试 System32
        system32 = os.path.join(windir, 'System32', 'hh.exe')
        if os.path.exists(system32):
            return system32
        return None

    def _get_pyChm_parser(self):
        """获取 pychm 库的解析器（备选方案）"""
        try:
            import chm
            return chm
        except ImportError:
            return None

    def extract(self, chm_path: str, output_dir: str = None) -> str:
        """
        解压 CHM 文件

        Args:
            chm_path: CHM 文件路径
            output_dir: 输出目录，默认使用临时目录

        Returns:
            str: 解压后的目录路径
        """
        if not os.path.exists(chm_path):
            raise FileNotFoundError(f"CHM 文件不存在: {chm_path}")

        if output_dir is None:
            # 在临时目录下创建以 CHM 文件名为名的子目录
            chm_name = os.path.splitext(os.path.basename(chm_path))[0]
            output_dir = os.path.join(self.temp_dir, chm_name)

        os.makedirs(output_dir, exist_ok=True)

        # 尝试使用 hh.exe 解压
        if self.hh_exe_path:
            try:
                cmd = [self.hh_exe_path, '-decompile', output_dir, chm_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print(f"使用 hh.exe 解压成功: {output_dir}")
                    return output_dir
                else:
                    print(f"hh.exe 解压失败: {result.stderr}")
            except Exception as e:
                print(f"hh.exe 执行异常: {e}")

        # 备选方案：使用 7z 解压
        seven_zip = self._find_7z()
        if seven_zip:
            try:
                cmd = [seven_zip, 'x', '-y', f'-o{output_dir}', chm_path]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    print(f"使用 7z 解压成功: {output_dir}")
                    return output_dir
            except Exception as e:
                print(f"7z 解压异常: {e}")

        raise RuntimeError("无法解压 CHM 文件，请安装 hh.exe 或 7z")

    def _find_7z(self) -> Optional[str]:
        """查找 7z.exe 路径"""
        paths_to_check = [
            r"C:\Program Files\7-Zip\7z.exe",
            r"C:\Program Files (x86)\7-Zip\7z.exe",
        ]
        for path in paths_to_check:
            if os.path.exists(path):
                return path
        return None

    def parse_directory(self, extracted_dir: str) -> List[Dict]:
        """
        解析 CHM 目录文件 (.hhc)

        Args:
            extracted_dir: 解压后的目录

        Returns:
            List[Dict]: 目录项列表
        """
        hhc_files = list(Path(extracted_dir).rglob("*.hhc"))
        if not hhc_files:
            return []

        # 解析第一个 .hhc 文件
        hhc_path = str(hhc_files[0])
        return self._parse_hhc(hhc_path)

    def _parse_hhc(self, hhc_path: str) -> List[Dict]:
        """解析 .hhc 目录文件"""
        items = []

        try:
            # 读取文件内容
            with open(hhc_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # 解析 HTML 格式的目录
            # CHM 目录通常是 <ul> 嵌套结构
            pattern = r'<li>\s*<object[^>]*type="text/sitemap"[^>]*>\s*<param\s+name="Name"\s+value="([^"]*)"[^>]*>.*?<param\s+name="Local"\s+value="([^"]*)"'

            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)

            for name, local in matches:
                items.append({
                    "name": name.strip(),
                    "local": local.strip()
                })

        except Exception as e:
            print(f"解析 .hhc 文件异常: {e}")

        return items

    def extract_chapter_notes(self, chm_path: str) -> List[Dict]:
        """
        从 CHM 提取章节说明

        Args:
            chm_path: CHM 文件路径

        Returns:
            List[Dict]: 章节说明列表
        """
        # 解压 CHM
        extracted_dir = self.extract(chm_path)

        # 解析目录
        toc_items = self.parse_directory(extracted_dir)

        # 收集所有 HTML 文件
        html_files = list(Path(extracted_dir).rglob("*.htm")) + list(Path(extracted_dir).rglob("*.html"))

        # 提取每个页面的内容
        chapter_notes = []
        current_chapter = ""

        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # 提取标题
                title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else ""

                # 提取正文内容（简化处理）
                # 移除脚本和样式
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

                # 提取 body 内容
                body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    body_content = body_match.group(1)
                    # 移除所有 HTML 标签
                    text = re.sub(r'<[^>]+>', '', body_content)
                    # 清理空白
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text and len(text) > 10:
                        # 判断是否章节标题
                        if title and (title.startswith("第") or "章" in title):
                            current_chapter = title

                        chapter_notes.append({
                            "profession": self._detect_profession_from_path(chm_path),
                            "chapter_title": current_chapter or title,
                            "section_title": title if current_chapter else "",
                            "content": text,
                            "source_file": chm_path
                        })

            except Exception as e:
                print(f"处理 HTML 文件异常 {html_file}: {e}")
                continue

        return chapter_notes

    def extract_errata(self, chm_path: str) -> List[Dict]:
        """
        从 CHM 提取勘误信息

        Args:
            chm_path: CHM 文件路径

        Returns:
            List[Dict]: 勘误列表
        """
        # 解压 CHM
        extracted_dir = self.extract(chm_path)

        # 收集所有 HTML 文件
        html_files = list(Path(extracted_dir).rglob("*.htm")) + list(Path(extracted_dir).rglob("*.html"))

        errata_list = []
        profession = self._detect_profession_from_path(chm_path)

        for html_file in html_files:
            try:
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # 提取标题
                title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else ""

                # 提取正文内容
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

                body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
                if body_match:
                    body_content = body_match.group(1)
                    text = re.sub(r'<[^>]+>', '', body_content)
                    text = re.sub(r'\s+', ' ', text).strip()

                    if text and len(text) > 10:
                        # 尝试提取关联的定额编号
                        quota_code = self._extract_quota_code(text)

                        errata_list.append({
                            "profession": profession,
                            "quota_code": quota_code,
                            "title": title,
                            "content": text,
                            "source_file": chm_path
                        })

            except Exception as e:
                print(f"处理 HTML 文件异常 {html_file}: {e}")
                continue

        return errata_list

    def _detect_profession_from_path(self, chm_path: str) -> str:
        """从 CHM 文件路径检测专业名称"""
        filename = os.path.basename(chm_path).lower()

        if "章节说明" in chm_path:
            return "河南省定额章节说明"
        elif "勘误" in chm_path or "相关文件" in chm_path:
            return "河南省相关文件及勘误"

        return "未知"

    def _extract_quota_code(self, text: str) -> str:
        """从文本中提取定额编号"""
        # 匹配常见定额编号格式
        patterns = [
            r'(\d+-\d+-\d+)',  # X-X-X
            r'(\d+-\d+)',      # X-XX
            r'(\d+-\d{3})',    # X-XXX
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return ""


class HTMLContentParser(HTMLParser):
    """HTML 内容解析器"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = ['script', 'style', 'head']

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            return

        # 处理换行标签
        if tag in ['p', 'div', 'br', 'li', 'tr']:
            self.text_parts.append('\n')
        elif tag in ['th', 'td']:
            self.text_parts.append('\t')

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            return

        if tag in ['p', 'div']:
            self.text_parts.append('\n')

    def handle_data(self, data):
        self.text_parts.append(data)

    def get_text(self) -> str:
        text = ''.join(self.text_parts)
        # 清理多余空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        return text.strip()


if __name__ == "__main__":
    # 测试代码
    import sys

    if len(sys.argv) < 2:
        print("用法: python chm_parser.py <CHM文件路径>")
        sys.exit(1)

    chm_path = sys.argv[1]

    if not os.path.exists(chm_path):
        print(f"文件不存在: {chm_path}")
        sys.exit(1)

    parser = ChmParser()

    if "章节说明" in chm_path:
        print("提取章节说明...")
        notes = parser.extract_chapter_notes(chm_path)
        print(f"共提取 {len(notes)} 条章节说明")
        for note in notes[:3]:
            print(f"  - {note.get('chapter_title', '')[:50]}: {note.get('content', '')[:50]}...")

    elif "勘误" in chm_path or "相关文件" in chm_path:
        print("提取勘误信息...")
        errata = parser.extract_errata(chm_path)
        print(f"共提取 {len(errata)} 条勘误")
        for err in errata[:3]:
            print(f"  - {err.get('title', '')[:50]}: {err.get('quota_code', 'N/A')}")
    else:
        print("无法确定 CHM 类型")
