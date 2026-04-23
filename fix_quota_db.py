#!/usr/bin/env python3
"""
全面检查并修复 quota.db 数据库
要求: DB记录与TXT原始文件(包含带字母的定额)完全一致
"""
import sqlite3
import re
import os
import shutil
from datetime import datetime

DB_PATH = 'db/quota.db'
TXT_DIR = 'db/定额'

# Line pattern: code TAB name TAB unit TAB price
LINE_PATTERN = re.compile(r'^(\S+)\t(.+?)\t(\S+)\t([\d.]+)')

# Profession mapping based on filename
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

def parse_txt_file(filepath, profession):
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
                records.append({
                    'code': code,
                    'name': name,
                    'unit': unit,
                    'price': float(price),
                    'profession': profession,
                })
    return records

def load_all_txt_records():
    """加载所有TXT文件的定额记录"""
    all_records = []
    for filename, profession in PROFESSION_MAP.items():
        filepath = os.path.join(TXT_DIR, filename)
        if not os.path.exists(filepath):
            print(f'文件不存在: {filepath}')
            continue
        records = parse_txt_file(filepath, profession)
        print(f'TXT {profession}: {len(records)}条定额')
        all_records.extend(records)
    return all_records

def check_and_fix():
    print("=" * 70)
    print("加载TXT原始数据")
    print("=" * 70)
    txt_records = load_all_txt_records()
    txt_total = len(txt_records)
    print(f'\nTXT总计: {txt_total}条\n')

    # Build TXT index by (code, profession)
    txt_index = {(r['code'], r['profession']): r for r in txt_records}

    print("=" * 70)
    print("加载数据库数据")
    print("=" * 70)
    conn = sqlite3.connect(DB_PATH)
    conn.text_factory = str
    cursor = conn.cursor()

    cursor.execute('PRAGMA table_info(quotas)')
    cols = [col[1] for col in cursor.fetchall()]
    print(f'quotas表列: {cols}')

    cursor.execute('SELECT code, name, unit, price, profession FROM quotas')
    db_by_code_prof = {(row[0], row[4]): {'name': row[1], 'unit': row[2], 'price': row[3]}
                       for row in cursor.fetchall()}
    db_total = len(db_by_code_prof)
    print(f'DB总计: {db_total}条\n')

    # Compare
    txt_codes = set(txt_index.keys())
    db_codes = set(db_by_code_prof.keys())

    missing = txt_codes - db_codes  # TXT有DB没有
    extra = db_codes - txt_codes    # DB有TXT没有

    print("=" * 70)
    print("差异分析")
    print("=" * 70)
    print(f'TXT有DB没有 (缺失): {len(missing)}条')
    print(f'DB有TXT没有 (多余): {len(extra)}条')

    # Show missing by profession
    by_prof = {}
    for code, prof in missing:
        if prof not in by_prof:
            by_prof[prof] = []
        by_prof[prof].append((code, txt_index[(code, prof)]))

    print("\n缺失记录 (TXT有DB没有):")
    for prof in sorted(by_prof.keys()):
        records = by_prof[prof]
        print(f'  {prof}: {len(records)}条缺失')
        for code, rec in sorted(records)[:3]:
            print(f'    {code} | {rec["name"][:40]} | {rec["unit"]} | {rec["price"]}')

    # Check content differences
    common = txt_codes & db_codes
    content_diff = []
    for code, prof in common:
        txt_r = txt_index[(code, prof)]
        db_r = db_by_code_prof[(code, prof)]
        if (txt_r['name'] != db_r['name'] or
            txt_r['unit'] != db_r['unit'] or
            abs(txt_r['price'] - db_r['price']) > 0.01):
            content_diff.append((code, prof, txt_r, db_r))

    if content_diff:
        print(f'\n内容有差异: {len(content_diff)}条')
        for code, prof, txt_r, db_r in content_diff[:3]:
            print(f'  {code} | {prof}')
            print(f'    TXT: {txt_r["name"][:40]} | {txt_r["unit"]} | {txt_r["price"]}')
            print(f'    DB:  {db_r["name"][:40]} | {db_r["unit"]} | {db_r["price"]}')

    # Summary by profession
    print("\n" + "-" * 70)
    print("按专业统计")
    print("-" * 70)

    cursor.execute('SELECT profession, COUNT(*) FROM quotas GROUP BY profession ORDER BY profession')
    db_prof_counts = {row[0]: row[1] for row in cursor.fetchall()}

    txt_by_prof = {}
    for r in txt_records:
        p = r['profession']
        txt_by_prof[p] = txt_by_prof.get(p, 0) + 1

    for prof in sorted(PROFESSION_MAP.values()):
        txt_cnt = txt_by_prof.get(prof, 0)
        db_cnt = db_prof_counts.get(prof, 0)
        diff = txt_cnt - db_cnt
        status = "OK" if diff == 0 else f"MISSING {diff}"
        print(f'{status:15} {prof}: TXT={txt_cnt}, DB={db_cnt}')

    conn.close()

    # Fix if needed
    if missing or extra or content_diff:
        print("\n" + "=" * 70)
        print("开始修复数据库")
        print("=" * 70)

        # Backup
        backup_path = f'{DB_PATH}.before_fix_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        shutil.copy(DB_PATH, backup_path)
        print(f'备份: {backup_path}')

        conn = sqlite3.connect(DB_PATH)
        conn.text_factory = str
        cursor = conn.cursor()

        # Delete extra
        if extra:
            for code, prof in extra:
                cursor.execute('DELETE FROM quotas WHERE code=? AND profession=?', (code, prof))
            print(f'删除 {len(extra)} 条多余记录')

        # Update content diffs
        if content_diff:
            for code, prof, txt_r, db_r in content_diff:
                cursor.execute('UPDATE quotas SET name=?, unit=?, price=? WHERE code=? AND profession=?',
                              (txt_r['name'], txt_r['unit'], txt_r['price'], code, prof))
            print(f'更新 {len(content_diff)} 条内容差异')

        # Insert missing
        if missing:
            inserted = 0
            for code, prof in missing:
                rec = txt_index[(code, prof)]
                cursor.execute('''INSERT INTO quotas (code, name, unit, price, profession)
                               VALUES (?, ?, ?, ?, ?)''',
                              (rec['code'], rec['name'], rec['unit'], rec['price'], rec['profession']))
                inserted += 1
            print(f'插入 {inserted} 条缺失记录')

        conn.commit()

        # Verify
        cursor.execute('SELECT COUNT(*) FROM quotas')
        new_total = cursor.fetchone()[0]
        print(f'\n修复后DB总计: {new_total}条 (应为 {txt_total}条)')

        if new_total == txt_total:
            print('SUCCESS: 数据库与TXT完全一致!')
        else:
            print(f'WARNING: 数量不匹配! 差异={txt_total - new_total}')

        conn.close()
    else:
        print('\n数据库与TXT已完全一致，无需修复')

if __name__ == '__main__':
    check_and_fix()