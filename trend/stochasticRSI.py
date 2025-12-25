# 只保留需要的导入
import backtrader as bt

# 移除 sys, datetime, csv 这些不需要的导入
from config import STRATEGY_PARAMS
class StochasticRSI(bt.Indicator):
    """
    自定义Stochastic RSI指标
    计算方法：先计算RSI，然后对RSI应用Stochastic指标
    """
    lines = ('percK', 'percD')
    params = (
        ('period', STRATEGY_PARAMS['rsi_period']),  # RSI周期
        ('stoch_period', STRATEGY_PARAMS['stoch_period']),  # Stochastic K周期
        ('dperiod', STRATEGY_PARAMS['stoch_d_period']),  # Stochastic D周期
        ('movav', bt.indicators.EMA),  # 移动平均线类型
        ('smooth_period', STRATEGY_PARAMS['smooth_period']),  # 增加平滑周期到5
        ('rsi_smooth_period', STRATEGY_PARAMS['rsi_smooth_period']),  # RSI平滑周期
    )

    def __init__(self):
        # 计算RSI
        rsi = bt.indicators.RSI(period=self.params.period)

        # 对RSI指标本身进行平滑处理
        smoothed_rsi = self.params.movav(rsi, period=self.params.rsi_smooth_period)

        # 计算RSI在指定周期内的最高价和最低价
        highest_rsi = bt.indicators.Highest(smoothed_rsi, period=self.params.stoch_period)
        lowest_rsi = bt.indicators.Lowest(smoothed_rsi, period=self.params.stoch_period)

        # 计算%K - 修复分母为0的情况
        # 当最高价等于最低价时，避免除以0，返回50（中性）
        raw_percK = bt.If(
            highest_rsi == lowest_rsi,
            50.0,
            100.0 * (smoothed_rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
        )

        # 添加边界检查，确保K值在0-100之间
        bounded_percK = bt.Max(bt.Min(raw_percK, 100.0), 0.0)

        # 对K值进行额外平滑
        smoothed_percK = self.params.movav(bounded_percK, period=self.params.smooth_period)

        # 再次进行边界检查
        self.l.percK = bt.Max(bt.Min(smoothed_percK, 100.0), 0.0)

        # 计算%D - %K的移动平均线
        raw_percD = self.params.movav(self.l.percK, period=self.params.dperiod)

        # 添加边界检查，确保D值在0-100之间
        self.l.percD = bt.Max(bt.Min(raw_percD, 100.0), 0.0)