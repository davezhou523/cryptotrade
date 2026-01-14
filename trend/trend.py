# 导入自定义DMI指标
import backtrader as bt
from config import STRATEGY_PARAMS
from datetime import datetime
from .dmi import DMI

class TrendDetector(bt.Indicator):
    """
    趋势判断类，使用DMI+BOLL技术指标判断三种趋势类型
    - 震荡趋势
    - 单边上涨趋势
    - 单边下跌趋势
    """
    lines = ('trend_type', 'adx')  # 添加adx线条
    params = (
        ('boll_period', STRATEGY_PARAMS['boll_period']),
        ('boll_dev', STRATEGY_PARAMS['boll_dev']),
        ('dmi_period', STRATEGY_PARAMS['dmi_period']),
        ('adx_threshold', STRATEGY_PARAMS['adx_threshold']),
        ('adx_buffer_threshold', STRATEGY_PARAMS['adx_buffer_threshold']),  # 新增：ADX缓冲阈值
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
        # 使用自定义DMI指标
        self.dmi = DMI(
            self.data,
            period=STRATEGY_PARAMS['dmi_period']
        )

        # 其他指标的创建代码保持不变
        self.boll = bt.indicators.BollingerBands(
            self.data,
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )
        
        self.atr = bt.indicators.ATR(
            self.data,
            period=STRATEGY_PARAMS['atr_period']
        )
        
        # 计算ATR的20期移动平均
        self.atr_sma20 = bt.indicators.SMA(self.atr, period=20)
        
        # 新增：计算成交量的5期移动平均
        self.volume_sma = bt.indicators.SMA(self.data.volume, period=5)
        
        # 新增：检测数据是否为日线级别
        self.is_daily = self.data._timeframe == bt.TimeFrame.Days

    def next(self):
        # DMI指标数据
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plus_di[0]
        minus_di_value = self.dmi.minus_di[0]
        # 将ADX值设置到线条中
        self.lines.adx[0] = adx_value
        # BOLL指标数据
        close = self.data.close[0]
        boll_top = self.boll.lines.top[0]
        boll_mid = self.boll.lines.mid[0]
        boll_bot = self.boll.lines.bot[0]
        
        # 历史数据（确保有足够的数据点）boll_mid_rising_periods：BOLL中轨连续上升的期数要求
        required_data_length = self.params.boll_mid_rising_periods + 5
        has_enough_data = len(self.data) > required_data_length
        
        # 价格位置判断
        price_above_top = close > boll_top  # 价格突破上轨
        price_near_bottom = close < boll_bot * 1.02  # 价格接近下轨（距离下轨2%以内）
        price_above_mid = close > boll_mid
        price_below_mid = close < boll_mid
        
        # 计算BOLL通道宽度占比
        boll_width = (boll_top - boll_bot) / boll_mid * 100
        is_narrow_channel = boll_width < self.params.boll_channel_width_threshold  # 窄幅震荡判断
        
        # BOLL中轨连续上升/下降期数判断
        is_boll_mid_rising = False
        is_boll_mid_falling = False
        
        if has_enough_data:
            # 检查中轨是否连续上升
            rising_count = 0
            for i in range(1, self.params.boll_mid_rising_periods + 1):
                if boll_mid > self.boll.lines.mid[-i]:
                    rising_count += 1
            is_boll_mid_rising = (rising_count >= self.params.boll_mid_rising_periods)
            
            # 检查中轨是否连续下降
            falling_count = 0
            for i in range(1, self.params.boll_mid_rising_periods + 1):
                if boll_mid < self.boll.lines.mid[-i]:
                    falling_count += 1
            is_boll_mid_falling = (falling_count >= self.params.boll_mid_rising_periods)
        
        # 成交量确认
        is_volume_confirm = False
        if has_enough_data and self.data.volume[0] > 0:
            avg_volume = self.volume_sma[0] if self.volume_sma[0] > 0 else 1
            volume_ratio = self.data.volume[0] / avg_volume
            is_volume_confirm = volume_ratio > self.params.volume_ratio_threshold

        # 优化后的is_bullish和is_bearish定义
        strong_bullish_signal = (plus_di_value > minus_di_value * 2)  # +DI远大于-DI
        strong_bearish_signal = (minus_di_value > plus_di_value * 2)  # -DI远大于+DI
        
        is_bullish = (
            (price_above_mid or price_above_top) and 
            plus_di_value > minus_di_value and 
            (is_boll_mid_rising or price_above_top)
        )
        
        is_bearish = (
            (price_below_mid or price_near_bottom) and
            minus_di_value > plus_di_value and
            (is_boll_mid_falling or price_near_bottom)
        )
        
        # 优化后的趋势判断逻辑
        # 趋势判断逻辑优化 - 使用缓冲阈值
        adx_near_threshold = (adx_value >= self.params.adx_threshold - self.params.adx_buffer_threshold)
        # ADX值是否明显低于阈值
        adx_far_below_threshold = (adx_value < self.params.adx_threshold - self.params.adx_buffer_threshold * 2)
        #DI指标的差异幅度判断
        di_diff = abs(plus_di_value - minus_di_value)
        di_total = plus_di_value + minus_di_value
        di_diff_ratio = di_diff / di_total if di_total > 0 else 0
        min_di_diff_ratio = 0.1  # DI差异比例阈值，小于此值视为方向不明确

        # 优化后的趋势判断逻辑
        if (adx_near_threshold and
                plus_di_value > minus_di_value and
                di_diff_ratio >= min_di_diff_ratio and
                is_bullish):
            # 上涨趋势：ADX接近或超过阈值，+DI > -DI且差异足够大，满足上涨条件
            self.lines.trend_type[0] = self.params.bullish_trend
        elif (adx_near_threshold and
              minus_di_value > plus_di_value and
              di_diff_ratio >= min_di_diff_ratio and
              is_bearish):
            # 下跌趋势：ADX接近或超过阈值，-DI > +DI且差异足够大，满足下跌条件
            # 新增：针对明显下跌趋势的特殊判断（如2025-09-22的大阴线）
            if (price_near_bottom or price_below_mid) and minus_di_value > plus_di_value * 1.2 and is_boll_mid_falling:
                self.lines.trend_type[0] = self.params.bearish_trend  # 判定为下跌趋势
            
        elif price_above_top and strong_bullish_signal:
            # 价格突破上轨且上涨动能极强，直接判定为上涨趋势
            self.lines.trend_type[0] = self.params.bullish_trend
        elif price_near_bottom and strong_bearish_signal:
            # 价格突破下轨且下跌动能极强，直接判定为下跌趋势
            self.lines.trend_type[0] = self.params.bearish_trend
        elif ((adx_far_below_threshold or di_diff_ratio < min_di_diff_ratio)
              and is_narrow_channel
              and not is_boll_mid_rising
              and not is_boll_mid_falling):
            # 震荡趋势：ADX明显低于阈值 或 DI差异太小，通道窄且中轨无明显趋势
            self.lines.trend_type[0] = self.params.sideways_trend
        else:
            # 综合判断：考虑所有因素
            if is_bullish and plus_di_value > minus_di_value and di_diff_ratio >= min_di_diff_ratio:
                self.lines.trend_type[0] = self.params.bullish_trend
            elif is_bearish and minus_di_value > plus_di_value and di_diff_ratio >= min_di_diff_ratio:
                self.lines.trend_type[0] = self.params.bearish_trend
            else:
                self.lines.trend_type[0] = self.params.sideways_trend
        # 改进趋势持续性要求：使用移动窗口统计趋势一致性
        current_trend = self.lines.trend_type[0]  # 获取当前周期趋势

        # 检查最近N个周期的趋势一致性
        trend_consistency = 0
        required_consistency = 2  # 需要至少连续2个周期趋势一致

        for i in range(1, required_consistency + 1):
            if len(self.lines.trend_type) > i and self.lines.trend_type[-i] == current_trend:
                trend_consistency += 1

        # 只有当趋势持续足够周期才确认，否则保持震荡
        if trend_consistency < required_consistency and current_trend != self.params.sideways_trend:
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
            # print(f"\n===== 日线趋势分析 [{current_date}] =====")
            # print(f"  收盘价: {format_num(close)}")
            # print(f"  DMI指标: ADX={format_num(adx_value)}, +DI={format_num(plus_di_value)}, -DI={format_num(minus_di_value)}")
            # print(f"  BOLL指标: 上轨={format_num(boll_top)}, 中轨={format_num(boll_mid)}, 下轨={format_num(boll_bot)}")
            # print(f"  价格突破上轨: {price_above_top}, 中轨上升: {is_boll_mid_rising}")
            # print(f"  最终趋势类型: {trend_type_name} ({self.lines.trend_type[0]})")
            # print("="*50)