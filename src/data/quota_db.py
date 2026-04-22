"""
定额数据库模块
只做CRUD操作，不含任何匹配逻辑
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from ..utils.logging import get_data_logger

logger = get_data_logger()


@dataclass
class Quota:
    """定额数据类"""
    id: Optional[int] = None
    code: str = ""
    name: str = ""
    unit: str = ""
    price: float = 0.0
    chapter: str = ""
    section: str = ""
    profession: str = ""
    source_file: str = ""
    work_content: str = ""


class QuotaDB:
    """
    定额数据库 - 只做CRUD，不含匹配逻辑

    接口：
    - get_by_code(code, profession): 按定额号查
    - search_by_prefix(prefix): 按前缀查
    - search_by_keyword(keyword): 按关键词查
    - get_by_profession(profession): 按专业查
    - get_all(): 全量查询
    - count(): 统计数量
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "db" / "quota.db"
        self.db_path = str(db_path)
        self._conn = None
        self._ensure_table()

    @property
    def conn(self) -> sqlite3.Connection:
        """懒加载数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_table(self):
        """确保表存在"""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL DEFAULT 0,
                chapter TEXT,
                section TEXT,
                profession TEXT NOT NULL,
                source_file TEXT,
                work_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(code, profession)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profession ON quotas(profession)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_code ON quotas(code)")

        self.conn.commit()
        logger.debug("quotas表检查完成")

    def get_by_code(self, code: str, profession: str = None) -> Optional[Dict]:
        """
        根据编号获取定额

        Args:
            code: 定额编号（如 4-9-159）
            profession: 专业名称（可选）

        Returns:
            定额信息字典，未找到返回None
        """
        logger.debug(f"查询定额: code={code}, profession={profession}")

        cursor = self.conn.cursor()
        if profession:
            row = cursor.execute(
                "SELECT * FROM quotas WHERE code = ? AND profession = ?",
                (code, profession)
            ).fetchone()
        else:
            row = cursor.execute(
                "SELECT * FROM quotas WHERE code = ?",
                (code,)
            ).fetchone()

        if row:
            result = dict(row)
            logger.debug(f"查询结果: 找到 {code}")
            return result

        logger.debug(f"查询结果: 未找到 {code}")
        return None

    def search_by_prefix(self, prefix: str) -> List[Dict]:
        """
        根据前缀搜索定额

        Args:
            prefix: 前缀（如 4-9）

        Returns:
            定额列表
        """
        logger.debug(f"按前缀搜索: prefix={prefix}")

        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM quotas WHERE code LIKE ? ORDER BY code",
            (f"{prefix}-%",)
        ).fetchall()

        result = [dict(row) for row in rows]
        logger.debug(f"搜索结果: {len(result)} 条")
        return result

    def search_by_keyword(self, keyword: str, top_k: int = 10) -> List[Dict]:
        """
        根据关键词搜索定额（LIKE匹配）

        Args:
            keyword: 关键词
            top_k: 返回数量限制

        Returns:
            定额列表
        """
        logger.debug(f"按关键词搜索: keyword={keyword}, top_k={top_k}")

        cursor = self.conn.cursor()
        pattern = f"%{keyword}%"
        rows = cursor.execute(
            """SELECT * FROM quotas
               WHERE name LIKE ? OR code LIKE ? OR work_content LIKE ?
               ORDER BY code LIMIT ?""",
            (pattern, pattern, pattern, top_k)
        ).fetchall()

        result = [dict(row) for row in rows]
        logger.debug(f"搜索结果: {len(result)} 条")
        return result

    def get_by_profession(self, profession: str) -> List[Dict]:
        """
        获取指定专业的所有定额

        Args:
            profession: 专业名称

        Returns:
            定额列表
        """
        logger.debug(f"按专业查询: profession={profession}")

        cursor = self.conn.cursor()
        rows = cursor.execute(
            "SELECT * FROM quotas WHERE profession = ? ORDER BY code",
            (profession,)
        ).fetchall()

        result = [dict(row) for row in rows]
        logger.debug(f"查询结果: {len(result)} 条")
        return result

    def get_all(self) -> List[Dict]:
        """获取所有定额"""
        logger.debug("获取所有定额")

        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT * FROM quotas ORDER BY code").fetchall()

        result = [dict(row) for row in rows]
        logger.debug(f"总记录数: {len(result)}")
        return result

    def add(self, quota: Dict) -> int:
        """
        添加定额

        Args:
            quota: 定额字典

        Returns:
            插入的ID
        """
        logger.debug(f"添加定额: code={quota.get('code')}")

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO quotas
            (code, name, unit, price, chapter, section, profession, source_file, work_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quota.get('code'),
            quota.get('name'),
            quota.get('unit'),
            quota.get('price', 0),
            quota.get('chapter', ''),
            quota.get('section', ''),
            quota.get('profession'),
            quota.get('source_file', ''),
            quota.get('work_content', '')
        ))

        self.conn.commit()
        return cursor.lastrowid or cursor.lastrowid

    def batch_add(self, quotas: List[Dict]):
        """
        批量添加定额

        Args:
            quotas: 定额列表
        """
        logger.info(f"批量添加定额: {len(quotas)} 条")

        cursor = self.conn.cursor()
        for quota in quotas:
            cursor.execute("""
                INSERT OR REPLACE INTO quotas
                (code, name, unit, price, chapter, section, profession, source_file, work_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quota.get('code'),
                quota.get('name'),
                quota.get('unit'),
                quota.get('price', 0),
                quota.get('chapter', ''),
                quota.get('section', ''),
                quota.get('profession'),
                quota.get('source_file', ''),
                quota.get('work_content', '')
            ))

        self.conn.commit()
        logger.info(f"批量添加完成: {len(quotas)} 条")

    def count(self) -> int:
        """获取定额总数"""
        cursor = self.conn.cursor()
        count = cursor.execute("SELECT COUNT(*) FROM quotas").fetchone()[0]
        return count

    def count_by_profession(self, profession: str) -> int:
        """获取指定专业的定额数量"""
        cursor = self.conn.cursor()
        count = cursor.execute(
            "SELECT COUNT(*) FROM quotas WHERE profession = ?",
            (profession,)
        ).fetchone()[0]
        return count

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("数据库连接已关闭")

    def __del__(self):
        """析构时关闭连接"""
        self.close()
