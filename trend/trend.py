import backtrader as bt
from config import STRATEGY_PARAMS
from datetime import datetime

class TrendDetector(bt.Indicator):
    """
    趋势判断类，使用DMI+BOLL技术指标判断三种趋势类型
    - 震荡趋势
    - 单边上涨趋势
    - 单边下跌趋势
    """
    lines = ('trend_type',)
    params = (
        ('boll_period', STRATEGY_PARAMS['boll_period']),
        ('boll_dev', STRATEGY_PARAMS['boll_dev']),
        ('dmi_period', STRATEGY_PARAMS['dmi_period']),
        ('adx_threshold', STRATEGY_PARAMS['adx_threshold']),
        ('boll_channel_width_threshold', STRATEGY_PARAMS['boll_channel_width_threshold']),
        ('boll_top_percentage', STRATEGY_PARAMS['boll_top_percentage']),
        ('boll_bottom_percentage', STRATEGY_PARAMS['boll_bottom_percentage']),
        # 新增：趋势确认参数
        ('boll_mid_rising_periods', STRATEGY_PARAMS['boll_mid_rising_periods']),
        ('volume_ratio_threshold', STRATEGY_PARAMS['volume_ratio_threshold']),
        ('atr_volatility_multiplier', STRATEGY_PARAMS['atr_volatility_multiplier']),
        # 趋势类型定义
        ('sideways_trend', STRATEGY_PARAMS['sideways_trend']),
        ('bullish_trend', STRATEGY_PARAMS['bullish_trend']),
        ('bearish_trend', STRATEGY_PARAMS['bearish_trend']),
    )

    def __init__(self):
        # 调用父类的__init__方法
        super().__init__()
        
        # 打印参数值，确认是否正确获取
        print(f"TrendDetector参数boll_period: {self.params.boll_period}")
        print(f"TrendDetector参数boll_dev: {self.params.boll_dev}")
        print(f"TrendDetector参数dmi_period: {self.params.dmi_period}")
        print(f"TrendDetector参数adx_threshold: {self.params.adx_threshold}")
        
        # 判断是否为日线级别数据，并存储为实例变量
        self.is_daily = (self.data._timeframe == bt.TimeFrame.Days) and (self.data._compression == 1)
        print(f"is_daily: {self.is_daily} timeframe: {self.data._timeframe} compression: {self.data._compression}")
        print(f"当前数据周期: {'日线级别'  if self.is_daily else f'{self.data._timeframe}周期，压缩率{self.data._compression}'}")

        # 使用Backtrader内置的DMI指标，只使用period参数
        self.dmi = bt.indicators.DMI(
            self.data, 
            period=self.params.dmi_period
        )
        
        # 检查DMI指标的实际参数
        print(f"DMI指标实际周期: {self.dmi.params.period}")
        print(f"boll_period指标实际周期: {self.params.boll_period}")

        # 使用Backtrader内置的BOLL指标
        self.boll = bt.indicators.BBands(
            self.data,
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )
        
        # 新增：ATR指标 - 判断趋势强度和波动率
        self.atr = bt.indicators.ATR(
            self.data,
            period=STRATEGY_PARAMS['atr_period']
        )
        
        # 新增：成交量指标 - 简单移动平均线
        self.volume_sma = bt.indicators.SMA(
            self.data.volume,
            period=5  # 5期成交量均线
        )

    def next(self):
        """
        计算当前趋势类型 - 整合DMI+BOLL+成交量+ATR技术指标
        - 震荡趋势：ADX < adx_threshold 且 (价格在BOLL通道内或通道宽度小于阈值)
        - 单边上涨趋势：+DI > -DI 且 ADX >= adx_threshold 且 
                      (1) 中轨连续上升N期 
                      (2) 成交量放大确认 
                      (3) ATR确认趋势强度
        - 单边下跌趋势：-DI > +DI 且 ADX >= adx_threshold 且 
                      (1) 中轨连续下降N期 
                      (2) 成交量放大确认（可选）
                      (3) ATR确认趋势强度
        """
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plusDI[0]
        minus_di_value = self.dmi.minusDI[0]
        
        # BOLL指标数据
        close = self.data.close[0]
        boll_top = self.boll.lines.top[0]
        boll_mid = self.boll.lines.mid[0]
        boll_bot = self.boll.lines.bot[0]
        
        # 历史数据（确保有足够的数据点）
        required_data_length = self.params.boll_mid_rising_periods + 5
        has_enough_data = len(self.data) > required_data_length
        
        # 价格在BOLL通道内的判断
        in_boll_channel = (boll_bot <= close <= boll_top)
        
        # 计算BOLL通道宽度占比
        boll_width = (boll_top - boll_bot) / boll_mid * 100
        is_narrow_channel = boll_width < self.params.boll_channel_width_threshold  # 窄幅震荡判断
        
        # 新增优化1：BOLL中轨连续上升/下降期数判断
        is_boll_mid_rising = False
        is_boll_mid_falling = False
        
        if has_enough_data:
            # 检查中轨是否连续上升
            rising_count = 0
            for i in range(1, self.params.boll_mid_rising_periods + 1):
                if boll_mid > self.boll.lines.mid[-i]:
                    rising_count += 1
                else:
                    break
            is_boll_mid_rising = (rising_count == self.params.boll_mid_rising_periods)
            
            # 检查中轨是否连续下降
            falling_count = 0
            for i in range(1, self.params.boll_mid_rising_periods + 1):
                if boll_mid < self.boll.lines.mid[-i]:
                    falling_count += 1
                else:
                    break
            is_boll_mid_falling = (falling_count == self.params.boll_mid_rising_periods)
        
        # 新增优化2：成交量确认上涨趋势的有效性
        is_volume_confirm = False
        if has_enough_data:
            # 当前成交量与5期平均成交量的比值
            current_volume = self.data.volume[0]
            avg_volume = self.volume_sma[0]
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            is_volume_confirm = volume_ratio > self.params.volume_ratio_threshold
        
        # 新增优化3：ATR判断趋势强度和波动率
        is_trend_strong = False
        if has_enough_data:
            # 计算ATR的平均值（过去20期）
            atr_values = [self.atr[-(i+1)] for i in range(20)] if len(self.data) > 20 else [self.atr[0]]
            avg_atr = sum(atr_values) / len(atr_values)
            # 当前ATR大于平均ATR的一定倍数，说明趋势强度足够
            is_trend_strong = self.atr[0] > avg_atr * self.params.atr_volatility_multiplier
        
        # 上涨趋势条件优化：综合多个因素
        price_above_mid = close > boll_mid
        is_bullish = (price_above_mid and 
                     is_boll_mid_rising and  # 中轨连续上升
                     is_volume_confirm and   # 成交量放大确认
                     is_trend_strong)        # ATR确认趋势强度
        
        # 下跌趋势条件优化
        price_below_mid = close < boll_mid
        is_bearish = (price_below_mid and 
                     is_boll_mid_falling and  # 中轨连续下降
                     is_trend_strong)         # ATR确认趋势强度
        
        # 综合DMI和BOLL的趋势判断
        # 震荡趋势条件优化：ADX低 + (价格在通道内或通道狭窄)
        if adx_value < self.params.adx_threshold and (in_boll_channel or is_narrow_channel):
            self.lines.trend_type[0] = self.params.sideways_trend
        elif (plus_di_value > minus_di_value and adx_value >= self.params.adx_threshold and is_bullish):
            # DMI显示上涨且满足所有上涨确认条件，确认上涨趋势
            self.lines.trend_type[0] = self.params.bullish_trend
        elif (minus_di_value > plus_di_value and adx_value >= self.params.adx_threshold and is_bearish):
            # DMI显示下跌且满足所有下跌确认条件，确认下跌趋势
            self.lines.trend_type[0] = self.params.bearish_trend
        else:
            # 指标冲突时，默认保持震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend
        
        # 日线级别数据输出详细日志
        if self.is_daily:
            # 获取当前日期
            current_date = self.data.datetime.datetime(0).strftime('%Y-%m-%d')
            
            # 趋势类型名称映射
            trend_type_name = {
                self.params.sideways_trend: "震荡趋势",
                self.params.bullish_trend: "上涨趋势",
                self.params.bearish_trend: "下跌趋势"
            }.get(self.lines.trend_type[0], "未知趋势")
            
            # 格式化数值，保留4位小数
            def format_num(num):
                return round(num, 4)
            
            # 输出详细日志
            print(f"\n===== 日线趋势分析 [{current_date}] =====")
            print(f"收盘价: {format_num(close)}")
            print(f"\nDMI指标:")
            print(f"  ADX: {format_num(adx_value)} (阈值: {self.params.adx_threshold})")
            print(f"  +DI: {format_num(plus_di_value)}")
            print(f"  -DI: {format_num(minus_di_value)}")
            print(f"  上涨动能强于下跌: {plus_di_value > minus_di_value}")
            
            print(f"\nBOLL指标:")
            print(f"  上轨: {format_num(boll_top)}")
            print(f"  中轨: {format_num(boll_mid)}")
            print(f"  下轨: {format_num(boll_bot)}")
            print(f"  通道宽度: {format_num(boll_width)}% (阈值: {self.params.boll_channel_width_threshold}%)")
            print(f"  价格在通道内: {in_boll_channel}")
            print(f"  通道狭窄: {is_narrow_channel}")
            print(f"  中轨连续上升{self.params.boll_mid_rising_periods}期: {is_boll_mid_rising}")
            print(f"  中轨连续下降{self.params.boll_mid_rising_periods}期: {is_boll_mid_falling}")
            print(f"  价格在中轨上方: {price_above_mid}")
            print(f"  价格在中轨下方: {price_below_mid}")
            
            print(f"\n成交量指标:")
            print(f"  当前成交量: {format_num(self.data.volume[0])}")
            print(f"  5期平均成交量: {format_num(avg_volume)}")
            print(f"  成交量比值: {format_num(volume_ratio)} (阈值: {self.params.volume_ratio_threshold})")
            print(f"  成交量确认: {is_volume_confirm}")
            
            print(f"\nATR指标:")
            print(f"  当前ATR: {format_num(self.atr[0])}")
            print(f"  20期平均ATR: {format_num(avg_atr)}")
            print(f"  ATR比值: {format_num(self.atr[0]/avg_atr) if avg_atr > 0 else 0.0} (阈值: {self.params.atr_volatility_multiplier})")
            print(f"  趋势强度足够: {is_trend_strong}")
            
            print(f"\n趋势判断结果:")
            print(f"  上涨条件满足: {is_bullish}")
            print(f"  下跌条件满足: {is_bearish}")
            print(f"  最终趋势类型: {trend_type_name} ({self.lines.trend_type[0]})")
            print("="*50)