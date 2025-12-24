import backtrader as bt


class DMI(bt.Indicator):
    """
    自定义DMI指标类
    Directional Movement Index (DMI) 用于判断趋势强度和方向
    """
    lines = ('plus_di', 'minus_di', 'adx')
    params = (('period', 14),)

    def __init__(self):
        # 使用Backtrader内置的DMI指标
        self.dmi = bt.indicators.DirectionalMovement(period=self.params.period)
        self.lines.plus_di = self.dmi.plusDI
        self.lines.minus_di = self.dmi.minusDI
        self.lines.adx = self.dmi.adx