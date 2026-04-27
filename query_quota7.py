# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB

os.chdir('E:/skillshub/quota-matcher')
db = QuotaDB()

with open('E:/skillshub/quota-matcher/quota_results4.txt', 'w', encoding='utf-8') as f:
    # 1. 钢制管件
    f.write("=== 钢制管件 ===\n")
    for r in db.search_by_keyword('钢制'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 2. 电缆保护管
    f.write("\n=== 电缆保护管 ===\n")
    for r in db.search_by_keyword('电缆保护管'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 3. 钢管敷设 6-2
    f.write("\n=== 钢管敷设 6-2 ===\n")
    for r in db.search_by_prefix('6-2'):
        if '管' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 4. 现场构件
    f.write("\n=== 现场构件制作 ===\n")
    for r in db.search_by_keyword('现场'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 5. 角钢支架
    f.write("\n=== 角钢支架 ===\n")
    for r in db.search_by_keyword('角钢支架'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 6. 槽钢支架
    f.write("\n=== 槽钢支架 ===\n")
    for r in db.search_by_keyword('槽钢支架'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 7. 立柱
    f.write("\n=== 立柱 ===\n")
    for r in db.search_by_keyword('立柱'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 8. 配电箱
    f.write("\n=== 配电箱 ===\n")
    for r in db.search_by_keyword('配电箱'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 9. 电气安装
    f.write("\n=== 电气安装 4-13 ===\n")
    for r in db.search_by_prefix('4-13'):
        if '防爆' in r['name'] or '活接' in r['name'] or '接头' in r['name']:
            f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

    # 10. 8-1铁构件
    f.write("\n=== 8-1铁构件 ===\n")
    for r in db.search_by_prefix('8-1'):
        f.write(f'{r["code"]} | {r["name"]} | {r["unit"]} | price={r["price"]}\n')

print("Done")