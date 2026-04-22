#!/usr/bin/env python3
"""
构建向量索引脚本

从 db/ 目录加载河南省各专业定额数据，
构建 SQLite + ChromaDB 向量索引，保存到 db/ 目录。

用法:
    python scripts/build_vector_index.py              # 使用本地模型，构建全部专业
    python scripts/build_vector_index.py --api-key YOUR_KEY  # 使用 MiniMax API
    python scripts/build_vector_index.py --append      # 追加新专业到现有索引
    python scripts/build_vector_index.py --rebuild     # 完全重建（清空现有数据）
    python scripts/build_vector_index.py --chm        # 仅处理 CHM 文件
"""

import sys
import os
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quota_loader import QuotaLoader
from src.vector_store import VectorStore
from src.chm_parser import ChmParser


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
        help="定额文件路径（单文件模式）"
    )
    parser.add_argument(
        "--profession",
        type=str,
        default=None,
        help="专业名称"
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
    parser.add_argument(
        "--append",
        action="store_true",
        help="追加模式：不删除现有数据，只追加新数据"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="完全重建模式：先删除现有数据库再重建"
    )
    parser.add_argument(
        "--chm",
        action="store_true",
        help="仅处理 CHM 文件（章节说明和勘误）"
    )
    parser.add_argument(
        "--chm-only",
        action="store_true",
        help="仅构建 CHM 向量索引"
    )
    args = parser.parse_args()

    # 确定路径
    project_root = Path(__file__).parent.parent
    db_dir = project_root / "db"
    quota_dir = db_dir / "定额"
    db_dir.mkdir(exist_ok=True)

    db_path = args.db_path or str(db_dir / "quota.db")
    chroma_path = args.chroma_path or str(db_dir / "chroma_data")

    # 8个专业定额文件列表（使用全称专业名）
    quota_files = [
        ("db/定额/河南省通用安装工程预算定额2016.txt", "河南省安装工程"),
        ("db/定额/河南省市政工程预算定额2016.txt", "河南省市政工程"),
        ("db/定额/河南省房屋建筑与装饰工程预算定额2016.txt", "河南省房屋建筑与装饰工程"),
        ("db/定额/河南省城市轨道交通工程预算定额2019.txt", "河南省城市轨道交通工程"),
        ("db/定额/河南省城市地下综合管廊工程预算定额2019.txt", "河南省城市地下综合管廊工程"),
        ("db/定额/河南省绿色建筑工程预算定额2019.txt", "河南省绿色建筑工程"),
        ("db/定额/河南省装配式建筑工程预算定额2019.txt", "河南省装配式建筑工程"),
        ("db/定额/河南省市政公用设施养护维修预算定额2020.txt", "河南省市政公用设施养护维修"),
    ]

    # CHM 文件
    chm_files = [
        ("db/定额/河南定额章节说明.chm", "chapter_notes"),
        ("db/定额/河南省相关文件及勘误.chm", "errata"),
    ]

    # 处理 CHM 模式
    if args.chm or args.chm_only:
        print("=" * 60)
        print("CHM 文件处理模式")
        print("=" * 60)

        vs = VectorStore(db_path=db_path, chroma_path=chroma_path)
        parser = ChmParser()

        for chm_path, chm_type in chm_files:
            full_path = project_root / chm_path
            if not full_path.exists():
                print(f"  [SKIP] {chm_path} (文件不存在)")
                continue

            print(f"\n处理: {chm_path}")

            if chm_type == "chapter_notes":
                print("  提取章节说明...")
                notes = parser.extract_chapter_notes(str(full_path))
                print(f"    提取到 {len(notes)} 条章节说明")

                if notes and not args.chm_only:
                    print("    存入 SQLite...")
                    vs.build_chapter_notes_index(notes, api_key=args.api_key)

            elif chm_type == "errata":
                print("  提取勘误信息...")
                errata = parser.extract_errata(str(full_path))
                print(f"    提取到 {len(errata)} 条勘误")

                if errata and not args.chm_only:
                    print("    存入 SQLite...")
                    vs.build_errata_index(errata, api_key=args.api_key)

        if args.chm or args.chm_only:
            print("\nCHM 处理完成！")
            return

    # 确定加载模式
    if args.quota_file:
        # 单文件模式
        profession = args.profession
        all_quotas = []
        loader = QuotaLoader(quota_file=args.quota_file, profession=profession)
        quotas = loader.load()
        all_quotas.extend(quotas)
        print(f"从 {args.quota_file} 加载 {len(quotas)} 条定额（专业：{loader.get_profession()}）")
    else:
        # 全量多专业模式
        all_quotas = []
        print("待加载专业定额文件：")
        for file_path, profession in quota_files:
            full_path = project_root / file_path
            if full_path.exists():
                loader = QuotaLoader(quota_file=str(full_path), profession=profession)
                quotas = loader.load()
                all_quotas.extend(quotas)
                print(f"  [OK] {profession}: {len(quotas)} 条")
            else:
                print(f"  [SKIP] {file_path} (文件不存在)")
        print()

    if not all_quotas and not args.chm:
        print("错误: 未找到有效定额数据")
        sys.exit(1)

    if all_quotas:
        print(f"共加载 {len(all_quotas)} 条定额")

    # 初始化向量存储
    print(f"\n初始化向量存储...")
    print(f"  SQLite: {db_path}")
    print(f"  ChromaDB: {chroma_path}")
    if args.rebuild:
        print(f"  模式: 完全重建")
    elif args.append:
        print(f"  模式: 追加")
    else:
        print(f"  模式: 覆盖")

    vs = VectorStore(db_path=db_path, chroma_path=chroma_path)

    # 完全重建模式：先删除现有数据库
    if args.rebuild:
        print("\n[警告] 完全重建模式将清空现有数据库！")

        # 删除 SQLite 数据
        try:
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM quotas")
            cursor.execute("DELETE FROM chapter_notes")
            cursor.execute("DELETE FROM errata")
            conn.commit()
            conn.close()
            print("  SQLite 数据已清空")
        except Exception as e:
            print(f"  清空 SQLite 失败: {e}")

        # 删除 ChromaDB collections
        try:
            for collection_name in vs.COLLECTION_NAMES.values():
                try:
                    vs.chroma_client.delete_collection(name=collection_name)
                    print(f"  已删除 Collection: {collection_name}")
                except Exception:
                    pass
            # 清理缓存
            vs._collections = {}
            print("  ChromaDB Collections 已清空")
        except Exception as e:
            print(f"  清空 ChromaDB 失败: {e}")

        # 重新初始化
        vs.init_db()

    # 构建索引
    if all_quotas:
        print(f"\n开始构建向量索引...")
        if args.api_key:
            print("使用 MiniMax API 生成向量")
        else:
            print("使用本地 sentence-transformers 生成向量（推荐）")

        vs.build_index(all_quotas, api_key=args.api_key, append=args.append)

    # 处理 CHM 文件
    if args.chm:
        print("\n" + "=" * 60)
        print("处理 CHM 文件...")
        print("=" * 60)

        parser = ChmParser()
        for chm_path, chm_type in chm_files:
            full_path = project_root / chm_path
            if not full_path.exists():
                print(f"  [SKIP] {chm_path} (文件不存在)")
                continue

            print(f"\n处理: {chm_path}")

            if chm_type == "chapter_notes":
                print("  提取章节说明...")
                notes = parser.extract_chapter_notes(str(full_path))
                print(f"    提取到 {len(notes)} 条章节说明")
                if notes:
                    vs.build_chapter_notes_index(notes, api_key=args.api_key)

            elif chm_type == "errata":
                print("  提取勘误信息...")
                errata = parser.extract_errata(str(full_path))
                print(f"    提取到 {len(errata)} 条勘误")
                if errata:
                    vs.build_errata_index(errata, api_key=args.api_key)

    # 验证
    print("\n" + "=" * 60)
    print("验证结果")
    print("=" * 60)

    # 验证数据库中的专业分布
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT profession, COUNT(*) FROM quotas GROUP BY profession")
        print("\n各专业定额数量：")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} 条")

        cursor.execute("SELECT COUNT(*) FROM chapter_notes")
        print(f"\n章节说明: {cursor.fetchone()[0]} 条")

        cursor.execute("SELECT COUNT(*) FROM errata")
        print(f"勘误: {cursor.fetchone()[0]} 条")

        conn.close()
    except Exception as e:
        print(f"数据库验证失败: {e}")

    # 测试搜索
    if all_quotas:
        print("\n测试搜索 '电力电缆':")
        results = vs.search("电力电缆", top_k=3, api_key=args.api_key)
        for r in results:
            print(f"  - {r.get('code')}: {r.get('name')} ({r.get('unit')})")

    print("\n完成！")


if __name__ == "__main__":
    main()
