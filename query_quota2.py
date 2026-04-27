# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB
db = QuotaDB()

# 精确搜索定额
print("=== 1. 接地线 4mm² ===")
for r in db.search_by_prefix('4-10'):
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 2. 钢管敷设 DN80 ===")
for r in db.search_by_prefix('6-2'):
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 3. 接线盒安装 ===")
for r in db.search_by_prefix('4-13'):
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 4. 铁构件制作 4-7 ===")
for r in db.search_by_prefix('4-7'):
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 5. 槽钢角钢支架 4-4 ===")
for r in db.search_by_prefix('4-4'):
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 6. 钢管 DN80 ===")
results = db.search_by_keyword('DN80')
for r in results:
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')

print("\n=== 7. 焊接钢管 ===")
results = db.search_by_keyword('焊接钢管')
for r in results[:10]:
    print(f'{r["code"]} | {r["name"]} | {r["unit"]}')