# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB
db = QuotaDB()

queries = [
    ('接地跨接线', '接地跨接'),
    ('BV4接地线', 'BV-4'),
    ('三防接线盒', '三防接线盒'),
    ('防爆接线盒', '防爆接线盒'),
    ('防爆活接头', '防爆活接头'),
    ('槽钢支架', '槽钢支架'),
    ('角钢支架', '角钢支架'),
    ('立柱制作', '立柱制作'),
    ('铁构件制作', '一般铁构件'),
    ('钢管DN80', 'DN80'),
    ('钢板制作', '钢板'),
]

for name, kw in queries:
    print(f'=== {name} ===')
    results = db.search_by_keyword(kw)[:5]
    for r in results:
        print(f'  {r["code"]} | {r["name"]} | {r["unit"]} | {r["price"]}')
    print()