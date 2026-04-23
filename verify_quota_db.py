#!/usr/bin/env python3
"""全面对比TXT定额原始文件与SQLite数据库的完整性和一致性"""
import sqlite3
import re
import os
import shutil
from collections import defaultdict

DB_PATH = 'db/quota.db'
TXT_DIR = 'db/定额'

# Line pattern: code TAB name TAB unit TAB price
# Code format: X-X-X (3 parts) or X-XX (2 parts but stored as X-0XX)
LINE_PATTERN = re.compile(r'^(\d+-\d+(?:-\d+)?)\t(.+?)\t(\S+)\t([\d.]+)')

def parse_txt_file(filepath):
    """解析TXT文件，返回定额记录列表"""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LINE_PATTERN.match(line)
            if m:
                code, name, unit, price = m.groups()
                # Normalize code format - ensure 3 parts
                parts = code.split('-')
                if len(parts) == 2:
                    # Convert X-XX to X-0-XX format for consistency
                    code = f"{parts[0]}-0{parts[1]}"
                records.append({
                    'code': code,
                    'name': name,
                    'unit': unit,
                    'price': float(price),
                })
    return records

def get_profession_from_filename(filename):
    """从文件名推断专业名称"""
    name_map = {
        '通用安装': '河南省安装工程',
        '市政工程': '河南省市政工程',
        '房屋建筑': '河南省房屋建筑与装饰工程',
        '城市轨道交通': '河南省城市轨道交通工程',
        '城市地下综合管廊': '河南省城市地下综合管廊工程',
        '绿色建筑': '河南省绿色建筑工程',
        '装配式建筑': '河南省装配式建筑工程',
        '市政公用设施养护维修': '河南省市政公用设施养护维修',
    }
    for key, prof in name_map.items():
        if key in filename:
            return prof
    return None

# Load all TXT records
print("=" * 70)
print("解析TXT原始文件")
print("=" * 70)

txt_files = [f for f in os.listdir(TXT_DIR) if f.endswith('.txt')]
txt_records = {}  # {(code, profession): record}
txt_by_prof = defaultdict(list)

for filename in sorted(txt_files):
    filepath = os.path.join(TXT_DIR, filename)
    profession = get_profession_from_filename(filename)
    records = parse_txt_file(filepath)
    print(f"TXT {filename}")
    print(f"      专业: {profession}, 定额数: {len(records)}")
    for r in records:
        r['profession'] = profession
        r['source_file'] = filename
        txt_records[(r['code'], profession)] = r
        txt_by_prof[profession].append(r)

print(f"\nTXT总计: {len(txt_records)}条记录")

# Load DB records
print("\n" + "=" * 70)
print("加载数据库记录")
print("=" * 70)

conn = sqlite3.connect(DB_PATH)
conn.text_factory = str
cursor = conn.cursor()

cursor.execute('SELECT code, name, unit, price, profession FROM quotas')
db_records = {(row[0], row[4]): {'name': row[1], 'unit': row[2], 'price': row[3]}
               for row in cursor.fetchall()}

# Count by profession
db_by_prof = defaultdict(list)
for (code, prof), data in db_records.items():
    db_by_prof[prof].append(code)

print(f"DB总计: {len(db_records)}条记录\n")
for prof in sorted(db_by_prof.keys()):
    print(f"  {prof}: {len(db_by_prof[prof])}条")

# Compare
print("\n" + "=" * 70)
print("详细对比")
print("=" * 70)

txt_codes = set(txt_records.keys())
db_codes = set(db_records.keys())

missing_in_db = txt_codes - db_codes  # TXT有DB没有
extra_in_db = db_codes - txt_codes   # DB有TXT没有

print(f"\nTXT有但DB没有: {len(missing_in_db)}条")
print(f"DB有但TXT没有: {len(extra_in_db)}条")

# Check content differences in common records
content_diffs = []
for code, prof in txt_codes & db_codes:
    txt_r = txt_records[(code, prof)]
    db_r = db_records[(code, prof)]
    if (txt_r['name'] != db_r['name'] or
        txt_r['unit'] != db_r['unit'] or
        abs(txt_r['price'] - db_r['price']) > 0.01):
        content_diffs.append((code, prof, txt_r, db_r))

print(f"内容有差异: {len(content_diffs)}条")

# Detail comparison by profession
print("\n" + "-" * 70)
print("按专业详细对比")
print("-" * 70)

all_profs = sorted(set(txt_by_prof.keys()) | set(db_by_prof.keys()))

for prof in all_profs:
    txt_count = len(txt_by_prof.get(prof, []))
    db_count = len(db_by_prof.get(prof, []))
    missing = sum(1 for c, p in missing_in_db if p == prof)
    extra = sum(1 for c, p in extra_in_db if p == prof)
    diffs = sum(1 for c, p, _, _ in content_diffs if p == prof)

    if txt_count == db_count and missing == 0 and extra == 0 and diffs == 0:
        status = "✓ OK"
    else:
        status = "✗ 不一致"

    print(f"\n{status} {prof}")
    print(f"  TXT记录数: {txt_count}")
    print(f"  DB记录数:  {db_count}")
    if missing > 0:
        print(f"  TXT有DB无: {missing}条")
    if extra > 0:
        print(f"  DB有TXT无: {extra}条")
    if diffs > 0:
        print(f"  内容差异: {diffs}条")

    # Show sample differences
    if missing > 0 and missing <= 10:
        print(f"  缺失记录:")
        missing_list = [(c, p) for c, p in missing_in_db if p == prof]
        for code, _ in sorted(missing_list):
            r = txt_records[(code, prof)]
            print(f"    {code} | {r['name'][:40]} | {r['unit']} | {r['price']}")

    if extra > 0 and extra <= 10:
        print(f"  多余记录:")
        extra_list = [(c, p) for c, p in extra_in_db if p == prof]
        for code, _ in sorted(extra_list):
            r = db_records[(code, prof)]
            print(f"    {code} | {r['name'][:40]} | {r['unit']} | {r['price']}")

# Show content diffs
if content_diffs:
    print("\n" + "-" * 70)
    print("内容差异详情 (前20条)")
    print("-" * 70)
    for code, prof, txt_r, db_r in content_diffs[:20]:
        print(f"\n{code} | {prof}")
        print(f"  TXT: {txt_r['name'][:60]} | {txt_r['unit']} | {txt_r['price']}")
        print(f"  DB:  {db_r['name'][:60]} | {db_r['unit']} | {db_r['price']}")

conn.close()

# Summary
print("\n" + "=" * 70)
print("对比结果摘要")
print("=" * 70)
if not missing_in_db and not extra_in_db and not content_diffs:
    print("✓ 数据库与TXT原始文件完全一致!")
else:
    print(f"不一致项:")
    if missing_in_db:
        print(f"  - 缺失: {len(missing_in_db)}条 (TXT有DB无)")
    if extra_in_db:
        print(f"  - 多余: {len(extra_in_db)}条 (DB有TXT无)")
    if content_diffs:
        print(f"  - 差异: {len(content_diffs)}条 (内容不同)")