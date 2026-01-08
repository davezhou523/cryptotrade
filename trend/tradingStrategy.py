import backtrader as bt
from config import STRATEGY_PARAMS
from trend.stochasticRSI import StochasticRSI
from trend.trend import TrendDetector

class TradingStrategy(bt.Strategy):
    """
    根据趋势判断买卖点
    增强版策略：结合趋势判断、Stoch RSI指标买卖信号和ATR止损止盈的策略
    使用多时间周期：日线级别判断趋势，{time_period}级别判断买卖点
    增加多指标验证机制，提高信号准确性
    """
    params = (
        # 时间周期参数
        ('time_period', '1h'),

        # 新增：价格波动过滤参数
        ('price_fluctuation_threshold', STRATEGY_PARAMS['price_fluctuation_threshold_default']),
        ('price_fluctuation_threshold_by_period', STRATEGY_PARAMS['price_fluctuation_threshold_by_period']),
        
        # 趋势检测参数
        ('boll_period', STRATEGY_PARAMS['boll_period']),
        ('boll_dev', STRATEGY_PARAMS['boll_dev']),
        ('dmi_period', STRATEGY_PARAMS['dmi_period']),
        ('adx_threshold', STRATEGY_PARAMS['adx_threshold']),

        # Stoch RSI参数
        ('rsi_period', STRATEGY_PARAMS['rsi_period']),
        ('stoch_period', STRATEGY_PARAMS['stoch_period']),
        ('stoch_d_period', STRATEGY_PARAMS['stoch_d_period']),
        ('oversold', STRATEGY_PARAMS['oversold']),
        ('overbought', STRATEGY_PARAMS['overbought']),

        # ATR参数
        ('atr_period', STRATEGY_PARAMS['atr_period']),

        # 止损止盈参数
        ('stop_loss_multiplier', STRATEGY_PARAMS['stop_loss_multiplier']),
        ('take_profit_multiplier', STRATEGY_PARAMS['take_profit_multiplier']),
        ('trailing_stop_multiplier', STRATEGY_PARAMS['trailing_stop_multiplier']),

        # 移动平均线参数
        ('ma_period', STRATEGY_PARAMS['ma_period']),

        # 新增：双均线参数
        ('fast_ma_period', 10),  # 快速MA
        ('slow_ma_period', 60),  # 慢速MA

        # 风险控制参数
        ('max_loss_per_trade', STRATEGY_PARAMS['max_loss_per_trade']),
        ('min_hold_periods', STRATEGY_PARAMS['min_hold_periods']),
        ('max_trades_per_day', STRATEGY_PARAMS['max_trades_per_day']),

        ('printlog', STRATEGY_PARAMS['printlog']),
    )

    def __init__(self):
        # 初始化数据引用
        # datas[0]: 指定时间周期数据（用于判断买卖点）
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_open = self.datas[0].open
        self.data_volume = self.datas[0].volume
        # 新增：RSI背离检测相关变量
        self.rsi_history = []
        self.price_history = []
        self.max_history_length = 10  # 用于背离检测的历史数据长度
        # 新增：时间窗口过滤参数
        self.avoid_hours = [0, 8, 20]  # UTC时间，根据实际情况调整
        # 新增：信号强度跟踪
        self.signal_strength = 0
        # datas[1]: 日线级别数据（用于判断趋势）
        self.data_daily_close = self.datas[1].close
        self.data_daily_high = self.datas[1].high
        self.data_daily_low = self.datas[1].low

        # 初始化日线级别的趋势检测器
        self.trend_detector_daily = TrendDetector(self.datas[1])

        # ====================== 指定时间周期多指标配置 ======================
        # 1. Stoch RSI指标（核心买卖点指标）
        self.stoch_rsi = StochasticRSI(
            period=self.params.rsi_period,
            stoch_period=self.params.stoch_period,
            dperiod=self.params.stoch_d_period
        )

        # 2. ATR指标（波动率和止损止盈计算）
        self.atr = bt.indicators.ATR(
            period=self.params.atr_period
        )

        # 3. 双移动平均线（趋势确认）
        self.fast_ma = bt.indicators.EMA(self.data_close, period=self.params.fast_ma_period)
        self.slow_ma = bt.indicators.EMA(self.data_close, period=self.params.slow_ma_period)

        # 4. BOLL通道（支撑阻力确认）
        self.boll = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )

        # 5. RSI指标（超买超卖确认）
        self.rsi = bt.indicators.RSI(period=self.params.rsi_period)

        # 6. MACD指标（动量确认）
        self.macd = bt.indicators.MACD(
            period_me1=12,
            period_me2=26,
            period_signal=9
        )

        # 7. 成交量指标（量能确认）
        self.volume_ma_5 = bt.indicators.SMA(self.data_volume, period=5)
        self.volume_ma_20 = bt.indicators.SMA(self.data_volume, period=20)
        # 动态设置价格波动过滤阈值
        self.price_fluctuation_threshold = self.params.price_fluctuation_threshold_by_period.get(
            self.params.time_period,
            self.params.price_fluctuation_threshold
        )
        # 跟踪订单状态
        self.order = None
        self.stop_loss = None
        self.take_profit = None
        self.trailing_stop = None
        self.entry_price = None
        self.entry_bar = None

        # 趋势名称映射
        self.trend_names = {
            0: '震荡趋势',
            1: '单边上涨趋势',
            -1: '单边下跌趋势'
        }

        # 跟踪交易数量
        self.trade_count = 0
        self.daily_trade_count = 0
        self.last_trade_date = None

    # 在tradingStrategy.py中修改log方法
    def log(self, txt, dt=None, doprint=False):
        """Logging function"""
        if True:  # 关闭所有日志输出
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    # 在tradingStrategy.py的notify_order方法中
    def notify_order(self, order):
        """订单状态通知 - 修复做空止盈止损设置"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                # 买入订单完成（做多开仓）
                self.log(f'买入执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                self.entry_price = order.executed.price
                self.entry_bar = len(self.datas[0]) - 1
        
                # 获取当前日线趋势
                trend_type = self.trend_detector_daily.trend_type[0] if len(self.trend_detector_daily.trend_type) > 0 else 0
        
                # 根据趋势动态调整止损止盈倍数
                if trend_type == 1:  # 上涨趋势
                    stop_loss_multiplier = self.params.stop_loss_multiplier * 1.5
                    take_profit_multiplier = self.params.take_profit_multiplier * 2.0
                elif trend_type == 0:  # 震荡趋势
                    stop_loss_multiplier = self.params.stop_loss_multiplier * 1.0
                    take_profit_multiplier = self.params.take_profit_multiplier * 1.2
                else:  # 下跌趋势
                    stop_loss_multiplier = self.params.stop_loss_multiplier * 0.8
                    take_profit_multiplier = self.params.take_profit_multiplier * 1.5
        
                # 设置做多止盈止损
                atr_value = self.atr[0]
                self.stop_loss = self.entry_price - stop_loss_multiplier * atr_value
                self.take_profit = self.entry_price + take_profit_multiplier * atr_value
                self.trailing_stop = self.entry_price - stop_loss_multiplier * atr_value
        
                self.log(f'做多止损设置: {self.stop_loss:.2f} | 止盈设置: {self.take_profit:.2f}')
                
            else:  # 卖出订单完成
                # 判断是卖出平仓还是卖出开仓（做空）
                if self.position.size < 0:  # 卖出后持仓为负，说明是做空开仓
                    self.log(f'做空开仓 | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f}')
                    self.entry_price = order.executed.price
                    self.entry_bar = len(self.datas[0]) - 1
        
                    # 获取当前日线趋势
                    trend_type = self.trend_detector_daily.trend_type[0] if len(self.trend_detector_daily.trend_type) > 0 else 0
        
                    # 根据趋势动态调整止损止盈倍数（做空场景）
                    if trend_type == -1:  # 下跌趋势
                        stop_loss_multiplier = self.params.stop_loss_multiplier * 1.5  # 给足波动空间
                        take_profit_multiplier = self.params.take_profit_multiplier * 2.0  # 顺势拿大利润
                    elif trend_type == 0:  # 震荡趋势
                        stop_loss_multiplier = self.params.stop_loss_multiplier * 1.0  # 严格止损
                        take_profit_multiplier = self.params.take_profit_multiplier * 1.2  # 快速止盈
                    else:  # 上涨趋势（反弹做空）
                        stop_loss_multiplier = self.params.stop_loss_multiplier * 0.8  # 严格止损
                        take_profit_multiplier = self.params.take_profit_multiplier * 1.5  # 反弹利润
        
                    # 设置做空止盈止损（逻辑与做多相反）
                    atr_value = self.atr[0]
                    self.stop_loss = self.entry_price + stop_loss_multiplier * atr_value  # 做空止损在入场价上方
                    self.take_profit = self.entry_price - take_profit_multiplier * atr_value  # 做空止盈在入场价下方
                    self.trailing_stop = self.entry_price + stop_loss_multiplier * atr_value  # 移动止损也在上方
        
                    self.log(f'做空止损设置: {self.stop_loss:.2f} | 止盈设置: {self.take_profit:.2f}')
                else:
                    # 卖出平仓
                    self.log(f'卖出平仓 | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f}')
                    self.entry_price = None
                    self.entry_bar = None
                    self.stop_loss = None
                    self.take_profit = None
                    self.trailing_stop = None

                # 更新交易计数（无论开仓类型）
                self.trade_count += 1
                current_date = self.datas[0].datetime.date(0)
                if self.last_trade_date != current_date:
                    self.daily_trade_count = 1
                    self.last_trade_date = current_date
                else:
                    self.daily_trade_count += 1

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/被拒绝')

        # 重置订单状态
        self.order = None

    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return

        # 获取交易详情（使用Trade对象的正确属性）
        trade_size = abs(trade.size)  # 获取交易数量（取绝对值，因为卖出时size为负数）
        gross_profit = trade.pnl
        net_profit = trade.pnlcomm
        commission = trade.commission

        # 尝试获取平均买入和卖出价格
        try:
            # 通过history获取详细交易记录
            entry_price = trade.history[0].event.price  # 买入价格
            exit_price = trade.history[-1].event.price  # 卖出价格
        except (IndexError, AttributeError):
            # 如果无法获取详细价格，使用平均价格
            entry_price = trade.price
            exit_price = trade.price

        # 计算收益率
        if entry_price > 0 and trade_size > 0:
            profit_percentage = (net_profit / (entry_price * trade_size)) * 100
        else:
            profit_percentage = 0

        # 确定交易结果类型
        if net_profit > 0:
            result_type = "盈利"
            result_color = "✅"
        else:
            result_type = "亏损"
            result_color = "❌"

        # 输出详细交易日志
        self.log(f'{result_color} 交易完成 | {result_type} | 数量: {trade_size:.4f} | 买入价: {entry_price:.2f} | 卖出价: {exit_price:.2f}')
        self.log(f'        毛利润: {gross_profit:.2f} | 手续费: {commission:.2f} | 净利润: {net_profit:.2f}')
        self.log(f'        收益率: {profit_percentage:.2f}%')

    def validate_buy_signal(self, trend_type, stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev):
        """优化后的买入信号验证逻辑 - 结合日线趋势"""
        validation_results = []
        valid_conditions = 0
        total_conditions = 8  # 增加到8个条件

        # 1. Stoch RSI金叉+超卖验证（核心条件）
        stoch_rsi_cross = (stoch_rsi_k > stoch_rsi_d) and (stoch_rsi_k_prev <= stoch_rsi_d_prev)
        stoch_rsi_oversold = stoch_rsi_k < self.params.oversold
        stoch_rsi_buy = stoch_rsi_cross and stoch_rsi_oversold
        validation_results.append(f"Stoch RSI金叉+超卖: {'✅' if stoch_rsi_buy else '❌'}")
        if stoch_rsi_buy:
            valid_conditions += 1

        # 2. 移动平均线验证
        price_above_fast_ma = self.data_close[0] > self.fast_ma[0]
        ma_cross = self.fast_ma[0] > self.slow_ma[0] and self.fast_ma[-1] <= self.slow_ma[-1]
        ma_buy = price_above_fast_ma and (ma_cross or trend_type == 1)
        validation_results.append(f"双均线确认: {'✅' if ma_buy else '❌'}")
        if ma_buy:
            valid_conditions += 1

        # 3. BOLL通道验证（支撑位确认）
        boll_buy = self.data_close[0] > self.boll.bot[0] and self.data_close[-1] <= self.boll.bot[-1]
        validation_results.append(f"BOLL通道支撑: {'✅' if boll_buy else '❌'}")
        if boll_buy:
            valid_conditions += 1

        # 4. RSI底背离验证
        rsi_buy = False
        if len(self.data_close) > 5:
            # 简单的RSI底背离检测
            rsi_buy = self.rsi[0] > self.rsi[-1] and self.data_close[0] < self.data_close[-1]
        validation_results.append(f"RSI底背离: {'✅' if rsi_buy else '❌'}")
        if rsi_buy:
            valid_conditions += 1

        # 5. MACD验证
        macd_buy = self.macd.macd[0] > self.macd.signal[0] and self.macd.macd[0] > 0
        validation_results.append(f"MACD多头: {'✅' if macd_buy else '❌'}")
        if macd_buy:
            valid_conditions += 1

        # 6. 成交量验证
        volume_confirm = self.data_volume[0] > self.volume_ma_5[0] * 1.2
        validation_results.append(f"成交量放大: {'✅' if volume_confirm else '❌'}")
        if volume_confirm:
            valid_conditions += 1

        # 7. 时间窗口过滤
        current_hour = self.data.datetime.datetime(0).hour
        time_filter = current_hour not in self.avoid_hours
        validation_results.append(f"时间窗口合适: {'✅' if time_filter else '❌'}")
        if time_filter:
            valid_conditions += 1

        # 8. 价格波动确认
        price_volatility = (self.data_high[0] - self.data_low[0]) / self.data_close[0] > 0.005
        validation_results.append(f"价格有波动: {'✅' if price_volatility else '❌'}")
        if price_volatility:
            valid_conditions += 1

        # 根据趋势类型设置不同的通过阈值
        thresholds = {1: 5, 0: 4, -1: 6}  # 上涨:5, 震荡:4, 下跌:6
        required = thresholds.get(trend_type, 4)

        is_valid = stoch_rsi_cross and (valid_conditions >= required)

        # 记录信号强度
        self.signal_strength = valid_conditions / total_conditions

        validation_results.append(f"验证结果: {valid_conditions}/{total_conditions} 满足条件 {'✅' if is_valid else '❌'}")
        validation_results.append(f"信号强度: {self.signal_strength:.2f}")

        return is_valid, validation_results

    def validate_sell_signal(self, stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev):
        """优化后的卖出信号验证逻辑 - 增加多种出场条件"""
        validation_results = []
        valid_conditions = 0
        total_conditions = 7  # 增加到7个条件

        # 获取当前指标值
        close = self.data_close[0]
        trend_type = self.trend_detector_daily.trend_type[0]

        # 1. Stoch RSI死叉+超买验证（核心条件）
        stoch_rsi_cross = (stoch_rsi_k < stoch_rsi_d) and (stoch_rsi_k_prev >= stoch_rsi_d_prev)
        stoch_rsi_overbought = stoch_rsi_k > self.params.overbought
        stoch_rsi_sell = stoch_rsi_cross and stoch_rsi_overbought
        validation_results.append(f"Stoch RSI死叉+超买: {'✅' if stoch_rsi_sell else '❌'}")
        if stoch_rsi_sell:
            valid_conditions += 1

        # 2. 移动平均线验证
        price_below_fast_ma = close < self.fast_ma[0]
        ma_dead_cross = self.fast_ma[0] < self.slow_ma[0] and self.fast_ma[-1] >= self.slow_ma[-1]
        ma_sell = price_below_fast_ma and (ma_dead_cross or trend_type == -1)
        validation_results.append(f"双均线确认: {'✅' if ma_sell else '❌'}")
        if ma_sell:
            valid_conditions += 1

        # 3. BOLL通道验证（压力位确认）
        boll_sell = close < self.boll.top[0] and close > self.boll.top[-1]
        validation_results.append(f"BOLL通道压力: {'✅' if boll_sell else '❌'}")
        if boll_sell:
            valid_conditions += 1

        # 4. RSI顶背离验证
        rsi_sell = False
        if len(self.data_close) > 5:
            # 简单的RSI顶背离检测
            rsi_sell = self.rsi[0] < self.rsi[-1] and self.data_close[0] > self.data_close[-1]
        validation_results.append(f"RSI顶背离: {'✅' if rsi_sell else '❌'}")
        if rsi_sell:
            valid_conditions += 1

        # 5. MACD验证
        macd_sell = self.macd.macd[0] < self.macd.signal[0] and self.macd.macd[0] < 0
        validation_results.append(f"MACD空头: {'✅' if macd_sell else '❌'}")
        if macd_sell:
            valid_conditions += 1

        # 6. 成交量验证（出货确认）
        volume_confirm = self.data_volume[0] > self.volume_ma_5[0] * 1.5
        validation_results.append(f"成交量放大（出货）: {'✅' if volume_confirm else '❌'}")
        if volume_confirm:
            valid_conditions += 1

        # 7. ATR波动验证（波动性突变）
        atr_value = self.atr[0]
        atr_spike = (self.data_high[0] - self.data_low[0]) > atr_value * 2.5
        validation_results.append(f"ATR波动异常: {'✅' if atr_spike else '❌'}")
        if atr_spike:
            valid_conditions += 1

        # 根据趋势类型设置不同的通过阈值
        thresholds = {1: 3, 0: 4, -1: 3}  # 上涨:3, 震荡:4, 下跌:3
        required = thresholds.get(trend_type, 3)

        # 核心条件（Stoch RSI死叉）必须满足，或极端行情直接卖出
        is_valid = (stoch_rsi_cross and stoch_rsi_overbought and (valid_conditions >= required)) or \
                   (atr_spike and self.position)

        validation_results.append(f"验证结果: {valid_conditions}/{total_conditions} 满足条件 {'✅' if is_valid else '❌'}")

        return is_valid, validation_results

    def next(self):
        # 时间窗口过滤
        current_hour = self.datas[0].datetime.datetime(0).hour
        if current_hour in self.avoid_hours:
            # self.log(f'当前时间 ({current_hour}:00 UTC) 处于避免交易窗口')
            return
        """主策略逻辑，每个数据点执行一次"""
        if self.order:
            return
        # 优化：动态价格波动过滤 - 根据时间周期调整阈值
        if len(self.data_close) > 1:
            price_change = abs(self.data_close[0] - self.data_close[-1]) / self.data_close[-1]
            # 取较大的阈值（动态阈值或1%）
            effective_threshold = max(self.price_fluctuation_threshold, 0.01)
            if price_change < effective_threshold:
                # self.log(f'价格波动 (价格波动{price_change:.4%}) 小于阈值 ({effective_threshold:.4%})，跳过')
                return
        # 增强价格波动过滤（从0.5%提高到1%）
        if len(self.data_close) > 1:
            price_change = abs(self.data_close[0] - self.data_close[-1]) / self.data_close[-1]
            if price_change < 0.01:  # 波动小于1%时跳过
                return
        # 记录当前价格（指定时间周期）
        self.log(f'当前价格: {self.data_close[0]:.2f}')

        # 获取指定时间周期的Stoch RSI指标值
        stoch_rsi_k = self.stoch_rsi.percK[0]
        stoch_rsi_d = self.stoch_rsi.percD[0]

        # 获取前一周期的Stoch RSI值
        stoch_rsi_k_prev = self.stoch_rsi.percK[-1]
        stoch_rsi_d_prev = self.stoch_rsi.percD[-1]

        # 获取指定时间周期的技术指标值
        atr_value = self.atr[0]

        # 获取指定时间周期的BOLL指标值
        boll_mid = self.boll.mid[0]
        boll_bot = self.boll.bot[0]
        boll_top = self.boll.top[0]

        # 获取指定时间周期的RSI指标值
        rsi_value = self.rsi[0]

        # 获取成交量信息
        volume_current = self.data_volume[0]
        volume_ma_5 = self.volume_ma_5[0] if len(self.volume_ma_5) > 0 else volume_current
        volume_ma_20 = self.volume_ma_20[0] if len(self.volume_ma_20) > 0 else volume_current

        # 获取日线级别的趋势类型
        trend_type = self.trend_detector_daily.trend_type[0]

        # 打印调试信息
        self.log(f'日线趋势: {self.trend_names.get(trend_type, "未知")}')
        self.log(f'{self.params.time_period} Stoch RSI: K={stoch_rsi_k:.2f}, D={stoch_rsi_d:.2f}')
        self.log(f'{self.params.time_period} 双均线: 快MA={self.fast_ma[0]:.2f}, 慢MA={self.slow_ma[0]:.2f}')

        # 检查是否有仓位
        if self.position:
            # 确保entry_bar已初始化
            if self.entry_bar is None:
                self.entry_bar = len(self) - 1  # 假设上一个bar开的仓

            # 检查是否达到最小持仓时间
            if len(self.datas[0]) - self.entry_bar < self.params.min_hold_periods:
                self.log(f'未达到最小持仓时间 {self.params.min_hold_periods}，继续持有')
                return

            # 更新移动止损 - 根据波动率和趋势动态调整
            if trend_type == 1:  # 上涨趋势
                # 计算当前盈利
                current_profit = (self.data_close[0] - self.entry_price) / self.entry_price
                # 盈利超过1ATR后启动移动止盈
                if current_profit > (self.atr[0] / self.entry_price) and self.take_profit is not None:
                    # 移动止盈 = 当前价格 - 1.5倍ATR
                    new_take_profit = self.data_close[0] - 1.5 * self.atr[0]
                    # 只向上调整止盈价格
                    if new_take_profit > self.take_profit:
                        self.take_profit = new_take_profit
                        self.log(f'移动止盈更新: {self.take_profit:.2f}')

                stop_loss_multiplier = self.params.stop_loss_multiplier * 1.2
                new_trailing_stop = self.data_close[0] - stop_loss_multiplier * atr_value
                self.log(f'移动止损更新: {new_trailing_stop:.2f}')
            elif trend_type == 0:  # 震荡趋势
                stop_loss_multiplier = self.params.stop_loss_multiplier
                new_trailing_stop = self.data_close[0] - stop_loss_multiplier * atr_value  # 震荡趋势的止损幅度

            else:  # 下跌趋势
                stop_loss_multiplier = self.params.stop_loss_multiplier * 0.8
                new_trailing_stop = self.data_close[0] - stop_loss_multiplier * atr_value  # 降低下跌趋势的止损幅度

            if self.trailing_stop is not None and new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop
                self.log(f'移动止损更新: {self.trailing_stop:.2f}')

            # 卖出信号1：Stoch RSI超买且死叉，通过多指标验证
            if (stoch_rsi_k > self.params.overbought):
                sell_valid, validation_results = self.validate_sell_signal(stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev,
                                                                           stoch_rsi_d_prev)
                if sell_valid and self.position:  # 添加仓位检查
                    self.log(f'{self.params.time_period} Stoch RSI超买且死叉，多指标验证通过，执行卖出')
                    for result in validation_results:
                        self.log(f'  {result}')
                    self.order = self.close()  # 使用close()代替sell()

            # 卖出信号2：价格连续两根K线跌破慢MA，增加距离条件
            elif (self.data_close[0] < self.slow_ma[0] - 0.005 * self.slow_ma[0]) and \
                    (self.data_close[-1] < self.slow_ma[-1] - 0.005 * self.slow_ma[-1]):
                self.log(f'{self.params.time_period} 价格连续两根K线跌破慢MA，执行卖出')
                # 确保有仓位才执行卖出（平仓）
                if self.position:
                    self.order = self.close()  # 使用close()代替sell()
                else:
                    self.log(f'当前无仓位，忽略卖出信号')

            # 卖出信号3：ATR突破（波动性增加时保护利润）
            elif (self.data_high[0] - self.data_low[0]) > atr_value * 2.5 and self.position:
                self.log(f'ATR突破，执行卖出保护利润')
                self.order = self.close()  # 使用close()代替sell()

            # 止损止盈检查（确保有仓位且参数有效）
            elif self.position and self.stop_loss is not None and self.data_close[0] <= self.stop_loss:
                self.log(f'触发止损，执行卖出')
                self.order = self.close()  # 使用close()代替sell()
            elif self.position and self.trailing_stop is not None and self.data_close[0] <= self.trailing_stop:
                self.log(f'触发移动止损，执行卖出')
                self.order = self.close()  # 使用close()代替sell()
            elif self.position and self.take_profit is not None and self.data_close[0] >= self.take_profit:
                self.log(f'触发止盈，执行卖出')
                self.order = self.close()  # 使用close()代替sell()

        else:  # 没有仓位，考虑买入或做空
            # 检查每日交易次数限制
            current_date = self.datas[0].datetime.date(0)
            if self.last_trade_date == current_date and self.daily_trade_count >= self.params.max_trades_per_day:
                self.log(f'每日交易次数已达上限 ({self.params.max_trades_per_day}次)')
                return

            # 买入和做空信号条件
            buy_condition = False
            short_condition = False

            # 根据日线趋势类型调整买入或做空条件（指定时间周期）
            if trend_type == 1:  # 日线上涨趋势
                # 确保4小时也处于上涨趋势（快MA在慢MA上方）
                if self.fast_ma[0] > self.slow_ma[0]:
                    # 上涨趋势中寻找买入信号
                    buy_valid, validation_results = self.validate_buy_signal(trend_type, stoch_rsi_k, stoch_rsi_d,
                                                                             stoch_rsi_k_prev, stoch_rsi_d_prev)
                    if buy_valid:
                        buy_condition = True
                        self.log('上涨趋势下多指标买入信号验证通过:')
                        for result in validation_results:
                            self.log(f'  {result}')

            elif trend_type == 0:  # 日线震荡趋势
                # 震荡趋势中寻找买入信号
                buy_valid, validation_results = self.validate_buy_signal(trend_type, stoch_rsi_k, stoch_rsi_d,
                                                                         stoch_rsi_k_prev, stoch_rsi_d_prev)
                if buy_valid:
                    buy_condition = True
                    self.log('震荡趋势下多指标买入信号验证通过:')
                    for result in validation_results:
                        self.log(f'  {result}')



            elif trend_type == -1:  # 日线下跌趋势
                # 确保1小时也处于下跌趋势（快MA在慢MA下方）
                if self.fast_ma[0] < self.slow_ma[0]:
                    # 下跌趋势中寻找做空信号
                    sell_valid, validation_results = self.validate_sell_signal(stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev)
                    # 增加额外验证：确保Stoch RSI K线确实超买
                    if sell_valid and stoch_rsi_k > self.params.overbought:
                        short_condition = True
                        self.log(f'{self.params.time_period} Stoch RSI超买且死叉，多指标验证通过，执行做空开仓')
                        for result in validation_results:
                            self.log(f'  {result}')

            # 计算交易数量的公共部分
            account_value = self.broker.getvalue()
            available_cash = self.broker.getcash()
            # 安全检查：如果账户价值为负数，不进行任何交易
            if account_value <= 50 or available_cash <= 50:
                self.log(
                    f'账户价值或可用现金为负数或零，不进行交易 | 账户价值: {account_value:.2f} | 可用现金: {available_cash:.2f}')
                return

            # 计算风险：基于账户总价值，但设置最大风险金额限制
            max_risk_amount = 100  # 设置最大风险金额（无论账户多大，单笔交易最大亏损不超过100）
            if account_value > 0:
                risk_per_trade = min(account_value * self.params.max_loss_per_trade * 0.5, max_risk_amount)
            else:
                self.log(f'账户价值为负数，不进行交易 | 账户价值: {account_value:.2f}')
                return
            # 确保ATR值不为零或非常小
            min_atr_value = 0.01  # 设置最小ATR值
            safe_atr_value = max(atr_value, min_atr_value)

            # 执行买入操作
            if buy_condition:
                # 计算基础交易数量
                buy_size = risk_per_trade / (safe_atr_value * self.params.stop_loss_multiplier)

                # 计算基于可用现金的最大可买入数量（考虑5%的安全边际和手续费）
                max_buy_size = available_cash / (self.data_close[0] * 1.05)  # 5%安全边际

                # 限制交易数量不超过可用资金允许的最大值和绝对最大值
                absolute_max_size = 100  # 设置绝对最大交易数量
                buy_size = min(buy_size, max_buy_size, absolute_max_size)

                # 确保交易数量为正数且合理
                buy_size = max(0.0001, buy_size)

                # 最后检查：确保总投资金额不超过可用现金的90%
                total_investment = buy_size * self.data_close[0]
                if total_investment > available_cash * 0.9:
                    buy_size = (available_cash * 0.9) / self.data_close[0]
                    # 最终安全检查
                if buy_size <= 0 or total_investment <= 0:
                    self.log(f'买入数量或金额无效，不进行交易 | 数量: {buy_size:.4f} | 金额: {total_investment:.2f}')
                    return
                self.log(f'执行买入 | 数量: {buy_size:.4f} | ATR: {atr_value:.6f} | 安全ATR: {safe_atr_value:.6f}')
                self.order = self.buy(size=buy_size)

            # 执行做空操作
            elif short_condition:
                # 做空操作单独的风险计算逻辑 - 使用基于可用现金的风险计算
                short_risk_per_trade = min(available_cash * self.params.max_loss_per_trade * 0.3, max_risk_amount)

                # 修复：使用short_risk_per_trade而不是risk_per_trade
                short_size = short_risk_per_trade / (safe_atr_value * self.params.stop_loss_multiplier)

                # 计算基于可用现金的最大可做空数量（考虑15%的安全边际和手续费）
                max_short_size = available_cash / (self.data_close[0] * 1.15)  # 15%安全边际

                # 限制交易数量不超过可用资金允许的最大值和绝对最大值
                absolute_max_size = 100  # 设置绝对最大交易数量
                short_size = min(short_size, max_short_size, absolute_max_size)

                # 确保交易数量为正数且合理
                short_size = max(0.0001, short_size)

                # 最后检查：确保总投资金额不超过可用现金的85%
                total_investment = short_size * self.data_close[0]
                if total_investment > available_cash * 0.85:
                    short_size = (available_cash * 0.85) / self.data_close[0]
                    # 最终安全检查
                if short_size <= 0 or total_investment <= 0:
                    self.log(f'做空数量或金额无效，不进行交易 | 数量: {short_size:.4f} | 金额: {total_investment:.2f}')
                    return
                self.log(f'执行做空 | 数量: {short_size:.4f} | ATR: {atr_value:.6f} | 安全ATR: {safe_atr_value:.6f}')
                self.order = self.sell(size=short_size)