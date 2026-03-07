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


def get_crypto_data(symbol: str, interval: str, start_year: int = 2025, end_year: int = 2025) -> bt.feeds.PandasData:
    """
    获取加密货币K线数据
    :param symbol: 交易对（如ETH、BTC）
    :param interval: 时间间隔（如1h、1d）
    :param start_year: 开始年份
    :param end_year: 结束年份
    :return: Backtrader数据对象
    """
    # 验证参数
    if interval not in ['1h', '1d', '4h', '1w']:
        raise ValueError("时间间隔必须是 '1h'、'1d'、'4h' 或 '1w'")
    
    # 构造文件路径
    data_dir = os.path.join(os.path.dirname(__file__), symbol.upper())
    
    # 收集所有年份的数据
    all_dfs = []
    for year in range(start_year, end_year + 1):
        file_path = os.path.join(data_dir, f"{symbol.lower()}usdt_{interval}_{year}0101_{year}1231.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            all_dfs.append(df)
        else:
            print(f"警告: 文件不存在: {file_path}")
    
    if not all_dfs:
        raise FileNotFoundError(f"找不到任何{interval}数据文件，年份范围: {start_year}-{end_year}")
    
    # 合并数据
    df = pd.concat(all_dfs, ignore_index=True)
    
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


def get_1h_data(symbol: str, start_year: int = 2025, end_year: int = 2025) -> bt.feeds.PandasData:
    """
    获取1小时K线数据
    :param symbol: 交易对（如ETH、BTC）
    :param start_year: 开始年份
    :param end_year: 结束年份
    :return: Backtrader数据对象
    """
    return get_crypto_data(symbol, '1h', start_year, end_year)
def get_4h_data(symbol: str, start_year: int = 2025, end_year: int = 2025) -> bt.feeds.PandasData:
    """
    获取4小时K线数据
    :param symbol: 交易对（如ETH、BTC）
    :param start_year: 开始年份
    :param end_year: 结束年份
    :return: Backtrader数据对象
    """
    return get_crypto_data(symbol, '4h', start_year, end_year)

def get_daily_data(symbol: str, start_year: int = 2025, end_year: int = 2025) -> bt.feeds.PandasData:
    """
    获取日K线数据
    :param symbol: 交易对（如ETH、BTC）
    :param start_year: 开始年份
    :param end_year: 结束年份
    :return: Backtrader数据对象
    """
    return get_crypto_data(symbol, '1d', start_year, end_year)

def get_weekly_data(symbol: str, start_year: int = 2025, end_year: int = 2025) -> bt.feeds.PandasData:
    """
    获取周K线数据
    :param symbol: 交易对（如ETH、BTC）
    :param start_year: 开始年份
    :param end_year: 结束年份
    :return: Backtrader数据对象
    """
    return get_crypto_data(symbol, '1w', start_year, end_year)