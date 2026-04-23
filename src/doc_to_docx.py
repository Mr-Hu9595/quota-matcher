# -*- coding: utf-8 -*-
"""
将 .doc 文件转换为 .docx 格式（保留原文件）
使用 Word COM 接口，需要 Windows + Microsoft Word
"""

import os
import sys
from pathlib import Path


def convert_doc_to_docx(doc_path: str, output_dir: str = None) -> str:
    """
    使用 Word COM 接口将 .doc 转换为 .docx

    Args:
        doc_path: .doc 文件路径
        output_dir: 输出目录，默认与原文件相同目录

    Returns:
        转换后的 .docx 文件路径
    """
    import win32com.client
    import pythoncom

    # 初始化 COM
    pythoncom.CoInitialize()

    doc_path = Path(doc_path)
    if not doc_path.exists():
        raise FileNotFoundError(f"文件不存在: {doc_path}")

    if doc_path.suffix.lower() != ".doc":
        raise ValueError(f"仅支持 .doc 文件: {doc_path}")

    # 确定输出路径
    if output_dir is None:
        output_dir = doc_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    docx_name = doc_path.stem + ".docx"
    docx_path = output_dir / docx_name

    # 避免覆盖原文件（如果 .docx 已存在）
    if docx_path.exists() and docx_path.stat().st_ino == doc_path.stat().st_ino:
        raise FileExistsError(f"源文件和目标文件相同: {docx_path}")

    word = None
    doc = None
    try:
        # 启动 Word
        word = win32com.client.Dispatch("Word.Application")
        word.Visible = False
        word.DisplayAlerts = False  # 不弹出警告对话框

        # 打开 .doc 文件
        doc = word.Documents.Open(str(doc_path.resolve()), ReadOnly=True)

        # 保存为 .docx (wdFormatXMLDocument = 16)
        doc.SaveAs(str(docx_path.resolve()), FileFormat=16)
        doc.Close(SaveChanges=False)

        print(f"转换成功: {docx_path}")
        return str(docx_path)

    finally:
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()


def batch_convert(doc_dir: str, output_dir: str = None, recursive: bool = False) -> list:
    """
    批量转换 .doc 文件

    Args:
        doc_dir: 包含 .doc 文件的目录
        output_dir: 输出目录，默认与原文件相同
        recursive: 是否递归搜索子目录

    Returns:
        成功转换的文件路径列表
    """
    doc_dir = Path(doc_dir)
    pattern = "**/*.doc" if recursive else "*.doc"

    results = []
    for doc_path in doc_dir.glob(pattern):
        try:
            result = convert_doc_to_docx(str(doc_path), output_dir)
            results.append(result)
        except Exception as e:
            print(f"转换失败 {doc_path}: {e}")

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法:")
        print("  python doc_to_docx.py <文件路径>          # 转换单个文件")
        print("  python doc_to_docx.py <目录路径>          # 批量转换")
        print("  python doc_to_docx.py <目录> -r            # 递归批量转换")
        print("  python doc_to_docx.py <文件> -o <输出目录> # 指定输出目录")
        sys.exit(1)

    output_dir = None
    recursive = False
    paths = []

    for arg in sys.argv[1:]:
        if arg == "-o" and len(paths) > 0 and output_dir is None:
            continue
        elif arg == "-o":
            continue
        elif arg == "-r":
            recursive = True
        elif arg.startswith("-"):
            continue
        elif Path(arg).is_dir() and len(paths) == 0:
            paths.append(arg)
            if len(sys.argv) > 2 and sys.argv[-2] == "-o":
                output_dir = sys.argv[-1]
        elif Path(arg).is_file() and Path(arg).suffix.lower() == ".doc":
            paths.append(arg)
            if len(sys.argv) > 2 and sys.argv[-2] == "-o":
                output_dir = sys.argv[-1]
        else:
            paths.append(arg)

    if not paths:
        print("错误: 请指定文件或目录路径")
        sys.exit(1)

    for path_str in paths:
        path = Path(path_str)
        if path.is_file():
            try:
                convert_doc_to_docx(path_str, output_dir)
            except Exception as e:
                print(f"错误: {e}")
        elif path.is_dir():
            results = batch_convert(path_str, output_dir, recursive)
            print(f"\n共成功转换 {len(results)} 个文件")
        else:
            print(f"路径不存在: {path_str}")
