"""
数据获取器基础接口
"""

from abc import ABC, abstractmethod
from datetime import datetime
import os
import pandas as pd
import backtrader as bt


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


def get_1h_data(symbol: str) -> bt.feeds.PandasData:
    """
    获取1小时K线数据
    :param symbol: 交易对（如ETH、BTC）
    :return: Backtrader数据对象
    """
    # 构造文件路径
    data_dir = os.path.join(os.path.dirname(__file__), symbol.upper())
    file_path = os.path.join(data_dir, f"{symbol.lower()}usdt_1h_20250101_20251222.csv")
    
    # 读取CSV文件
    df = pd.read_csv(file_path)
    
    # 转换时间列
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 创建Backtrader数据对象
    data = bt.feeds.PandasData(
        dataname=df,
        datetime='datetime',
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest=-1
    )
    
    return data


def get_daily_data(symbol: str) -> bt.feeds.PandasData:
    """
    获取日K线数据
    :param symbol: 交易对（如ETH、BTC）
    :return: Backtrader数据对象
    """
    # 构造文件路径
    data_dir = os.path.join(os.path.dirname(__file__), symbol.upper())
    file_path = os.path.join(data_dir, f"{symbol.lower()}usdt_1d_20250101_20251222.csv")
    
    # 读取CSV文件
    df = pd.read_csv(file_path)
    
    # 转换时间列
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # 创建Backtrader数据对象
    data = bt.feeds.PandasData(
        dataname=df,
        datetime='datetime',
        open='open',
        high='high',
        low='low',
        close='close',
        volume='volume',
        openinterest=-1
    )
    
    return data