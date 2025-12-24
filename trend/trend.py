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
        计算当前趋势类型 - 整合DMI和BOLL指标
        - 震荡趋势：ADX < adx_threshold 且 价格在BOLL通道内
        - 单边上涨趋势：+DI > -DI 且 ADX >= adx_threshold 且 (价格突破BOLL上轨或在中上轨之间)
        - 单边下跌趋势：-DI > +DI 且 ADX >= adx_threshold 且 (价格突破BOLL下轨或在中下轨之间)
        """
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plusDI[0]
        minus_di_value = self.dmi.minusDI[0]
        
        # BOLL指标数据
        close = self.data.close[0]
        boll_top = self.boll.lines.top[0]
        boll_mid = self.boll.lines.mid[0]
        boll_bot = self.boll.lines.bot[0]
        
        # 价格在BOLL通道内的判断
        in_boll_channel = (boll_bot <= close <= boll_top)
        # 价格接近或突破BOLL上轨
        near_boll_top = (close >= boll_mid)
        # 价格接近或突破BOLL下轨
        near_boll_bot = (close <= boll_mid)
        
        # 综合DMI和BOLL的趋势判断
        if adx_value < self.params.adx_threshold and in_boll_channel:
            # ADX低且价格在通道内，确认震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend
        elif (plus_di_value > minus_di_value and adx_value >= self.params.adx_threshold and near_boll_top):
            # DMI显示上涨且价格在通道上半部分，确认上涨趋势
            self.lines.trend_type[0] = self.params.bullish_trend
        elif (minus_di_value > plus_di_value and adx_value >= self.params.adx_threshold and near_boll_bot):
            # DMI显示下跌且价格在通道下半部分，确认下跌趋势
            self.lines.trend_type[0] = self.params.bearish_trend
        else:
            # 指标冲突时，默认保持震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend