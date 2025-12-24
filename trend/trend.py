import backtrader as bt
from .dmi import DMI
class TrendDetector(bt.Indicator):
    """
    趋势判断类，使用DMI+BOLL技术指标判断三种趋势类型
    - 震荡趋势
    - 单边上涨趋势
    - 单边下跌趋势
    """
    lines = ('trend_type',)
    params = (
        # BOLL参数
        ('boll_period', 20),
        ('boll_dev', 2),

        # DMI参数
        ('dmi_period', 14),
        ('adx_threshold', 15),  # 降低ADX阈值

        # 趋势类型定义
        ('sideways_trend', 0),
        ('bullish_trend', 1),
        ('bearish_trend', -1),
    )

    def __init__(self):
        # 初始化指标
        self.dmi = DMI(period=self.params.dmi_period)
        self.boll = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )

    def next(self):
        """
        计算当前趋势类型
        - 震荡趋势：ADX < adx_threshold
        - 单边上涨趋势：+DI > -DI 且 ADX >= adx_threshold
        - 单边下跌趋势：-DI > +DI 且 ADX >= adx_threshold
        """
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plus_di[0]
        minus_di_value = self.dmi.minus_di[0]

        # 判断趋势类型
        if adx_value < self.params.adx_threshold:
            # 震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend
        elif plus_di_value > minus_di_value and adx_value >= self.params.adx_threshold:
            # 单边上涨趋势
            self.lines.trend_type[0] = self.params.bullish_trend
        elif minus_di_value > plus_di_value and adx_value >= self.params.adx_threshold:
            # 单边下跌趋势
            self.lines.trend_type[0] = self.params.bearish_trend
        else:
            # 默认情况：震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend