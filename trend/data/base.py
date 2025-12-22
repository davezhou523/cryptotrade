"""
数据获取器基础接口
"""

from abc import ABC, abstractmethod
from datetime import datetime


class DataFetcher(ABC):
    """
    数据获取器抽象基类，定义统一的数据获取接口
    """
    
    @abstractmethod
    def fetch_klines(self, symbol: str, interval: str, start_time: datetime, end_time: datetime, save_dir: str = None) -> str:
        """
        获取K线数据
        :param symbol: 交易对 (如: ETHUSDT)
        :param interval: 时间间隔 (如: 1m, 1h, 4h, 1d)
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param save_dir: 保存目录（可选）
        :return: 保存数据的CSV文件名
        """
        pass
    
    @abstractmethod
    def get_supported_intervals(self) -> list:
        """
        获取支持的时间间隔列表
        :return: 时间间隔列表
        """
        pass