#!/usr/bin/env python3
"""移动源代码到 src/ 目录"""

import shutil
from pathlib import Path

src_dir = Path(__file__).parent.parent
dst_dir = src_dir / "src"

# 需要移动的文件
files_to_move = [
    "quota_matcher.py",
    "quota_loader.py",
    "local_matcher.py",
    "minimax_matcher.py",
    "vector_store.py",
    "file_parser.py",
    "column_identifier.py",
    "unit_converter.py",
    "quantity_extractor.py",
    "claude_matcher.py",
    "doc_to_docx.py",
]

print(f"源目录: {src_dir}")
print(f"目标目录: {dst_dir}")

# 确保目标目录存在
dst_dir.mkdir(exist_ok=True)

# 移动文件
for fname in files_to_move:
    src_path = src_dir / fname
    dst_path = dst_dir / fname
    if src_path.exists():
        shutil.move(str(src_path), str(dst_path))
        print(f"移动: {fname}")
    else:
        print(f"跳过(不存在): {fname}")

print("\n完成!")
