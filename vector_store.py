"""
向量存储模块
使用ChromaDB实现定额名称的向量相似度搜索
配合SQLite存储定额元数据
"""

import os
import sqlite3
from typing import List, Dict, Optional
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class VectorStore:
    """向量存储模块 - SQLite + ChromaDB 双存储"""

    def __init__(self, db_path: str = None, chroma_path: str = None):
        """
        初始化向量存储

        Args:
            db_path: SQLite数据库路径，默认在skill目录下
            chroma_path: ChromaDB数据目录，默认在skill目录下
        """
        if db_path is None:
            db_path = Path(__file__).parent / "quota.db"
        if chroma_path is None:
            chroma_path = Path(__file__).parent / "chroma_data"

        self.db_path = str(db_path)
        self.chroma_path = str(chroma_path)
        self._db_conn = None

        if not CHROMADB_AVAILABLE:
            print("警告: ChromaDB未安装，向量搜索功能不可用")
            print("请运行: pip install chromadb")
            return

        # 初始化ChromaDB客户端
        os.makedirs(self.chroma_path, exist_ok=True)
        self.chroma_client = chromadb.Client(Settings(
            persist_directory=self.chroma_path,
            anonymized_telemetry=False
        ))

        # 获取或创建collection
        self.collection_name = "quota_embeddings"
        try:
            self.collection = self.chroma_client.get_collection(name=self.collection_name)
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Quota name embeddings for similarity search"}
            )

    def has_index(self) -> bool:
        """检查向量索引是否存在"""
        if not CHROMADB_AVAILABLE:
            return False
        try:
            count = self.collection.count()
            return count > 0
        except Exception:
            return False

    @property
    def db_conn(self):
        """获取SQLite连接（懒加载）"""
        if self._db_conn is None:
            self._db_conn = sqlite3.connect(self.db_path)
            self._db_conn.row_factory = sqlite3.Row
        return self._db_conn

    def init_db(self):
        """初始化SQLite数据库表"""
        conn = self.db_conn
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quotas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                unit TEXT NOT NULL,
                price REAL,
                chapter TEXT,
                section TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_code ON quotas(code)
        """)

        conn.commit()

    def build_index(self, quotas: List[Dict], api_key: str = None):
        """
        构建向量索引

        Args:
            quotas: 定额数据列表
            api_key: MiniMax API密钥（用于生成embedding）
        """
        if not CHROMADB_AVAILABLE:
            print("错误: ChromaDB未安装，无法构建向量索引")
            return

        # 确保数据库已初始化
        self.init_db()

        # 先存储到SQLite
        conn = self.db_conn
        cursor = conn.cursor()

        # 清空旧数据
        cursor.execute("DELETE FROM quotas")
        conn.commit()

        # 插入新数据
        for quota in quotas:
            cursor.execute("""
                INSERT OR REPLACE INTO quotas (code, name, unit, price, chapter, section)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                quota.get("code"),
                quota.get("name"),
                quota.get("unit"),
                quota.get("price", 0),
                quota.get("chapter", ""),
                quota.get("section", "")
            ))

        conn.commit()

        # 生成向量并存储到ChromaDB
        print(f"正在生成 {len(quotas)} 个定额的向量...")
        for i, quota in enumerate(quotas):
            if i % 500 == 0:
                print(f"  处理进度: {i}/{len(quotas)}")

            # 生成向量
            embedding = self._get_embedding(quota.get("name", ""), api_key)
            if embedding is None:
                continue

            # 存储到ChromaDB
            doc = f"{quota.get('code')}|{quota.get('name')}|{quota.get('unit')}"

            # 先获取SQLite中的id
            cursor.execute("SELECT id FROM quotas WHERE code = ?", (quota.get("code"),))
            row = cursor.fetchone()
            if row:
                db_id = str(row["id"])
            else:
                db_id = quota.get("code")

            try:
                self.collection.add(
                    ids=[db_id],
                    embeddings=[embedding],
                    documents=[doc],
                    metadatas=[{
                        "code": quota.get("code", ""),
                        "name": quota.get("name", ""),
                        "unit": quota.get("unit", "")
                    }]
                )
            except Exception as e:
                print(f"  警告: 添加向量失败 {quota.get('code')}: {e}")

        print(f"  向量索引构建完成！共 {len(quotas)} 条")

    def _get_embedding(self, text: str, api_key: str = None) -> Optional[List[float]]:
        """
        使用MiniMax Embedding API生成向量

        Args:
            text: 待向量化的文本
            api_key: API密钥

        Returns:
            向量列表，失败返回None
        """
        if not text:
            return None

        api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            print("警告: 未设置MINIMAX_API_KEY，无法生成向量")
            return None

        try:
            import requests

            url = "https://api.minimax.chat/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "embo-01",
                "text": text
            }

            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                if "data" in result and len(result["data"]) > 0:
                    return result["data"][0].get("embedding")
            else:
                print(f"  向量生成失败: {response.status_code}")

        except Exception as e:
            print(f"  向量生成异常: {e}")

        return None

    def search(self, query: str, top_k: int = 10, api_key: str = None) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            api_key: API密钥

        Returns:
            定额详情列表
        """
        if not CHROMADB_AVAILABLE:
            print("错误: ChromaDB未安装")
            return []

        # 生成查询向量
        query_embedding = self._get_embedding(query, api_key)
        if query_embedding is None:
            print("警告: 无法生成查询向量，尝试使用关键词搜索")
            return []

        # ANN搜索
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )

            if not results or not results.get("ids"):
                return []

            # 获取详细数据
            quota_list = []
            for i, qid in enumerate(results["ids"][0]):
                # 尝试从ChromaDB获取metadata
                metadata = results.get("metadatas", [[]])[0][i] if results.get("metadatas") else {}

                # 尝试从SQLite获取详细信息
                quota = self.get_by_id(qid)
                if quota:
                    quota_list.append(quota)
                else:
                    # 使用metadata
                    quota_list.append({
                        "code": metadata.get("code", qid),
                        "name": metadata.get("name", ""),
                        "unit": metadata.get("unit", ""),
                        "score": results.get("distances", [[]])[0][i] if results.get("distances") else 0
                    })

            return quota_list

        except Exception as e:
            print(f"搜索异常: {e}")
            return []

    def get_by_id(self, id: str) -> Optional[Dict]:
        """
        根据ID获取定额详情

        Args:
            id: 定额ID（可以是数字ID或定额编号）

        Returns:
            定额信息，未找到返回None
        """
        conn = self.db_conn
        cursor = conn.cursor()

        # 先尝试按编号查询
        cursor.execute("SELECT * FROM quotas WHERE code = ?", (id,))
        row = cursor.fetchone()

        if row:
            return dict(row)

        # 再尝试按数字ID查询
        try:
            cursor.execute("SELECT * FROM quotas WHERE id = ?", (int(id),))
            row = cursor.fetchone()
            if row:
                return dict(row)
        except ValueError:
            pass

        return None

    def get_by_code(self, code: str) -> Optional[Dict]:
        """根据定额编号获取详情"""
        conn = self.db_conn
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM quotas WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def close(self):
        """关闭数据库连接"""
        if self._db_conn:
            self._db_conn.close()
            self._db_conn = None

    def __del__(self):
        """析构时关闭连接"""
        self.close()


if __name__ == "__main__":
    print("VectorStore module for quota matching")
    print("Usage:")
    print("  from vector_store import VectorStore")
    print("  vs = VectorStore()")
    print("  vs.build_index(quotas, api_key)")
    print("  results = vs.search('电缆敷设', top_k=10)")
