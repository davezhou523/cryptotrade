# 在trend/tradingStrategy.py中添加自定义EMA计算类
import backtrader as bt
import numpy as np
from config import STRATEGY_PARAMS
class CustomEMA(bt.Indicator):
    """自定义EMA实现，与Binance算法一致"""
    lines = ('ema',)
    params = (('period', STRATEGY_PARAMS['fast_ma_period']),)
    
    def __init__(self):
        self.smoothing = 2 / (self.params.period + 1)  # Binance使用的平滑因子
        self.addminperiod(self.params.period)
    
    def next(self):
        if len(self) == self.params.period:
            # 第一个EMA值使用SMA作为初始值
            ema_value = sum(self.data.get(size=self.params.period)) / self.params.period
        else:
            # EMA公式：EMA = 今日收盘价 * 平滑因子 + 昨日EMA * (1 - 平滑因子)
            ema_value = self.data[0] * self.smoothing + self.l.ema[-1] * (1 - self.smoothing)
        
        self.l.ema[0] = ema_value

