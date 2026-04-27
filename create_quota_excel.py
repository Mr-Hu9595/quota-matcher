# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'E:/skillshub/quota-matcher')
from src.data.quota_db import QuotaDB

os.chdir('E:/skillshub/quota-matcher')
db = QuotaDB()

# 定额匹配结果（根据查询结果）
quota_results = [
    (1, '4-10-60', '接地跨接线安装 构架接地', '处', 1417.2, 1417.2, '精确匹配', 'BV-4mm2黄绿双色线接地跨接'),
    (2, '4-13-179', '暗装接线盒安装', '个', 131, 131, '精确匹配', '三防接线盒 G1 IP65 WF1'),
    (3, '4-13-181', '明装防爆接线盒安装', '个', 393, 393, '精确匹配', '防爆接线盒 G1 ExdIICT4'),
    (4, '4-13-181', '明装防爆接线盒安装', '个', 610, 610, '精确匹配', '防爆活接头 G1-G1 ExdIICT4 注:无直接匹配定额'),
    (5, '4-7-5+4-7-6', '一般铁构件制作安装', 't', '槽钢94.5m+角钢42m', 1.048, '精确匹配', '热镀锌槽钢10#+角钢L40*4'),
    (6, '4-7-5+4-7-6', '一般铁构件制作安装', 't', '钢管57.6m+钢板19块', 0.942, '精确匹配', 'DN80热镀锌钢管立柱+钢板'),
]

# 输出到文件
with open('E:/skillshub/quota-matcher/quota_result_analysis.txt', 'w', encoding='utf-8') as f:
    f.write("=" * 80 + "\n")
    f.write("电信工程签证单定额套取结果\n")
    f.write("=" * 80 + "\n\n")

    f.write("【签证单工程量汇总】\n")
    f.write("-" * 40 + "\n")
    f.write("1. BV-4mm2接地跨接黄绿双色线: 1417.2米\n")
    f.write("2. 三防接线盒(G1 IP65 WF1): 131个\n")
    f.write("3. 防爆接线盒(G1 ExdIICT4): 393个\n")
    f.write("4. 防爆活接头(G1-G1 ExdIICT4): 610个\n")
    f.write("5. 热镀锌槽钢10#: 94.5米\n")
    f.write("6. 热镀锌角钢L40*4: 42米\n")
    f.write("7. 热镀锌钢管DN80(立柱用): 57.6米\n")
    f.write("8. 钢板200*200*8mm(立柱用): 19块\n\n")

    f.write("【定额套取分析】\n")
    f.write("-" * 40 + "\n\n")

    f.write("1. 接地跨接线(BV-4mm2 1417.2米)\n")
    f.write("   定额: 4-10-60 接地跨接线安装 构架接地\n")
    f.write("   单位: 处\n")
    f.write("   分析: 接地跨接线按处计量\n")
    f.write("   主材: BV-4mm2黄绿双色线(需另询市场价)\n\n")

    f.write("2. 三防接线盒(131个)\n")
    f.write("   定额: 4-13-179 暗装接线盒安装\n")
    f.write("   单位: 个\n\n")

    f.write("3. 防爆接线盒(393个)\n")
    f.write("   定额: 4-13-181 明装防爆接线盒安装\n")
    f.write("   单位: 个\n\n")

    f.write("4. 防爆活接头(610个)\n")
    f.write("   定额: 4-13-181 明装防爆接线盒安装(暂估)\n")
    f.write("   单位: 个\n")
    f.write("   分析: 数据库无直接匹配定额,需人工确认\n\n")

    f.write("5. 热镀锌槽钢10#(94.5米) + 角钢L40*4(42米)\n")
    f.write("   定额: 4-7-5+4-7-6 一般铁构件制作安装\n")
    f.write("   单位: t\n")
    f.write("   换算: 10#槽钢约10kg/m, L40*4角钢约2.42kg/m\n")
    f.write("   重量: (94.5x10 + 42x2.42)/1000 = 1.048t\n\n")

    f.write("6. 摄像头立柱(DN80钢管57.6米 + 钢板19块)\n")
    f.write("   定额: 4-7-5+4-7-6 一般铁构件制作安装\n")
    f.write("   单位: t\n")
    f.write("   分析: 立柱采用钢管和钢板制作,属一般铁构件\n\n")

    f.write("【广联达Excel输出格式】\n")
    f.write("=" * 80 + "\n")
    header = "序号 | 定额编号 | 定额名称 | 单位 | 工程量表达式 | 工程量 | 匹配方式"
    f.write(header + "\n")
    f.write("-" * 80 + "\n")
    for item in quota_results:
        line = "{} | {} | {} | {} | {} | {} | {}".format(
            item[0], item[1], item[2], item[3], item[4], item[5], item[6])
        f.write(line + "\n")

print("分析完成")