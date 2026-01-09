import backtrader as bt
from config import STRATEGY_PARAMS

class StochasticRSI(bt.Indicator):
    """
    标准Stoch RSI指标实现（与Binance一致）
    计算公式：StochRSI = (RSI - RSI_Low) / (RSI_High - RSI_Low) * 100
    其中：
    - RSI：基础RSI指标（14周期）
    - RSI_Low：RSI在指定周期内的最低价（14周期）
    - RSI_High：RSI在指定周期内的最高价（14周期）
    - %K：StochRSI的3周期简单移动平均
    - %D：%K的3周期简单移动平均
    """
    lines = ('percK', 'percD')
    params = (
        ('period', STRATEGY_PARAMS['rsi_period']),  # RSI周期
        ('stoch_period', STRATEGY_PARAMS['stoch_period']),  # Stochastic K周期
        ('dperiod', STRATEGY_PARAMS['stoch_d_period']),  # Stochastic D周期
        ('movav', bt.ind.SimpleMovingAverage),  # 移动平均类型
    )

    def __init__(self):
        # 1. 计算基础RSI（使用标准14周期）
        rsi = bt.indicators.RSI(period=self.params.period)

        # 2. 计算RSI在指定周期内的最高价和最低价
        highest_rsi = bt.indicators.Highest(rsi, period=self.params.stoch_period)
        lowest_rsi = bt.indicators.Lowest(rsi, period=self.params.stoch_period)

        # 3. 计算原始StochRSI值
        raw_stoch_rsi = bt.If(
            highest_rsi == lowest_rsi,
            50.0,  # 当最高价等于最低价时，设置为中间值50
            100.0 * (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
        )

        # 4. 计算%K值：对原始StochRSI进行3周期简单移动平均
        self.l.percK = self.params.movav(raw_stoch_rsi, period=3)

        # 5. 计算%D值：对%K值进行3周期简单移动平均
        self.l.percD = self.params.movav(self.l.percK, period=3)

        # 6. 将结果限制在0-100范围内
        self.l.percK = bt.Max(bt.Min(self.l.percK, 100.0), 0.0)
        self.l.percD = bt.Max(bt.Min(self.l.percD, 100.0), 0.0)