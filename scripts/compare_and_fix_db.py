#!/usr/bin/env python3
"""全面对比定额TXT原始文件和SQLite数据库，修复任何不一致"""
import sqlite3
import re
import os
from datetime import datetime

DB_PATH = 'db/quota.db'
TXT_DIR = 'db/定额'

LINE_PATTERN = re.compile(r'^(\d+-\d+-\d+)\t(.+?)\t(\S+)\t([\d.]+)')

def parse_txt_file(filepath):
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LINE_PATTERN.match(line)
            if m:
                code, name, unit, price = m.groups()
                records.append({
                    'code': code,
                    'name': name,
                    'unit': unit,
                    'price': float(price),
                })
    return records

# Profession mapping
PROFESSION_MAP = {
    '河南省通用安装工程预算定额2016.txt': '河南省安装工程',
    '河南省市政工程预算定额2016.txt': '河南省市政工程',
    '河南省房屋建筑与装饰工程预算定额2016.txt': '河南省房屋建筑与装饰工程',
    '河南省城市轨道交通工程预算定额2019.txt': '河南省城市轨道交通工程',
    '河南省城市地下综合管廊工程预算定额2019.txt': '河南省城市地下综合管廊工程',
    '河南省绿色建筑工程预算定额2019.txt': '河南省绿色建筑工程',
    '河南省装配式建筑工程预算定额2019.txt': '河南省装配式建筑工程',
    '河南省市政公用设施养护维修预算定额2020.txt': '河南省市政公用设施养护维修',
}

# Load all TXT records
all_txt_records = []
for filename, profession in PROFESSION_MAP.items():
    filepath = os.path.join(TXT_DIR, filename)
    records = parse_txt_file(filepath)
    for r in records:
        r['profession'] = profession
        r['source_file'] = filename
    all_txt_records.extend(records)
    print(f'TXT {filename}: {len(records)} records')

print(f'\nTotal TXT records: {len(all_txt_records)}')

# Load DB records
conn = sqlite3.connect(DB_PATH)
conn.text_factory = str
cursor = conn.cursor()
cursor.execute('SELECT code, name, unit, price, profession FROM quotas')
db_by_code_prof = {(row[0], row[4]): {'name': row[1], 'unit': row[2], 'price': row[3]} for row in cursor.fetchall()}
cursor.execute('SELECT profession, COUNT(*) FROM quotas GROUP BY profession')
for row in cursor.fetchall():
    print(f'DB {row[0]}: {row[1]} records')

cursor.execute('SELECT COUNT(*) FROM quotas')
print(f'\nTotal DB records: {cursor.fetchone()[0]}')

# Build TXT index
txt_index = {(r['code'], r['profession']): r for r in all_txt_records}

# Compare
txt_codes = set(txt_index.keys())
db_codes = set(db_by_code_prof.keys())

missing_in_db = txt_codes - db_codes
extra_in_db = db_codes - txt_codes

print(f'\nTXT has but DB missing: {len(missing_in_db)}')
print(f'DB has but TXT missing: {len(extra_in_db)}')

# Check content differences
content_diffs = []
for code, prof in txt_codes & db_codes:
    txt_r = txt_index[(code, prof)]
    db_r = db_by_code_prof[(code, prof)]
    if (txt_r['name'] != db_r['name'] or
        txt_r['unit'] != db_r['unit'] or
        abs(txt_r['price'] - db_r['price']) > 0.01):
        content_diffs.append((code, prof, txt_r, db_r))

print(f'Content differences: {len(content_diffs)}')

# Detail by profession
print('\n=== By Profession ===')
txt_by_prof = {}
for r in all_txt_records:
    prof = r['profession']
    if prof not in txt_by_prof:
        txt_by_prof[prof] = []
    txt_by_prof[prof].append(r)

for filename, profession in PROFESSION_MAP.items():
    txt_count = len(txt_by_prof.get(profession, []))
    db_count = sum(1 for c, p in db_codes if p == profession)
    missing = sum(1 for c, p in missing_in_db if p == profession)
    extra = sum(1 for c, p in extra_in_db if p == profession)
    diffs = sum(1 for c, p, _, _ in content_diffs if p == profession)
    status = 'OK' if (txt_count == db_count and missing == 0 and extra == 0 and diffs == 0) else 'MISMATCH'
    print(f'{status} {profession}: TXT={txt_count}, DB={db_count}, missing={missing}, extra={extra}, diff={diffs}')

# Show first 20 missing records
if missing_in_db:
    print('\n=== Missing in DB (first 20) ===')
    sorted_missing = sorted(missing_in_db, key=lambda x: (x[1], x[0]))
    for code, prof in sorted_missing[:20]:
        r = txt_index[(code, prof)]
        print(f'  {code} | {prof} | {r["name"][:50]} | {r["unit"]} | {r["price"]}')

# Show first 20 extra records
if extra_in_db:
    print('\n=== Extra in DB (first 20) ===')
    sorted_extra = sorted(extra_in_db, key=lambda x: (x[1], x[0]))
    for code, prof in sorted_extra[:20]:
        r = db_by_code_prof[(code, prof)]
        print(f'  {code} | {prof} | {r["name"][:50]} | {r["unit"]} | {r["price"]}')

conn.close()

# Fix database
if missing_in_db or extra_in_db or content_diffs:
    print('\n=== Fixing Database ===')
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    cursor = conn.cursor()

    # Backup
    backup_path = f'{DB_PATH}.fixbackup'
    import shutil
    shutil.copy(DB_PATH, backup_path)
    print(f'Backup: {backup_path}')

    # Delete extra
    if extra_in_db:
        for code, prof in extra_in_db:
            cursor.execute('DELETE FROM quotas WHERE code=? AND profession=?', (code, prof))
        print(f'Deleted {len(extra_in_db)} extra records')

    # Update content diffs
    if content_diffs:
        for code, prof, txt_r, db_r in content_diffs:
            cursor.execute('UPDATE quotas SET name=?, unit=?, price=? WHERE code=? AND profession=?',
                          (txt_r['name'], txt_r['unit'], txt_r['price'], code, prof))
        print(f'Updated {len(content_diffs)} content diff records')

    # Insert missing
    if missing_in_db:
        for code, prof in missing_in_db:
            r = txt_index[(code, prof)]
            cursor.execute('''INSERT INTO quotas (code, name, unit, price, profession, source_file)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                          (r['code'], r['name'], r['unit'], r['price'], r['profession'], r['source_file']))
        print(f'Inserted {len(missing_in_db)} missing records')

    conn.commit()

    # Verify
    cursor.execute('SELECT COUNT(*) FROM quotas')
    new_count = cursor.fetchone()[0]
    expected = len(all_txt_records)
    print(f'\nDB now has {new_count} records (expected {expected})')
    if new_count == expected:
        print('SUCCESS: Database matches TXT files!')
    else:
        print(f'WARNING: Count mismatch!')

    conn.close()
else:
    print('\nNo differences found - database is correct!')