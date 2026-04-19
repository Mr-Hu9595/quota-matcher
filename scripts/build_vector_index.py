#!/usr/bin/env python3
"""
构建向量索引脚本

从 db/河南省通用安装工程预算定额2016.txt 加载定额数据，
构建 SQLite + ChromaDB 向量索引，保存到 db/ 目录。

用法:
    python scripts/build_vector_index.py              # 使用本地模型
    python scripts/build_vector_index.py --api-key YOUR_KEY  # 使用 MiniMax API
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quota_loader import QuotaLoader
from src.vector_store import VectorStore


def main():
    parser = argparse.ArgumentParser(description="构建定额向量索引")
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="MiniMax API Key（可选，不提供则使用本地 sentence-transformers）"
    )
    parser.add_argument(
        "--quota-file",
        type=str,
        default=None,
        help="定额文件路径（默认: db/河南省通用安装工程预算定额2016.txt）"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help="SQLite 数据库路径（默认: db/quota.db）"
    )
    parser.add_argument(
        "--chroma-path",
        type=str,
        default=None,
        help="ChromaDB 数据目录（默认: db/chroma_data）"
    )
    args = parser.parse_args()

    # 确定路径
    project_root = Path(__file__).parent.parent
    db_dir = project_root / "db"
    db_dir.mkdir(exist_ok=True)

    quota_file = args.quota_file or str(db_dir / "河南省通用安装工程预算定额2016.txt")
    db_path = args.db_path or str(db_dir / "quota.db")
    chroma_path = args.chroma_path or str(db_dir / "chroma_data")

    # 检查定额文件是否存在
    if not Path(quota_file).exists():
        print(f"错误: 定额文件不存在: {quota_file}")
        print(f"请将定额数据文件放到: {quota_file}")
        sys.exit(1)

    # 加载定额数据
    print(f"正在加载定额数据: {quota_file}")
    loader = QuotaLoader(quota_file=quota_file)
    quotas = loader.load()
    print(f"共加载 {len(quotas)} 条定额")

    if not quotas:
        print("错误: 未找到有效定额数据")
        sys.exit(1)

    # 初始化向量存储
    print(f"\n初始化向量存储...")
    print(f"  SQLite: {db_path}")
    print(f"  ChromaDB: {chroma_path}")
    vs = VectorStore(db_path=db_path, chroma_path=chroma_path)

    # 构建索引
    print(f"\n开始构建向量索引...")
    if args.api_key:
        print("使用 MiniMax API 生成向量")
    else:
        print("使用本地 sentence-transformers 生成向量（推荐）")

    vs.build_index(quotas, api_key=args.api_key)

    # 验证
    if vs.has_index():
        print(f"\n✓ 向量索引构建成功！")
        print(f"  - SQLite: {db_path}")
        print(f"  - ChromaDB: {chroma_path}")
        print(f"  - 定额数量: {len(quotas)}")

        # 测试搜索
        print("\n测试搜索 '电力电缆':")
        results = vs.search("电力电缆", top_k=3, api_key=args.api_key)
        for r in results:
            print(f"  - {r.get('code')}: {r.get('name')} ({r.get('unit')})")
    else:
        print("\n✗ 向量索引构建失败，请检查错误信息")


if __name__ == "__main__":
    main()
