import backtrader as bt

class DMI(bt.Indicator):
    """
    自定义DMI指标类
    Directional Movement Index (DMI) 用于判断趋势强度和方向
    """
    lines = ('plus_di', 'minus_di', 'adx')
    params = (('period', 14),)

    def __init__(self):
        # 调用父类的__init__方法
        super().__init__()
        
        # 直接使用backtrader的DMI指标，使用params中的period
        self.dmi = bt.indicators.DMI(self.data, period=self.params.period)

        # 映射指标线
        self.lines.plus_di = self.dmi.plusDI
        self.lines.minus_di = self.dmi.minusDI
        self.lines.adx = self.dmi.adx