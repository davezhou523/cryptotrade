import backtrader as bt

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
        ('dmi_period', 7),
        ('adx_threshold', 15),  # 降低ADX阈值

        # 趋势类型定义
        ('sideways_trend', 0),
        ('bullish_trend', 1),
        ('bearish_trend', -1),
    )

    def __init__(self):
        # 调用父类的__init__方法
        super().__init__()
        
        # 打印参数值，确认是否正确获取
        print(f"TrendDetector参数dmi_period: {self.params.dmi_period}")
        
        # 使用Backtrader内置的DMI指标，只使用period参数
        self.dmi = bt.indicators.DMI(
            self.data, 
            period=self.params.dmi_period
        )
        
        # 检查DMI指标的实际参数
        print(f"DMI指标实际周期: {self.dmi.params.period}")

        # 使用Backtrader内置的BOLL指标
        self.boll = bt.indicators.BBands(
            self.data,
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
        plus_di_value = self.dmi.plusDI[0]
        minus_di_value = self.dmi.minusDI[0]

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