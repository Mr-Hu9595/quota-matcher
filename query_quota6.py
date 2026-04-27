# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB

os.chdir('E:/skillshub/quota-matcher')
db = QuotaDB()

with open('E:/skillshub/quota-matcher/quota_results3.txt', 'w', encoding='utf-8') as f:
    # 1. 一般铁构件制作 安装 4-7
    f.write("=== 一般铁构件制作安装 4-7 ===\n")
    for r in db.search_by_prefix('4-7'):
        if '铁构件' in r['name'] or '支架' in r['name'] or '构件' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 2. 电气设备安装 4-8
    f.write("\n=== 电气设备安装 4-8 ===\n")
    for r in db.search_by_prefix('4-8'):
        if '铁构件' in r['name'] or '支架' in r['name'] or '接线盒' in r['name'] or '活接头' in r['name'] or '钢管' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 3. 电力电缆 4-9
    f.write("\n=== 电力电缆 4-9 相关 ===\n")
    for r in db.search_by_prefix('4-9'):
        if '接地' in r['name'] or '跨接' in r['name'] or 'BV' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 4. 搜索活接头
    f.write("\n=== 活接头 ===\n")
    for r in db.search_by_keyword('活接头'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 5. 搜索钢管
    f.write("\n=== 焊接钢管 ===\n")
    for r in db.search_by_keyword('焊接钢管'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 6. 搜索镀锌钢管
    f.write("\n=== 镀锌钢管 ===\n")
    for r in db.search_by_keyword('镀锌钢管'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 7. 搜索槽钢角钢
    f.write("\n=== 槽钢角钢 ===\n")
    for r in db.search_by_keyword('槽钢'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

print("Done")