# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB

os.chdir('E:/skillshub/quota-matcher')
db = QuotaDB()

with open('E:/skillshub/quota-matcher/quota_results2.txt', 'w', encoding='utf-8') as f:
    # 1. 接地线/接地跨接
    f.write("=== 接地跨接 4-10-59/60/61 ===\n")
    for r in db.search_by_prefix('4-10-59'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')
    for r in db.search_by_prefix('4-10-60'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')
    for r in db.search_by_prefix('4-10-61'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 2. 防爆接线盒
    f.write("\n=== 防爆接线盒 4-13-181 ===\n")
    for r in db.search_by_prefix('4-13-181'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 3. 暗装接线盒
    f.write("\n=== 暗装接线盒 4-13-179 ===\n")
    for r in db.search_by_prefix('4-13-179'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 4. 一般铁构件制作 8-1
    f.write("\n=== 一般铁构件制作 8-1 ===\n")
    for r in db.search_by_prefix('8-1'):
        if '铁构件' in r['name'] or '支架' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 5. 电力电缆 4-9
    f.write("\n=== 电力电缆 4-9 ===\n")
    for r in db.search_by_prefix('4-9')[:30]:
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 6. 钢管敷设 6-2-xxx
    f.write("\n=== 钢管敷设 6-2 ===\n")
    for r in db.search_by_prefix('6-2'):
        if '钢管' in r['name'] or '管' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 7. 电气支架 4-2
    f.write("\n=== 电气支架 4-2 ===\n")
    for r in db.search_by_prefix('4-2'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

print("Done")