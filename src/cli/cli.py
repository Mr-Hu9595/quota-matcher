# -*- coding: utf-8 -*-
"""
自然语言接口 - Claude Code 调用入口

用法:
    python -m src.cli process "D:\清单.xlsx"
    python -m src.cli query "电力电缆"
    python -m src.cli learn --code "4-9-XXX" --name "xxx" --keywords "电力电缆"
    python -m src.cli stats
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.data.quota_db import QuotaDB
from src.data.rule_db import RuleDB
from src.engine.hybrid_engine import HybridEngine
from src.engine.rule_engine import RuleEngine
from src.business.quota_matcher import QuotaMatcherBusiness
from src.utils.logging import get_logger, get_data_logger, get_match_logger

logger = get_logger()
data_logger = get_data_logger()
match_logger = get_match_logger()


class QuotaCLI:
    """
    自然语言接口 - Claude Code 调用入口

    提供命令：
    - process: 处理工程量清单
    - query: 查询定额
    - learn: 学习新规则
    - stats: 统计信息
    """

    def __init__(self):
        """初始化CLI"""
        logger.info("初始化 QuotaCLI...")

        self.quota_db = QuotaDB()
        self.rule_db = RuleDB()

        # 从环境变量获取 API Key
        api_key = os.environ.get("MINIMAX_API_KEY") or os.environ.get("MINIMAX_CHAT_API_KEY")
        self.engine = HybridEngine(rule_db=self.rule_db, quota_db=self.quota_db, api_key=api_key)

        logger.info("QuotaCLI 初始化完成")

    def process(self, input_file: str, output: str = None) -> str:
        """
        处理工程量清单文件

        Args:
            input_file: 输入文件路径
            output: 输出文件路径（可选）

        Returns:
            输出文件路径
        """
        logger.info(f"CLI process: {input_file} -> {output or '自动'}")

        business = QuotaMatcherBusiness(
            engine=self.engine,
            quota_db=self.quota_db,
            rule_db=self.rule_db
        )

        return business.process(input_file, output)

    def query(self, keyword: str = None, prefix: str = None, limit: int = 10) -> List[dict]:
        """
        查询定额

        Args:
            keyword: 关键词（可选）
            prefix: 前缀（可选）
            limit: 返回数量

        Returns:
            定额列表
        """
        logger.info(f"CLI query: keyword={keyword}, prefix={prefix}, limit={limit}")

        if prefix:
            results = self.quota_db.search_by_prefix(prefix)
        elif keyword:
            results = self.quota_db.search_by_keyword(keyword, top_k=limit)
        else:
            results = self.quota_db.get_all()[:limit]

        return results

    def learn(self, code: str, name: str, unit: str, keywords: List[str]):
        """
        学习新规则

        Args:
            code: 定额编号
            name: 定额名称
            unit: 单位
            keywords: 关键词列表
        """
        logger.info(f"CLI learn: code={code}, name={name}")

        self.rule_db.add_rule(code, name, unit, keywords)
        print(f"规则已添加: {code} - {name}")

    def confirm(self, code: str):
        """
        确认规则使用

        Args:
            code: 定额编号
        """
        logger.info(f"CLI confirm: code={code}")

        self.rule_db.confirm_rule(code)
        print(f"规则已确认: {code}")

    def stats(self) -> dict:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        logger.info("CLI stats")

        stats = {
            'quota_count': self.quota_db.count(),
            'rule_count': self.rule_db.count(),
            'prefixes': self.rule_db.get_all_prefixes()
        }

        print(f"统计信息:")
        print(f"  定额数量: {stats['quota_count']}")
        print(f"  规则数量: {stats['rule_count']}")
        print(f"  前缀分类: {len(stats['prefixes'])} 个")

        return stats


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(
        description="Quota Matcher CLI - Claude Code自然语言驱动入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m src.cli process "D:\\清单.xlsx"
  python -m src.cli query --keyword "电力电缆"
  python -m src.cli query --prefix "4-9"
  python -m src.cli learn --code "4-9-999" --name "测试定额" --unit "10m" --keywords "电力电缆,测试"
  python -m src.cli confirm --code "4-9-159"
  python -m src.cli stats
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # process 命令
    process_parser = subparsers.add_parser('process', help='处理工程量清单')
    process_parser.add_argument('input_file', help='输入文件路径')
    process_parser.add_argument('-o', '--output', help='输出文件路径')

    # query 命令
    query_parser = subparsers.add_parser('query', help='查询定额')
    query_parser.add_argument('--keyword', '-k', help='关键词')
    query_parser.add_argument('--prefix', '-p', help='前缀')
    query_parser.add_argument('--limit', '-l', type=int, default=10, help='返回数量')

    # learn 命令
    learn_parser = subparsers.add_parser('learn', help='学习新规则')
    learn_parser.add_argument('--code', required=True, help='定额编号')
    learn_parser.add_argument('--name', required=True, help='定额名称')
    learn_parser.add_argument('--unit', required=True, help='单位')
    learn_parser.add_argument('--keywords', required=True, help='关键词（逗号分隔）')

    # confirm 命令
    confirm_parser = subparsers.add_parser('confirm', help='确认规则使用')
    confirm_parser.add_argument('--code', required=True, help='定额编号')

    # stats 命令
    subparsers.add_parser('stats', help='统计信息')

    args = parser.parse_args()

    # 初始化CLI
    cli = QuotaCLI()

    # 执行命令
    if args.command == 'process':
        cli.process(args.input_file, args.output)

    elif args.command == 'query':
        results = cli.query(args.keyword, args.prefix, args.limit)
        print(f"\n查询结果 ({len(results)} 条):")
        for r in results:
            print(f"  {r.get('code')}: {r.get('name')} ({r.get('unit')})")

    elif args.command == 'learn':
        keywords = [k.strip() for k in args.keywords.split(',')]
        cli.learn(args.code, args.name, args.unit, keywords)

    elif args.command == 'confirm':
        cli.confirm(args.code)

    elif args.command == 'stats':
        cli.stats()

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
