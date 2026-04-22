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

    # Collection 名称常量（ChromaDB 要求 ASCII 名称）
    # 格式: quota_HENAN_[ProfessionID]
    COLLECTION_NAMES = {
        "河南省安装工程": "quota_HENAN_1",
        "河南省市政工程": "quota_HENAN_2",
        "河南省房屋建筑与装饰工程": "quota_HENAN_3",
        "河南省城市轨道交通工程": "quota_HENAN_4",
        "河南省城市地下综合管廊工程": "quota_HENAN_5",
        "河南省绿色建筑工程": "quota_HENAN_6",
        "河南省装配式建筑工程": "quota_HENAN_7",
        "河南省市政公用设施养护维修": "quota_HENAN_8",
        "河南省定额章节说明": "quota_HENAN_chapter",
        "河南省相关文件及勘误": "quota_HENAN_errata",
    }

    # 专业 ID 映射（反向查找）
    PROFESSION_IDS = {v: k for k, v in COLLECTION_NAMES.items()}

    def __init__(self, db_path: str = None, chroma_path: str = None):
        """
        初始化向量存储

        Args:
            db_path: SQLite数据库路径，默认在skill目录下
            chroma_path: ChromaDB数据目录，默认在skill目录下
        """
        if db_path is None:
            db_path = Path(__file__).parent.parent / "db" / "quota.db"
        if chroma_path is None:
            chroma_path = Path(__file__).parent.parent / "db" / "chroma_data"

        self.db_path = str(db_path)
        self.chroma_path = str(chroma_path)
        self._db_conn = None
        self._collections = {}  # 缓存 Collection 对象

        if not CHROMADB_AVAILABLE:
            print("警告: ChromaDB未安装，向量搜索功能不可用")
            print("请运行: pip install chromadb")
            return

        # 初始化ChromaDB客户端（持久化）
        os.makedirs(self.chroma_path, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(
            path=self.chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )

        # 默认 Collection（向后兼容）
        self.collection_name = "quota_embeddings"
        try:
            self.collection = self.chroma_client.get_collection(name=self.collection_name)
        except Exception:
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Quota name embeddings for similarity search"}
            )

    def get_collection(self, profession: str):
        """
        获取指定专业的 Collection

        Args:
            profession: 专业名称

        Returns:
            ChromaDB Collection 对象
        """
        if not CHROMADB_AVAILABLE:
            return None

        collection_name = self.COLLECTION_NAMES.get(profession, self.collection_name)

        if collection_name not in self._collections:
            try:
                self._collections[collection_name] = self.chroma_client.get_collection(name=collection_name)
            except Exception:
                self._collections[collection_name] = self.chroma_client.create_collection(
                    name=collection_name,
                    metadata={"description": f"河南省{profession}定额向量索引", "profession": profession}
                )

        return self._collections[collection_name]

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

        # 首先检查quotas表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='quotas'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # 检查并更新表结构
            cursor.execute("PRAGMA table_info(quotas)")
            columns = [row[1] for row in cursor.fetchall()]

            # 添加缺失的列
            if 'source_file' not in columns:
                cursor.execute("ALTER TABLE quotas ADD COLUMN source_file TEXT")
            if 'profession' not in columns:
                cursor.execute("ALTER TABLE quotas ADD COLUMN profession TEXT NOT NULL DEFAULT '河南省安装工程'")
            if 'created_at' not in columns:
                cursor.execute("ALTER TABLE quotas ADD COLUMN created_at TIMESTAMP")
                cursor.execute("UPDATE quotas SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

            conn.commit()
            print("quotas表已更新")
        else:
            # 创建新表
            cursor.execute("""
                CREATE TABLE quotas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    unit TEXT NOT NULL,
                    price REAL,
                    chapter TEXT,
                    section TEXT,
                    profession TEXT NOT NULL,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(code, profession)
                )
            """)
            cursor.execute("CREATE INDEX idx_profession ON quotas(profession)")
            cursor.execute("CREATE INDEX idx_code ON quotas(code)")
            print("quotas表创建完成")

        # 创建 chapter_notes 表（如果不存在）
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chapter_notes'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE chapter_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profession TEXT NOT NULL,
                    chapter_title TEXT NOT NULL,
                    section_title TEXT,
                    content TEXT NOT NULL,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_chapter_profession ON chapter_notes(profession)")
            print("chapter_notes表创建完成")

        # 创建 errata 表（如果不存在）
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='errata'")
        if not cursor.fetchone():
            cursor.execute("""
                CREATE TABLE errata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profession TEXT NOT NULL,
                    quota_code TEXT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_file TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("CREATE INDEX idx_errata_profession ON errata(profession)")
            cursor.execute("CREATE INDEX idx_errata_quota_code ON errata(quota_code)")
            print("errata表创建完成")

        conn.commit()

    def migrate_add_profession(self):
        """迁移旧数据库，添加profession列并更新现有数据为'安装'"""
        conn = self.db_conn
        cursor = conn.cursor()

        try:
            # 检查是否已有profession列
            cursor.execute("PRAGMA table_info(quotas)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'profession' not in columns:
                cursor.execute("ALTER TABLE quotas ADD COLUMN profession TEXT NOT NULL DEFAULT '安装'")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_profession ON quotas(profession)")
                conn.commit()
                print("数据库迁移成功：已添加profession列")
            else:
                print("数据库已是最新结构")
        except Exception as e:
            print(f"数据库迁移失败: {e}")

    def build_index(self, quotas: List[Dict], api_key: str = None, append: bool = False):
        """
        构建向量索引（分Collection存储）

        Args:
            quotas: 定额数据列表
            api_key: MiniMax API密钥（用于生成embedding）
            append: 如果为True，则追加数据而非覆盖（默认False）
        """
        if not CHROMADB_AVAILABLE:
            print("错误: ChromaDB未安装，无法构建向量索引")
            return

        # 确保数据库已初始化
        self.init_db()

        # 按专业分组
        quotas_by_profession = {}
        for quota in quotas:
            profession = quota.get("profession", "河南省安装工程")
            quotas_by_profession.setdefault(profession, []).append(quota)

        # 先存储到SQLite（统一）
        conn = self.db_conn
        cursor = conn.cursor()

        if not append:
            # 清空旧数据（仅首次构建）
            cursor.execute("DELETE FROM quotas")
            conn.commit()

        # 插入新数据
        for quota in quotas:
            profession = quota.get("profession", "河南省安装工程")
            work_content = quota.get("work_content", quota.get("name", ""))
            cursor.execute("""
                INSERT OR REPLACE INTO quotas (code, name, unit, price, chapter, section, profession, source_file, work_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quota.get("code"),
                quota.get("name"),
                quota.get("unit"),
                quota.get("price", 0),
                quota.get("chapter", ""),
                quota.get("section", ""),
                profession,
                quota.get("source_file", ""),
                work_content
            ))

        conn.commit()

        # 为每个专业构建向量索引（分Collection）
        total = len(quotas)
        processed = 0

        for profession, prof_quotas in quotas_by_profession.items():
            collection = self.get_collection(profession)
            if collection is None:
                continue

            if not append:
                # 清空该专业的向量数据（通过删除并重建Collection）
                try:
                    self.chroma_client.delete_collection(name=self.COLLECTION_NAMES.get(profession, profession))
                    collection = self.chroma_client.create_collection(
                        name=self.COLLECTION_NAMES.get(profession, profession),
                        metadata={"description": f"河南省{profession}定额向量索引", "profession": profession}
                    )
                    self._collections[self.COLLECTION_NAMES.get(profession, profession)] = collection
                except Exception:
                    pass

            print(f"\n正在处理专业: {profession} ({len(prof_quotas)} 条)")

            for i, quota in enumerate(prof_quotas):
                # 生成向量（同时使用name和work_content）
                name = quota.get("name", "")
                work_content = quota.get("work_content", name)
                # 如果work_content为空，使用name
                if not work_content:
                    work_content = name
                # 组合文本用于向量化
                combined_text = f"{name} {work_content}"

                embedding = self._get_embedding(combined_text, api_key)
                if embedding is None:
                    continue

                # 构建Document格式（包含work_content）
                doc = f"[{profession}]|{quota.get('code')}|{name}|{work_content}|{quota.get('unit')}|{quota.get('chapter', '')}"

                # 构建唯一的ID（专业+编号）
                chroma_id = f"{profession}_{quota.get('code')}"

                try:
                    collection.add(
                        ids=[chroma_id],
                        embeddings=[embedding],
                        documents=[doc],
                        metadatas=[{
                            "code": quota.get("code", ""),
                            "name": name,
                            "work_content": work_content,
                            "unit": quota.get("unit", ""),
                            "profession": profession,
                            "chapter": quota.get("chapter", "")
                        }]
                    )
                except Exception as e:
                    print(f"  警告: 添加向量失败 {chroma_id}: {e}")

                processed += 1
                if (i + 1) % 500 == 0:
                    print(f"    {profession} 进度: {i+1}/{len(prof_quotas)}")

        print(f"\n向量索引构建完成！共 {processed}/{total} 条")

    def append_index(self, quotas: List[Dict], api_key: str = None):
        """
        追加定额数据到现有索引

        Args:
            quotas: 定额数据列表
            api_key: MiniMax API密钥（用于生成embedding）
        """
        return self.build_index(quotas, api_key, append=True)

    def build_chapter_notes_index(self, chapter_notes: List[Dict], api_key: str = None):
        """
        构建章节说明向量索引

        Args:
            chapter_notes: 章节说明列表
            api_key: API密钥
        """
        if not CHROMADB_AVAILABLE:
            print("错误: ChromaDB未安装")
            return

        self.init_db()
        conn = self.db_conn
        cursor = conn.cursor()

        # 插入到SQLite
        for note in chapter_notes:
            cursor.execute("""
                INSERT INTO chapter_notes (profession, chapter_title, section_title, content, source_file)
                VALUES (?, ?, ?, ?, ?)
            """, (
                note.get("profession", ""),
                note.get("chapter_title", ""),
                note.get("section_title", ""),
                note.get("content", ""),
                note.get("source_file", "")
            ))

        conn.commit()

        # 构建向量索引
        collection = self.get_collection("河南省定额章节说明")
        if collection is None:
            return

        for note in chapter_notes:
            embedding = self._get_embedding(note.get("content", ""), api_key)
            if embedding is None:
                continue

            doc = f"[章节说明]|{note.get('profession', '')}|{note.get('chapter_title', '')}|{note.get('content', '')[:200]}"
            chroma_id = f"note_{note.get('id', id(note))}"

            try:
                collection.add(
                    ids=[chroma_id],
                    embeddings=[embedding],
                    documents=[doc],
                    metadatas=[{
                        "profession": note.get("profession", ""),
                        "chapter_title": note.get("chapter_title", ""),
                        "section_title": note.get("section_title", ""),
                        "source": "chapter_notes"
                    }]
                )
            except Exception as e:
                print(f"  警告: 添加章节说明向量失败: {e}")

        print(f"章节说明索引构建完成！共 {len(chapter_notes)} 条")

    def build_errata_index(self, errata_list: List[Dict], api_key: str = None):
        """
        构建勘误向量索引

        Args:
            errata_list: 勘误列表
            api_key: API密钥
        """
        if not CHROMADB_AVAILABLE:
            print("错误: ChromaDB未安装")
            return

        self.init_db()
        conn = self.db_conn
        cursor = conn.cursor()

        # 插入到SQLite
        for errata in errata_list:
            cursor.execute("""
                INSERT INTO errata (profession, quota_code, title, content, source_file)
                VALUES (?, ?, ?, ?, ?)
            """, (
                errata.get("profession", ""),
                errata.get("quota_code", ""),
                errata.get("title", ""),
                errata.get("content", ""),
                errata.get("source_file", "")
            ))

        conn.commit()

        # 构建向量索引
        collection = self.get_collection("河南省相关文件及勘误")
        if collection is None:
            return

        for errata in errata_list:
            embedding = self._get_embedding(errata.get("content", ""), api_key)
            if embedding is None:
                continue

            doc = f"[勘误]|{errata.get('profession', '')}|{errata.get('quota_code', '')}|{errata.get('title', '')}|{errata.get('content', '')[:200]}"
            chroma_id = f"errata_{errata.get('id', id(errata))}"

            try:
                collection.add(
                    ids=[chroma_id],
                    embeddings=[embedding],
                    documents=[doc],
                    metadatas=[{
                        "profession": errata.get("profession", ""),
                        "quota_code": errata.get("quota_code", ""),
                        "title": errata.get("title", ""),
                        "source": "errata"
                    }]
                )
            except Exception as e:
                print(f"  警告: 添加勘误向量失败: {e}")

        print(f"勘误索引构建完成！共 {len(errata_list)} 条")

    def _get_embedding(self, text: str, api_key: str = None) -> Optional[List[float]]:
        """
        使用 MiniMax Embedding API 或本地模型生成向量

        Args:
            text: 待向量化的文本
            api_key: API密钥（可选）

        Returns:
            向量列表，失败返回None
        """
        if not text:
            return None

        # 优先使用 MiniMax API
        api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if api_key:
            embedding = self._get_minimax_embedding(text, api_key)
            if embedding:
                return embedding
            # MiniMax 失败，尝试本地模型

        # 本地模型兜底
        return self._get_local_embedding(text)

    def _get_minimax_embedding(self, text: str, api_key: str) -> Optional[List[float]]:
        """使用 MiniMax Embedding API 生成向量"""
        try:
            import requests

            url = "https://api.minimax.chat/v1/embeddings"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "embo-01",
                "texts": [text],
                "type": "db"
            }

            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                base_resp = result.get("base_resp", {})
                if base_resp.get("status_code") == 1008:
                    print(f"  向量生成失败: 余额不足，请充值 MiniMax API")
                    return None
                elif base_resp.get("status_code") != 0:
                    print(f"  向量生成失败: {base_resp.get('status_msg', '未知错误')}")
                    return None
                vectors = result.get("vectors")
                if vectors and len(vectors) > 0:
                    return vectors[0].get("embedding")
            else:
                print(f"  向量生成失败: HTTP {response.status_code}")

        except Exception as e:
            print(f"  向量生成异常: {e}")

        return None

    def _get_local_embedding(self, text: str) -> Optional[List[float]]:
        """使用本地 sentence-transformers 模型生成向量（模型只加载一次）"""
        try:
            from sentence_transformers import SentenceTransformer

            # 类级别缓存模型，避免重复加载
            if not hasattr(self.__class__, '_local_model'):
                print("  首次使用，加载本地模型...")
                self.__class__._local_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                print("  模型加载完成")

            embedding = self.__class__._local_model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

        except ImportError:
            print("  错误: 未安装 sentence-transformers，请运行: pip install sentence-transformers")
            return None
        except Exception as e:
            print(f"  本地向量生成异常: {e}")
            return None

    def search(self, query: str, top_k: int = 10, api_key: str = None, profession: str = None) -> List[Dict]:
        """
        向量相似度搜索

        Args:
            query: 查询文本
            top_k: 返回数量
            api_key: API密钥
            profession: 专业过滤（可选，为None则搜索所有Collection）

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

        results = []

        # 确定要搜索的Collection列表
        if profession:
            collections_to_search = [(profession, self.get_collection(profession))]
        else:
            collections_to_search = [(p, self.get_collection(p)) for p in self.COLLECTION_NAMES.keys()]

        # 搜索每个Collection
        for prof, collection in collections_to_search:
            if collection is None:
                continue

            try:
                search_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, 20)
                )

                if not search_results or not search_results.get("ids"):
                    continue

                # 获取详细数据
                for i, qid in enumerate(search_results["ids"][0]):
                    metadata = search_results.get("metadatas", [[]])[0][i] if search_results.get("metadatas") else {}

                    # 尝试从SQLite获取详细信息
                    quota = self.get_by_id(qid)
                    if quota:
                        quota["score"] = search_results.get("distances", [[]])[0][i] if search_results.get("distances") else 0
                        results.append(quota)
                    else:
                        # 使用metadata
                        results.append({
                            "code": metadata.get("code", qid),
                            "name": metadata.get("name", ""),
                            "unit": metadata.get("unit", ""),
                            "profession": metadata.get("profession", prof),
                            "chapter": metadata.get("chapter", ""),
                            "score": search_results.get("distances", [[]])[0][i] if search_results.get("distances") else 0
                        })

            except Exception as e:
                print(f"搜索 {prof} 异常: {e}")
                continue

        # 按相似度排序并返回前top_k条
        results.sort(key=lambda x: x.get("score", 0))
        return results[:top_k]

    def get_by_id(self, id: str) -> Optional[Dict]:
        """
        根据ID获取定额详情

        Args:
            id: 定额ID（可以是数字ID、定额编号或 profession_code 格式如 "河南省安装工程_1-1-1"）

        Returns:
            定额信息，未找到返回None
        """
        conn = self.db_conn
        cursor = conn.cursor()

        # 先尝试按编号查询（可能有多个专业相同编号）
        cursor.execute("SELECT * FROM quotas WHERE code = ?", (id,))
        row = cursor.fetchone()

        if row:
            return dict(row)

        # 再尝试解析 profession_code 格式（如 "河南省安装工程_1-1-1"）
        if '_' in str(id):
            parts = str(id).split('_', 1)
            if len(parts) == 2:
                profession, code = parts
                cursor.execute("SELECT * FROM quotas WHERE code = ? AND profession = ?", (code, profession))
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
