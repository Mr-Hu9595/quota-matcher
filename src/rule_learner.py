"""
规则自动学习模块 - SQLite + 向量库混合架构

架构：
- SQLite: 精确规则存储（前缀索引、关键词索引）
- 向量库: 语义相似度搜索（辅助）
- 自动学习: 用户确认后写入SQLite

使用方式：
    from src.rule_learner import RuleLearner

    learner = RuleLearner()

    # 精确匹配（主）
    results = learner.match_exact("电力电缆敷设")

    # 向量搜索（辅助）
    results = learner.match_vector("安装一根10kV电力电缆")

    # 学习新规则
    learner.learn(code="4-9-XXX", name="定额名称", unit="10m", keywords=["关键词"])
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# 规则库路径
RULES_DIR = Path(__file__).parent.parent / "规则库"
RULES_DB = RULES_DIR / "rules.db"
RULES_JSON = RULES_DIR / "定额匹配规则库.json"


@dataclass
class QuotaRule:
    """定额规则数据类"""
    id: Optional[int] = None
    code: str = ""           # 定额编号，如 4-9-159
    name: str = ""           # 定额名称
    unit: str = ""           # 单位
    prefix: str = ""         # 前缀，如 4-9
    keywords: str = ""       # 关键词（逗号分隔存储）
    source: str = "manual"   # 来源：manual/excel/auto
    confirm_count: int = 0   # 被确认次数
    created_at: str = ""      # 创建时间
    updated_at: str = ""     # 更新时间

    @property
    def keywords_list(self) -> List[str]:
        return [k.strip() for k in self.keywords.split(',') if k.strip()]

    @property
    def keyword_set(self) -> set:
        return set(self.keywords_list)


class RuleDatabase:
    """规则数据库管理"""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or RULES_DB)
        self._conn = None
        self._init_db()

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """初始化数据库表"""
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

    def insert_rule(self, code: str, name: str, unit: str, keywords: List[str],
                    prefix: str = None, source: str = "manual") -> int:
        """插入规则"""
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
        return rule_id

    def get_rule(self, code: str) -> Optional[QuotaRule]:
        """根据编号获取规则"""
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM rules WHERE code = ?", (code,)).fetchone()
        if row:
            return self._row_to_rule(row)
        return None

    def get_rules_by_prefix(self, prefix: str) -> List[QuotaRule]:
        """根据前缀获取规则"""
        cursor = self.conn.cursor()
        rows = cursor.execute("SELECT * FROM rules WHERE prefix = ? ORDER BY code", (prefix,)).fetchall()
        return [self._row_to_rule(row) for row in rows]

    def match_by_keywords(self, text: str, top_k: int = 10) -> List[Tuple[QuotaRule, int]]:
        """
        根据关键词匹配规则

        Returns:
            List of (规则, 命中关键词数) 按命中数降序
        """
        text_lower = text.lower()
        text_words = set(text_lower.split())

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
        return scored[:top_k]

    def increment_confirm(self, code: str):
        """增加规则确认次数"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE rules SET confirm_count = confirm_count + 1, updated_at = ?
            WHERE code = ?
        """, (datetime.now().isoformat(), code))
        self.conn.commit()

    def get_prefix_info(self, prefix: str) -> Optional[Dict]:
        """获取前缀信息"""
        cursor = self.conn.cursor()
        row = cursor.execute("SELECT * FROM prefix_index WHERE prefix = ?", (prefix,)).fetchone()
        if row:
            return dict(row)
        return None

    def get_all_prefixes(self) -> List[Dict]:
        """获取所有前缀"""
        cursor = self.conn.cursor()
        return [dict(row) for row in cursor.execute("SELECT * FROM prefix_index ORDER BY prefix").fetchall()]

    def get_all_rules(self) -> List[QuotaRule]:
        """获取所有规则"""
        cursor = self.conn.cursor()
        return [self._row_to_rule(row) for row in cursor.execute("SELECT * FROM rules ORDER BY code").fetchall()]

    def get_rule_count(self) -> int:
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
        if self._conn:
            self._conn.close()
            self._conn = None


class RuleLearner:
    """
    规则自动学习器 - 混合架构

    精确匹配流程（主）：
    1. 关键词分词
    2. SQLite 关键词索引命中
    3. 前缀筛选
    4. 排序返回

    向量搜索流程（辅）：
    1. 工作内容向量化
    2. ChromaDB 语义相似度搜索
    3. 返回候选
    """

    def __init__(self, db_path: str = None):
        self.db = RuleDatabase(db_path)
        self._vector_store = None  # 延迟加载

    @property
    def vector_store(self):
        """延迟加载向量存储"""
        if self._vector_store is None:
            from src.vector_store import VectorStore
            self._vector_store = VectorStore()
        return self._vector_store

    def learn(self, code: str, name: str, unit: str, keywords: List[str],
              source: str = 'manual') -> QuotaRule:
        """
        学习并收录新规则

        Args:
            code: 定额编号
            name: 定额名称
            unit: 单位
            keywords: 关键词列表
            source: 来源 (manual/excel/auto)

        Returns:
            创建的规则对象
        """
        self.db.insert_rule(code, name, unit, keywords, source=source)
        return self.db.get_rule(code)

    def learn_from_excel_row(self, row_data: Dict) -> Optional[QuotaRule]:
        """
        从Excel行数据学习规则

        Args:
            row_data: 包含 code, name, unit, keywords 的字典

        Returns:
            创建的规则或None
        """
        code = row_data.get('code', '')
        name = row_data.get('name', '')
        unit = row_data.get('unit', '')
        keywords = row_data.get('keywords', [])

        if not code or not name:
            return None

        code = str(code).strip()
        name = str(name).strip()
        unit = str(unit).strip() if unit else ''

        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(',')]

        return self.learn(code, name, unit, keywords, source='excel')

    def match(self, work_content: str, top_k: int = 10) -> List[Tuple[QuotaRule, int, float]]:
        """
        精确匹配（主流程）

        Args:
            work_content: 工作内容描述
            top_k: 返回前k个结果

        Returns:
            List of (规则, 关键词命中数, 向量相似度) 按综合分数降序
        """
        # 1. 关键词精确匹配
        keyword_matches = self.db.match_by_keywords(work_content, top_k * 2)

        # 2. 向量搜索（辅助）
        try:
            vector_results = self.vector_store.search(work_content, top_k=top_k * 2, api_key=None)
            vector_score_map = {r.get('code'): r.get('score', 0) for r in vector_results}
        except Exception:
            vector_score_map = {}

        # 3. 合并结果
        seen_codes = set()
        results = []

        # 优先排列关键词高命中
        for rule, hits in keyword_matches:
            if rule.code in seen_codes:
                continue
            seen_codes.add(rule.code)

            vec_score = vector_score_map.get(rule.code, 0)
            # 综合分数 = 关键词命中 * 0.7 + 向量分数 * 0.3
            combined = hits * 0.7 + vec_score * 0.3
            results.append((rule, hits, vec_score, combined))

        # 添加纯向量匹配（关键词未命中的）
        for r in vector_results:
            code = r.get('code')
            if code and code not in seen_codes:
                seen_codes.add(code)
                vec_score = r.get('score', 0)
                # 从数据库获取规则完整信息
                rule = self.db.get_rule(code)
                if rule:
                    results.append((rule, 0, vec_score, vec_score * 0.3))

        # 4. 按综合分数排序
        results.sort(key=lambda x: x[3], reverse=True)
        return [(r[0], r[1], r[2]) for r in results[:top_k]]

    def match_exact(self, work_content: str, prefix: str = None, top_k: int = 10) -> List[Tuple[QuotaRule, int]]:
        """
        纯精确匹配（不使用向量）

        Args:
            work_content: 工作内容描述
            prefix: 前缀筛选（可选）
            top_k: 返回前k个结果

        Returns:
            List of (规则, 关键词命中数)
        """
        results = self.db.match_by_keywords(work_content, top_k * 2)

        if prefix:
            results = [(r, h) for r, h in results if r.prefix == prefix]

        return results[:top_k]

    def match_vector(self, work_content: str, prefix: str = None, top_k: int = 10) -> List[Dict]:
        """
        纯向量匹配

        Args:
            work_content: 工作内容描述
            prefix: 前缀筛选（可选）
            top_k: 返回前k个结果

        Returns:
            向量搜索结果列表
        """
        try:
            results = self.vector_store.search(work_content, top_k=top_k, api_key=None)

            if prefix:
                # 根据prefix筛选
                prefix_collections = {
                    '4-9': 'quota_HENAN_1', '4-12': 'quota_HENAN_1', '4-7': 'quota_HENAN_1',
                    '4-6': 'quota_HENAN_1', '4-10': 'quota_HENAN_1', '4-14': 'quota_HENAN_1',
                    '4-2': 'quota_HENAN_1', '4-17': 'quota_HENAN_1',
                    '5-2': 'quota_HENAN_2', '5-5': 'quota_HENAN_2', '5-6': 'quota_HENAN_2',
                    '9-4': 'quota_HENAN_3', '9-5': 'quota_HENAN_3',
                }
                collection_name = prefix_collections.get(prefix)
                if collection_name:
                    results = [r for r in results if r.get('collection') == collection_name]

            return results[:top_k]
        except Exception as e:
            print(f"向量搜索失败: {e}")
            return []

    def confirm_rule(self, code: str):
        """确认使用某规则（增加置信度）"""
        self.db.increment_confirm(code)

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_rules': self.db.get_rule_count(),
            'prefixes': self.db.get_all_prefixes(),
            'top_rules': self._get_top_confirmed()
        }

    def _get_top_confirmed(self, limit: int = 10) -> List[Dict]:
        """获取确认次数最多的规则"""
        cursor = self.db.conn.cursor()
        rows = cursor.execute("""
            SELECT code, name, unit, confirm_count
            FROM rules
            ORDER BY confirm_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def export_to_json(self, json_path: str = None):
        """导出规则到JSON"""
        if json_path is None:
            json_path = str(RULES_JSON)

        rules = self.db.get_all_rules()
        prefixes = self.db.get_all_prefixes()

        data = {
            'schema_version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'prefix_index': {p['prefix']: {'name': p['name'], 'category': p['category']} for p in prefixes},
            'rules': [
                {
                    'code': r.code,
                    'name': r.name,
                    'unit': r.unit,
                    'prefix': r.prefix,
                    'keywords': r.keywords_list,
                    'source': r.source,
                    'confirm_count': r.confirm_count
                }
                for r in rules
            ],
            'stats': {
                'total_rules': len(rules),
                'prefix_count': len(prefixes)
            }
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def close(self):
        self.db.close()


# 便捷函数
_learner_instance = None

def get_learner() -> RuleLearner:
    """获取全局规则学习器实例"""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = RuleLearner()
    return _learner_instance

def match_rules(work_content: str, top_k: int = 10) -> List[Tuple[QuotaRule, int, float]]:
    """匹配规则快捷函数"""
    return get_learner().match(work_content, top_k)

def learn_rule(code: str, name: str, unit: str, keywords: List[str]) -> QuotaRule:
    """学习新规则快捷函数"""
    return get_learner().learn(code, name, unit, keywords)
