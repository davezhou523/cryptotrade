"""
数据获取包，提供统一的接口从不同交易所获取历史K线数据
"""

from .base import DataFetcher
from .binance import BinanceDataFetcher
# 未来添加Gate.io支持时导入
# from .gateio import GateioDataFetcher

__all__ = ['DataFetcher', 'BinanceDataFetcher']