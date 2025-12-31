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
        # 使用Backtrader内置的DMI指标
        # self.dmi = bt.indicators.DMI(
        #     self.data,
        #     period=STRATEGY_PARAMS['dmi_period']  # 使用配置文件中的参数
        # )
        self.dmi = DMI(
            self.data,
            period=STRATEGY_PARAMS['dmi_period']  # 使用配置文件中的参数
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

    # 在next方法中，确保正确访问DMI指标的属性
    def next(self):
        # DMI指标数据
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plus_di[0]  # 使用自定义DMI的plus_di属性（带下划线）
        minus_di_value = self.dmi.minus_di[0]  # 使用自定义DMI的minus_di属性（带下划线）
        
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
            # 计算ATR的平均值（过去20期）
            if len(self.atr) >= 20:
                atr_values = [self.atr[-(i+1)] for i in range(20)]
                avg_atr = sum(atr_values) / len(atr_values)
            else:
                # 数据不足20期时，使用已有的所有数据
                atr_values = [self.atr[-(i+1)] for i in range(len(self.atr))]
                avg_atr = sum(atr_values) / len(atr_values) if atr_values else 0
            
            # 当前ATR大于平均ATR的一定倍数，说明趋势强度足够
            is_trend_strong = self.atr[0] > avg_atr * self.params.atr_volatility_multiplier
        
        # 上涨趋势条件优化：综合多个因素
        price_above_mid = close > boll_mid
        # 修复后
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
        # 震荡趋势条件优化：
        # 1. ADX低 + (价格在通道内或通道狭窄)，OR
        # 2. BOLL中轨既不连续上升也不连续下降（横盘）
        if (adx_value < self.params.adx_threshold and (in_boll_channel or is_narrow_channel)) or \
           (not is_boll_mid_rising and not is_boll_mid_falling):
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
            print(f"  收盘价: {format_num(close)}")
            print(f"\nDMI指标:")
            print(f"  ADX: {format_num(adx_value)} (阈值: {self.params.adx_threshold}), 周期: {self.params.dmi_period}")
            print(f"  +DI: {format_num(plus_di_value)}")
            print(f"  -DI: {format_num(minus_di_value)}")
            print(f"  上涨动能强于下跌: {plus_di_value > minus_di_value}")
            print(f"  配置参数: DMI周期={self.params.dmi_period}, ADX阈值={self.params.adx_threshold}")
            print(f"\nATR指标:")
            print(f"  当前ATR: {format_num(self.atr[0])}")
            print(f"  20期平均ATR: {format_num(avg_atr)}")
            print(
                f"  ATR比值: {format_num(self.atr[0] / avg_atr) if avg_atr > 0 else 0.0} (阈值: {self.params.atr_volatility_multiplier})")
            print(f"  趋势强度足够: {is_trend_strong}")
            print(f"  配置参数: ATR周期={STRATEGY_PARAMS['atr_period']}, 波动率阈值={self.params.atr_volatility_multiplier}")

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
            print(f"  配置参数: BOLL周期={self.params.boll_period}, 标准差={self.params.boll_dev}, 通道宽度阈值={self.params.boll_channel_width_threshold}%, 中轨连续期数={self.params.boll_mid_rising_periods}")
            
            print(f"\n成交量指标:")
            print(f"  当前成交量: {format_num(self.data.volume[0])}")
            print(f"  5期平均成交量: {format_num(avg_volume)}")
            print(f"  成交量比值: {format_num(volume_ratio)} (阈值: {self.params.volume_ratio_threshold})")
            print(f"  成交量确认: {is_volume_confirm}")
            print(f"  配置参数: 成交量移动平均周期=5, 成交量比值阈值={self.params.volume_ratio_threshold}")
            print(f"收盘价: {format_num(close)}")
            print(f"\n趋势判断结果:")
            print(f"  上涨条件满足: {is_bullish}")
            print(f"  下跌条件满足: {is_bearish}")
            print(f"  最终趋势类型: {trend_type_name} ({self.lines.trend_type[0]})")
            print("="*50)