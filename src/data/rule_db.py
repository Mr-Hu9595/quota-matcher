"""
规则数据库模块
支持规则自学习扩展
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from ..utils.logging import get_data_logger

logger = get_data_logger()


@dataclass
class QuotaRule:
    """定额规则数据类"""
    id: Optional[int] = None
    code: str = ""
    name: str = ""
    unit: str = ""
    prefix: str = ""
    keywords: str = ""
    source: str = "manual"
    confirm_count: int = 0
    created_at: str = ""
    updated_at: str = ""

    @property
    def keywords_list(self) -> List[str]:
        return [k.strip() for k in self.keywords.split(',') if k.strip()]

    @property
    def keyword_set(self) -> set:
        return set(self.keywords_list)


class RuleDB:
    """
    规则数据库 - 支持自学习扩展

    接口：
    - get_rules(prefix): 获取规则列表
    - add_rule(code, name, unit, keywords): 添加规则
    - confirm_rule(code): 确认使用（增加置信度）
    - get_rule(code): 获取单个规则
    - get_prefix_info(prefix): 获取前缀信息
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "规则库" / "rules.db"
        self.db_path = str(db_path)
        self._conn = None
        self._init_db()

    @property
    def conn(self) -> sqlite3.Connection:
        """懒加载数据库连接"""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """初始化数据库表"""
        logger.debug("初始化规则数据库")

        cursor = self.conn.cursor()

        # 规则表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                unit TEXT,
                prefix TEXT NOT NULL,
                keywords TEXT,
                source TEXT DEFAULT 'manual',
                confirm_count INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # 前缀索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prefix_index (
                prefix TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT,
                updated_at TEXT
            )
        """)

        # 关键词索引表（用于精确匹配）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS keyword_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL UNIQUE,
                rule_id INTEGER,
                weight REAL DEFAULT 1.0,
                FOREIGN KEY (rule_id) REFERENCES rules(id)
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_prefix ON rules(prefix)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rules_code ON rules(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_keyword_keyword ON keyword_index(keyword)")

        self.conn.commit()
        logger.debug("规则数据库初始化完成")

    def get_rules(self, prefix: str = None) -> List[QuotaRule]:
        """
        获取规则列表

        Args:
            prefix: 前缀筛选（可选）

        Returns:
            规则列表
        """
        logger.debug(f"获取规则列表: prefix={prefix}")

        cursor = self.conn.cursor()
        if prefix:
            rows = cursor.execute(
                "SELECT * FROM rules WHERE prefix = ? ORDER BY code",
                (prefix,)
            ).fetchall()
        else:
            rows = cursor.execute("SELECT * FROM rules ORDER BY code").fetchall()

        result = [self._row_to_rule(row) for row in rows]
        logger.debug(f"获取规则: {len(result)} 条")
        return result

    def get_rule(self, code: str) -> Optional[QuotaRule]:
        """
        根据编号获取规则

        Args:
            code: 定额编号

        Returns:
            规则对象，未找到返回None
        """
        logger.debug(f"获取规则: code={code}")

        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM rules WHERE code = ?", (code,)).fetchone()

        if row:
            return self._row_to_rule(row)
        return None

    def add_rule(self, code: str, name: str, unit: str, keywords: List[str],
                 prefix: str = None, source: str = "manual") -> int:
        """
        添加规则

        Args:
            code: 定额编号
            name: 定额名称
            unit: 单位
            keywords: 关键词列表
            prefix: 前缀（可选，默认从code提取）
            source: 来源

        Returns:
            规则ID
        """
        logger.debug(f"添加规则: code={code}, name={name}")

        if prefix is None:
            parts = code.split('-')
            prefix = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else parts[0]

        now = datetime.now().isoformat()
        keywords_str = ','.join(keywords)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rules (code, name, unit, prefix, keywords, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (code, name, unit, prefix, keywords_str, source, now))

        rule_id = cursor.lastrowid or cursor.execute(
            "SELECT id FROM rules WHERE code = ?", (code,)
        ).fetchone()[0]

        # 更新关键词索引
        for kw in keywords:
            cursor.execute("""
                INSERT OR IGNORE INTO keyword_index (keyword, rule_id)
                VALUES (?, ?)
            """, (kw.strip(), rule_id))

        # 更新前缀索引
        cursor.execute("""
            INSERT OR IGNORE INTO prefix_index (prefix, updated_at)
            VALUES (?, ?)
        """, (prefix, now))

        self.conn.commit()
        logger.info(f"规则添加成功: {code}")
        return rule_id

    def confirm_rule(self, code: str):
        """
        确认使用某规则（增加置信度）

        Args:
            code: 定额编号
        """
        logger.debug(f"确认规则: code={code}")

        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE rules SET confirm_count = confirm_count + 1, updated_at = ?
            WHERE code = ?
        """, (datetime.now().isoformat(), code))
        self.conn.commit()

    def match_by_keywords(self, text: str, top_k: int = 10) -> List[Tuple[QuotaRule, int]]:
        """
        根据关键词匹配规则

        Args:
            text: 工作内容文本
            top_k: 返回数量

        Returns:
            List of (规则, 命中关键词数) 按命中数降序
        """
        logger.debug(f"关键词匹配: text={text[:30]}...")

        text_lower = text.lower()
        cursor = self.conn.cursor()
        all_rules = cursor.execute("SELECT * FROM rules").fetchall()

        scored = []
        for row in all_rules:
            rule = self._row_to_rule(row)
            kw_set = rule.keyword_set

            # 计算命中分数
            hits = 0
            for kw in kw_set:
                if kw.lower() in text_lower:
                    hits += 1
                elif len(kw) > 3 and any(word in text_lower for word in kw.lower().split()):
                    hits += 0.5

            if hits > 0:
                scored.append((rule, hits))

        scored.sort(key=lambda x: x[1], reverse=True)
        result = scored[:top_k]
        logger.debug(f"关键词匹配结果: {len(result)} 条")
        return result

    def get_prefix_info(self, prefix: str) -> Optional[Dict]:
        """
        获取前缀信息

        Args:
            prefix: 前缀

        Returns:
            前缀信息字典
        """
        cursor = self.conn.cursor()
        row = cursor.execute(
            "SELECT * FROM prefix_index WHERE prefix = ?", (prefix,)
        ).fetchone()

        if row:
            return dict(row)
        return None

    def get_all_prefixes(self) -> List[Dict]:
        """获取所有前缀"""
        cursor = self.conn.cursor()
        return [dict(row) for row in cursor.execute(
            "SELECT * FROM prefix_index ORDER BY prefix"
        ).fetchall()]

    def count(self) -> int:
        """获取规则总数"""
        cursor = self.conn.cursor()
        return cursor.execute("SELECT COUNT(*) FROM rules").fetchone()[0]

    def _row_to_rule(self, row) -> QuotaRule:
        return QuotaRule(
            id=row['id'],
            code=row['code'],
            name=row['name'],
            unit=row['unit'] or '',
            prefix=row['prefix'],
            keywords=row['keywords'] or '',
            source=row['source'] or 'manual',
            confirm_count=row['confirm_count'] or 0,
            created_at=row['created_at'] or '',
            updated_at=row['updated_at'] or ''
        )

    def close(self):
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.debug("规则数据库连接已关闭")
