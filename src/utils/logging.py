"""
统一日志管理器
全流程操作留痕，便于调试和Bug追踪
"""

import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# 日志目录
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class QuotaLogger:
    """统一日志管理器"""

    _instance = None

    def __init__(self):
        self.log_dir = LOG_DIR
        self._setup_loggers()

    def _setup_loggers(self):
        """设置各层日志器"""

        # 业务层日志
        self.business = self._create_logger(
            "quota.business",
            self.log_dir / "business.log",
            level=logging.INFO
        )

        # 引擎层日志
        self.engine = self._create_logger(
            "quota.engine",
            self.log_dir / "engine.log",
            level=logging.DEBUG
        )

        # 数据层日志
        self.data = self._create_logger(
            "quota.data",
            self.log_dir / "data.log",
            level=logging.DEBUG
        )

        # 匹配日志（记录每一条匹配操作，便于分析）
        self.match = self._create_logger(
            "quota.match",
            self.log_dir / "match.log",
            level=logging.INFO
        )

        # API日志（记录AI/向量API调用）
        self.api = self._create_logger(
            "quota.api",
            self.log_dir / "api.log",
            level=logging.INFO
        )

    def _create_logger(self, name: str, filepath: Path, level=logging.DEBUG):
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # 避免重复添加handler
        if not logger.handlers:
            # 文件handler（按天滚动）
            fh = TimedRotatingFileHandler(
                filepath,
                when='midnight',
                interval=1,
                backupCount=30,
                encoding='utf-8'
            )
            fh.setLevel(level)

            # 控制台handler
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            # 格式
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            logger.addHandler(fh)
            logger.addHandler(ch)

        return logger

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = QuotaLogger()
        return cls._instance


# 便捷函数
def get_logger(name: str = "quota"):
    """获取业务日志器"""
    return QuotaLogger.get_instance().business


def get_data_logger():
    """获取数据层日志器"""
    return QuotaLogger.get_instance().data


def get_engine_logger():
    """获取引擎层日志器"""
    return QuotaLogger.get_instance().engine


def get_match_logger():
    """获取匹配日志器"""
    return QuotaLogger.get_instance().match


def get_api_logger():
    """获取API日志器"""
    return QuotaLogger.get_instance().api


class MatchLog:
    """匹配日志辅助类"""

    @staticmethod
    def log(item_name: str, code: str, confidence: str, engine: str, note: str = ""):
        """记录单条匹配操作"""
        logger = get_match_logger()
        logger.info(
            f"MATCH | item={_truncate(item_name, 30)} | "
            f"code={code} | confidence={confidence} | engine={engine} | {note}"
        )

    @staticmethod
    def log_batch_start(count: int):
        """记录批量匹配开始"""
        logger = get_match_logger()
        logger.info(f"BATCH_START | count={count}")

    @staticmethod
    def log_batch_end(success: int, failed: int, high: int, medium: int, low: int):
        """记录批量匹配结束"""
        logger = get_match_logger()
        logger.info(
            f"BATCH_END | success={success} | failed={failed} | "
            f"high={high} | medium={medium} | low={low}"
        )


def _truncate(text: str, max_len: int) -> str:
    """截断文本"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
