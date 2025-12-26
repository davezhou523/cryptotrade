import backtrader as bt
from config import STRATEGY_PARAMS
from trend.stochasticRSI import StochasticRSI
from trend.trend import TrendDetector


class TradingStrategy(bt.Strategy):
    """
    增强版策略：结合趋势判断、Stoch RSI指标买卖信号和ATR止损止盈的策略
    使用多时间周期：日线级别判断趋势，1小时级别判断买卖点
    增加多指标验证机制，提高信号准确性
    """
    params = (
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
        # datas[0]: 1小时级别数据（用于判断买卖点）
        self.data_1h_close = self.datas[0].close
        self.data_1h_high = self.datas[0].high
        self.data_1h_low = self.datas[0].low
        self.data_1h_open = self.datas[0].open
        self.data_1h_volume = self.datas[0].volume

        # datas[1]: 日线级别数据（用于判断趋势）
        self.data_daily_close = self.datas[1].close
        self.data_daily_high = self.datas[1].high
        self.data_daily_low = self.datas[1].low

        # 初始化日线级别的趋势检测器
        self.trend_detector_daily = TrendDetector(self.datas[1])

        # ====================== 1小时级别多指标配置 ======================
        # 1. Stoch RSI指标（核心买卖点指标）
        self.stoch_rsi_1h = StochasticRSI(
            period=self.params.rsi_period,
            stoch_period=self.params.stoch_period,
            dperiod=self.params.stoch_d_period
        )

        # 2. ATR指标（波动率和止损止盈计算）
        self.atr_1h = bt.indicators.ATR(
            period=self.params.atr_period
        )

        # 3. 双移动平均线（趋势确认）
        self.fast_ma_1h = bt.indicators.EMA(self.data_1h_close, period=self.params.fast_ma_period)
        self.slow_ma_1h = bt.indicators.EMA(self.data_1h_close, period=self.params.slow_ma_period)

        # 4. BOLL通道（支撑阻力确认）
        self.boll_1h = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )

        # 5. RSI指标（超买超卖确认）
        self.rsi_1h = bt.indicators.RSI(period=self.params.rsi_period)

        # 6. MACD指标（动量确认）
        self.macd_1h = bt.indicators.MACD(
            period_me1=12,
            period_me2=26,
            period_signal=9
        )

        # 7. 成交量指标（量能确认）
        self.volume_ma_5 = bt.indicators.SMA(self.data_1h_volume, period=5)
        self.volume_ma_20 = bt.indicators.SMA(self.data_1h_volume, period=20)

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

    def log(self, txt, dt=None, doprint=False):
        """Logging function"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交或已接受，不做处理
            return

        if order.status in [order.Completed]:
            # 订单已完成
            if order.isbuy():
                # 买入订单完成
                self.log(f'买入执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                # 初始化持仓变量
                self.entry_price = order.executed.price
                self.entry_bar = len(self.datas[0]) - 1

                # 设置止损止盈
                atr_value = self.atr_1h[0]
                self.stop_loss = self.entry_price - self.params.stop_loss_multiplier * atr_value
                self.take_profit = self.entry_price + self.params.take_profit_multiplier * atr_value
                self.trailing_stop = self.entry_price - self.params.trailing_stop_multiplier * atr_value

                # 更新交易计数
                self.trade_count += 1
                current_date = self.datas[0].datetime.date(0)
                if self.last_trade_date != current_date:
                    self.daily_trade_count = 1
                    self.last_trade_date = current_date
                else:
                    self.daily_trade_count += 1

            else:
                # 卖出订单完成
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                # 重置持仓变量
                self.entry_price = None
                self.entry_bar = None
                self.stop_loss = None
                self.take_profit = None
                self.trailing_stop = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # 订单被取消、保证金不足或被拒绝
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
        """
        多指标验证买入信号
        返回: (是否有效, 验证结果详细信息)
        """
        validation_results = []
        valid_conditions = 0
        total_conditions = 7

        # 获取当前指标值
        close = self.data_1h_close[0]
        volume_current = self.data_1h_volume[0]

        # 1. Stoch RSI金叉验证（核心条件，必须满足）
        stoch_rsi_cross = (stoch_rsi_k > stoch_rsi_d) and (stoch_rsi_k_prev <= stoch_rsi_d_prev)
        validation_results.append(f"Stoch RSI金叉: {'✅' if stoch_rsi_cross else '❌'}")
        if stoch_rsi_cross:
            valid_conditions += 1

        # 2. 移动平均线验证（放宽条件：不要求严格多头排列，只要求价格在快MA上方）
        price_above_fast_ma = close > self.fast_ma_1h[0]
        validation_results.append(f"价格在快MA上方: {'✅' if price_above_fast_ma else '❌'}")
        if price_above_fast_ma:
            valid_conditions += 1

        # 3. 价格位置验证
        price_above_slow_ma = close > self.slow_ma_1h[0]
        validation_results.append(f"价格在慢MA上方: {'✅' if price_above_slow_ma else '❌'}")
        if price_above_slow_ma:
            valid_conditions += 1

        # 4. 成交量验证（放宽条件：只要求大于均量）
        volume_cond = volume_current > self.volume_ma_5[0]
        validation_results.append(f"成交量放大: {'✅' if volume_cond else '❌'}")
        if volume_cond:
            valid_conditions += 1

        # 5. MACD验证
        macd_cond = self.macd_1h.macd[0] > self.macd_1h.signal[0]
        validation_results.append(f"MACD多头: {'✅' if macd_cond else '❌'}")
        if macd_cond:
            valid_conditions += 1

        # 6. BOLL通道验证（放宽条件：不要求必须在中轨上方）
        boll_cond = close > self.boll_1h.bot[0]  # 价格在BOLL下轨上方即可
        validation_results.append(f"价格在BOLL下轨上方: {'✅' if boll_cond else '❌'}")
        if boll_cond:
            valid_conditions += 1

        # 7. RSI验证（放宽条件：不要求必须大于50）
        rsi_cond = self.rsi_1h[0] > 40  # RSI在40上方即可
        validation_results.append(f"RSI在40上方: {'✅' if rsi_cond else '❌'}")
        if rsi_cond:
            valid_conditions += 1

        # 根据趋势类型设置不同的通过阈值
        if trend_type == 1:  # 上涨趋势
            required = 4  # 需要满足至少4个条件
        elif trend_type == 0:  # 震荡趋势
            required = 3  # 需要满足至少3个条件
        else:  # 下跌趋势
            required = 4  # 需要满足至少4个条件

        # 核心条件（Stoch RSI金叉）必须满足
        is_valid = stoch_rsi_cross and (valid_conditions >= required)
        
        validation_results.append(f"验证结果: {valid_conditions}/{total_conditions} 满足条件 {'✅' if is_valid else '❌'}")
        
        return is_valid, validation_results
    
    def validate_sell_signal(self, stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev):
        """
        多指标验证卖出信号
        返回: (是否有效, 验证结果详细信息)
        """
        validation_results = []
        valid_conditions = 0
        total_conditions = 5
    
        # 获取当前指标值
        close = self.data_1h_close[0]
    
        # 1. Stoch RSI死叉验证（核心条件，必须满足）
        stoch_rsi_cross = (stoch_rsi_k < stoch_rsi_d) and (stoch_rsi_k_prev >= stoch_rsi_d_prev)
        validation_results.append(f"Stoch RSI死叉: {'✅' if stoch_rsi_cross else '❌'}")
        if stoch_rsi_cross:
            valid_conditions += 1
    
        # 2. 移动平均线验证（放宽条件）
        price_below_fast_ma = close < self.fast_ma_1h[0]
        validation_results.append(f"价格在快MA下方: {'✅' if price_below_fast_ma else '❌'}")
        if price_below_fast_ma:
            valid_conditions += 1
    
        # 3. MACD验证
        macd_cond = self.macd_1h.macd[0] < self.macd_1h.signal[0]
        validation_results.append(f"MACD空头: {'✅' if macd_cond else '❌'}")
        if macd_cond:
            valid_conditions += 1
    
        # 4. BOLL通道验证（放宽条件）
        boll_cond = close < self.boll_1h.top[0]  # 价格在BOLL上轨下方即可
        validation_results.append(f"价格在BOLL上轨下方: {'✅' if boll_cond else '❌'}")
        if boll_cond:
            valid_conditions += 1
    
        # 5. RSI验证（放宽条件）
        rsi_cond = self.rsi_1h[0] < 60  # RSI在60下方即可
        validation_results.append(f"RSI在60下方: {'✅' if rsi_cond else '❌'}")
        if rsi_cond:
            valid_conditions += 1
    
        # 设置通过阈值
        required = 3  # 需要满足至少3个条件
    
        # 核心条件（Stoch RSI死叉）必须满足
        is_valid = stoch_rsi_cross and (valid_conditions >= required)
        
        validation_results.append(f"验证结果: {valid_conditions}/{total_conditions} 满足条件 {'✅' if is_valid else '❌'}")
        
        return is_valid, validation_results

    def next(self):
        """主策略逻辑，每个数据点执行一次"""
        if self.order:
            return

        # 记录当前价格（1小时级别）
        self.log(f'当前价格: {self.data_1h_close[0]:.2f}')

        # 获取1小时级别的Stoch RSI指标值
        stoch_rsi_k = self.stoch_rsi_1h.percK[0]
        stoch_rsi_d = self.stoch_rsi_1h.percD[0]

        # 获取前一周期的Stoch RSI值
        stoch_rsi_k_prev = self.stoch_rsi_1h.percK[-1]
        stoch_rsi_d_prev = self.stoch_rsi_1h.percD[-1]

        # 获取1小时级别的技术指标值
        atr_value = self.atr_1h[0]

        # 获取1小时级别的BOLL指标值
        boll_mid = self.boll_1h.mid[0]
        boll_bot = self.boll_1h.bot[0]
        boll_top = self.boll_1h.top[0]

        # 获取1小时级别的RSI指标值
        rsi_value = self.rsi_1h[0]

        # 获取成交量信息
        volume_current = self.data_1h_volume[0]
        volume_ma_5 = self.volume_ma_5[0] if len(self.volume_ma_5) > 0 else volume_current
        volume_ma_20 = self.volume_ma_20[0] if len(self.volume_ma_20) > 0 else volume_current

        # 获取日线级别的趋势类型
        trend_type = self.trend_detector_daily.trend_type[0]

        # 打印调试信息
        self.log(f'日线趋势: {self.trend_names.get(trend_type, "未知")}')
        self.log(f'1小时Stoch RSI: K={stoch_rsi_k:.2f}, D={stoch_rsi_d:.2f}')
        self.log(f'1小时双均线: 快MA={self.fast_ma_1h[0]:.2f}, 慢MA={self.slow_ma_1h[0]:.2f}')

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
                new_trailing_stop = self.data_1h_close[0] - self.params.trailing_stop_multiplier * atr_value
            elif trend_type == 0:  # 震荡趋势
                new_trailing_stop = self.data_1h_close[0] - 1.5 * atr_value  # 降低震荡趋势的止损幅度
            else:  # 下跌趋势
                new_trailing_stop = self.data_1h_close[0] - 1.0 * atr_value  # 降低下跌趋势的止损幅度

            if new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop
                self.log(f'移动止损更新: {self.trailing_stop:.2f}')

            # 卖出信号1：Stoch RSI超买且死叉，通过多指标验证
            if (stoch_rsi_k > self.params.overbought):
                sell_valid, validation_results = self.validate_sell_signal(stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev,
                                                                           stoch_rsi_d_prev)
                if sell_valid:
                    self.log('1小时Stoch RSI超买且死叉，多指标验证通过，执行卖出')
                    for result in validation_results:
                        self.log(f'  {result}')
                    self.order = self.sell(size=self.position.size)

            # 卖出信号2：价格连续两根K线跌破慢MA
            elif (self.data_1h_close[0] < self.slow_ma_1h[0]) and (self.data_1h_close[-1] < self.slow_ma_1h[-1]):
                self.log(f'1小时价格连续两根K线跌破慢MA，执行卖出')
                self.order = self.sell(size=self.position.size)

            # 卖出信号3：ATR突破（波动性增加时保护利润）
            elif (self.data_1h_high[0] - self.data_1h_low[0]) > atr_value * 2.5:
                self.log(f'ATR突破，执行卖出保护利润')
                self.order = self.sell(size=self.position.size)

            # 止损止盈检查
            elif self.data_1h_close[0] <= self.stop_loss:
                self.log(f'触发止损，执行卖出')
                self.order = self.sell(size=self.position.size)
            elif self.data_1h_close[0] <= self.trailing_stop:
                self.log(f'触发移动止损，执行卖出')
                self.order = self.sell(size=self.position.size)
            elif self.data_1h_close[0] >= self.take_profit:
                self.log(f'触发止盈，执行卖出')
                self.order = self.sell(size=self.position.size)

        else:  # 没有仓位，考虑买入
            # 检查每日交易次数限制
            current_date = self.datas[0].datetime.date(0)
            if self.last_trade_date == current_date and self.daily_trade_count >= self.params.max_trades_per_day:
                self.log(f'每日交易次数已达上限 ({self.params.max_trades_per_day}次)')
                return

            # 买入信号条件：根据趋势类型调整
            buy_condition = False

            # 根据日线趋势类型调整买入条件（1小时级别）
            if trend_type == 1:  # 日线上涨趋势
                # 上涨趋势中需要明确的买入信号
                buy_valid, validation_results = self.validate_buy_signal(trend_type, stoch_rsi_k, stoch_rsi_d,
                                                                       stoch_rsi_k_prev, stoch_rsi_d_prev)
                if buy_valid:
                    buy_condition = True
                    self.log('上涨趋势下多指标买入信号验证通过:')
                    for result in validation_results:
                        self.log(f'  {result}')

            elif trend_type == 0:  # 日线震荡趋势
                # 震荡趋势中需要更明确的超卖信号
                if (stoch_rsi_k < 40):  # 放宽震荡趋势中超卖阈值
                    buy_valid, validation_results = self.validate_buy_signal(trend_type, stoch_rsi_k, stoch_rsi_d,
                                                                           stoch_rsi_k_prev, stoch_rsi_d_prev)
                    if buy_valid:
                        buy_condition = True
                        self.log('震荡趋势下多指标买入信号验证通过:')
                        for result in validation_results:
                            self.log(f'  {result}')

            else:  # 日线下跌趋势
                # 下跌趋势中需要非常明确的超卖信号（谨慎买入）
                if (stoch_rsi_k < 30):  # 放宽下跌趋势中超卖阈值
                    # 价格接近BOLL下轨
                    if (self.data_1h_close[0] <= boll_bot * 1.02):  # 放宽价格接近BOLL下轨的条件
                        # 成交量明显放大
                        if volume_current > self.volume_ma_20[0] * 1.2:  # 降低成交量放大要求
                            buy_valid, validation_results = self.validate_buy_signal(trend_type, stoch_rsi_k,
                                                                                     stoch_rsi_d, stoch_rsi_k_prev,
                                                                                     stoch_rsi_d_prev)
                            if buy_valid:
                                buy_condition = True
                                self.log('下跌趋势下多指标买入信号验证通过:')
                                for result in validation_results:
                                    self.log(f'  {result}')

            if buy_condition:
                self.log(f'买入信号确认，执行买入 | 当前价格: {self.data_1h_close[0]:.2f}')

                # 计算买入手数 - 基于风险的头寸管理
                cash = self.broker.getcash()
                value = self.broker.getvalue()

                # 确保使用正数计算风险金额
                safe_value = max(value, 0)
                safe_cash = max(cash, 0)

                # 计算基于风险的头寸大小
                risk_amount = safe_value * self.params.max_loss_per_trade
                if atr_value > 0:
                    # 根据市场波动率动态调整仓位
                    if atr_value > (self.atr_1h[-1] * 1.5) and len(self.atr_1h) > 1:
                        # 高波动率时降低仓位
                        position_size_risk = risk_amount / (self.params.stop_loss_multiplier * atr_value) * 0.7
                    else:
                        position_size_risk = risk_amount / (self.params.stop_loss_multiplier * atr_value)
                else:
                    position_size_risk = safe_cash / self.data_1h_close[0]

                # 计算基于可用资金的头寸大小（使用更保守的比例）
                cash_size = (safe_cash * 0.7) / self.data_1h_close[0]  # 最多使用70%的可用资金

                # 确保头寸大小为正数
                position_size_risk = max(position_size_risk, 0)
                cash_size = max(cash_size, 0)

                # 取较小的头寸大小
                position_size = min(position_size_risk, cash_size)

                if position_size > 0.0001:  # 设置最小交易数量
                    self.log(f'买入数量: {position_size:.4f}')
                    
                    # 预先计算止损止盈价位用于日志记录
                    current_price = self.data_1h_close[0]
                    atr_value = self.atr_1h[0]
                    # 根据当前价格和ATR预先计算预期的止损止盈
                    expected_stop_loss = current_price - self.params.stop_loss_multiplier * atr_value
                    expected_take_profit = current_price + self.params.take_profit_multiplier * atr_value
                    self.log(f'预期止损价位: {expected_stop_loss:.2f}, 预期止盈价位: {expected_take_profit:.2f}')
                    
                    self.order = self.buy(size=position_size)
                    
                    # 记录交易信息
                    self.last_trade_date = self.datas[0].datetime.date(0)
                    self.daily_trade_count += 1
                    self.entry_bar = len(self.datas[0])
                else:
                    self.log(f'可用资金不足或风险过高，无法买入')