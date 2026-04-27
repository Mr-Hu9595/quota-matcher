# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB

os.chdir('E:/skillshub/quota-matcher')
db = QuotaDB()

with open('E:/skillshub/quota-matcher/quota_results.txt', 'w', encoding='utf-8') as f:
    f.write("=== 1. 接地线 4-10 ===\n")
    for r in db.search_by_prefix('4-10'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]}\n')

    f.write("\n=== 2. 钢管敷设 6-2 ===\n")
    for r in db.search_by_prefix('6-2'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]}\n')

    f.write("\n=== 3. 接线盒安装 4-13 ===\n")
    for r in db.search_by_prefix('4-13'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]}\n')

    f.write("\n=== 4. 铁构件制作 4-7 ===\n")
    for r in db.search_by_prefix('4-7'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]}\n')

    f.write("\n=== 5. 槽钢角钢支架 4-4 ===\n")
    for r in db.search_by_prefix('4-4'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]}\n')

print("Done. Results written to quota_results.txt")