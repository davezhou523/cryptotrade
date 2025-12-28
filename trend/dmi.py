import backtrader as bt
import numpy as np
from config import STRATEGY_PARAMS

class DMI(bt.Indicator):
    """
    自定义DMI指标类，精确实现与Binance一致的DMI算法
    """
    lines = ('plus_di', 'minus_di', 'adx')
    params = (
        ('period', STRATEGY_PARAMS['dmi_period']),
    )

    def __init__(self):
        super(DMI, self).__init__()
        
        # 初始化存储变量
        self._tr_values = []
        self._plus_dm_values = []
        self._minus_dm_values = []
        
        # 存储平滑后的值
        self._sm_tr = 0.0
        self._sm_plus_dm = 0.0
        self._sm_minus_dm = 0.0
        
        # DX和ADX相关
        self._dx_values = []
        self._sm_dx = 0.0
        
        # 记录当前周期
        self._current_period = 0

    def next(self):
        # 获取当前K线数据
        high = self.data.high[0]
        low = self.data.low[0]
        close = self.data.close[0]
        
        # 获取前一根K线数据
        if len(self.data) > 1:
            prev_high = self.data.high[-1]
            prev_low = self.data.low[-1]
            prev_close = self.data.close[-1]
        else:
            # 数据不足时，使用默认值
            prev_high = high
            prev_low = low
            prev_close = close
        
        # 计算TR
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = max(tr1, tr2, tr3)
        
        # 计算+DM和-DM
        plus_dm = high - prev_high if high - prev_high > prev_low - low and high - prev_high > 0 else 0
        minus_dm = prev_low - low if prev_low - low > high - prev_high and prev_low - low > 0 else 0
        
        # 存储原始值
        self._tr_values.append(tr)
        self._plus_dm_values.append(plus_dm)
        self._minus_dm_values.append(minus_dm)
        
        # 更新当前周期
        self._current_period += 1
        
        # 计算初始SMMA值
        if self._current_period == self.params.period:
            self._sm_tr = sum(self._tr_values)
            self._sm_plus_dm = sum(self._plus_dm_values)
            self._sm_minus_dm = sum(self._minus_dm_values)
        elif self._current_period > self.params.period:
            # 后续SMMA值计算
            self._sm_tr = (self._sm_tr * (self.params.period - 1) + tr) / self.params.period
            self._sm_plus_dm = (self._sm_plus_dm * (self.params.period - 1) + plus_dm) / self.params.period
            self._sm_minus_dm = (self._sm_minus_dm * (self.params.period - 1) + minus_dm) / self.params.period
        
        # 计算+DI和-DI
        if self._current_period >= self.params.period and self._sm_tr != 0:
            plus_di = 100 * (self._sm_plus_dm / self._sm_tr)
            minus_di = 100 * (self._sm_minus_dm / self._sm_tr)
        else:
            plus_di = 0.0
            minus_di = 0.0
        
        # 计算DX
        if self._current_period >= self.params.period:
            di_sum = plus_di + minus_di
            if di_sum != 0:
                dx = 100 * abs(plus_di - minus_di) / di_sum
            else:
                dx = 0.0
            self._dx_values.append(dx)
        else:
            dx = 0.0
        
        # 计算ADX - 修复核心问题！
        if len(self._dx_values) >= self.params.period:
            if len(self._dx_values) == self.params.period:
                # 初始ADX使用DX的简单平均值
                self._sm_dx = sum(self._dx_values) / self.params.period
            elif len(self._dx_values) > self.params.period:
                # 后续ADX使用SMMA计算
                self._sm_dx = (self._sm_dx * (self.params.period - 1) + dx) / self.params.period
            
            adx = self._sm_dx  # 直接使用SMMA值，不再额外除以period
        else:
            adx = 0.0
        
        # 设置输出值
        self.lines.plus_di[0] = plus_di
        self.lines.minus_di[0] = minus_di
        self.lines.adx[0] = adx