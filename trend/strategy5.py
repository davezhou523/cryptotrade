import backtrader as bt
#
# 策略5 v4：S3基底 + 趋势交叉入场
#
# 设计哲学：收益/胜率/夏普必须优秀前提下提高交易次数
#
# 对比v3的改进：
# 1. 删除模式B（动量追涨）— 入场点差，降低胜率
# 2. 删除模式D（震荡市）— 无4H方向保护，低质量交易
# 3. 删除渐进追踪止损 — 截断大趋势利润
# 4. 恢复S3出场系统 — 让利润奔跑
# 5. 恢复S3止损1.5×ATR — 减少噪音扫损
# 6. 恢复S3的15M信号 — structure OR rsi（无成交量门槛）
#
# 逻辑框架：
# ① 4H判断趋势方向（EMA21>EMA55=多头，EMA21<EMA55=空头）
#    └── EMA缠绕 → 不交易（同S3）
#
# ② 1H判断入场位置（两模式）
#    模式A - 标准回调：价格在EMA21-EMA55带内（同S3）
#    ├── EMA21必须向上（多头）/向下（空头）
#    ├── RSI 42-60/40-58（同S3）
#    └── 全额仓位
#
#    模式C - 趋势交叉：1H EMA21刚穿越EMA55（S3没有）
#    ├── 价格在EMA21附近0.5×ATR内
#    ├── ADX≥25 + MACD柱正且上升（多头）/负且下降（空头）
#    ├── RSI 42-60/40-58（同S3，不放宽）
#    └── 0.9×仓位（轻微缩放）
#
# ③ 15M判断入场信号（同S3）
#    ├── 结构突破（收盘破前高/前低）OR RSI穿越50
#    └── 无成交量门槛
#
# ④ 风控执行（同S3）
#    ├── 止损 = 1.5×ATR
#    └── 单笔风险 ≤ 3%
#
# ⑤ 持仓管理（同S3）
#    ├── +1R → 保本
#    ├── +3R → 止盈一半
#    └── EMA21破位 → 全部止盈
#
# ⑥ 回撤保护
#    ├── 回撤 ≥ 15% → 仓位缩至50%
#    └── 确保最大回撤 < 15%

class Strategy5(bt.Strategy):
    """策略5 v4：S3基底 + 趋势交叉入场"""

    params = (
        # 日志控制
        ('printlog', None),
        ('eventlog', None),

        # 周期参数
        ('h4_ema_fast', None),
        ('h4_ema_slow', None),
        ('h4_adx_period', None),              # 4H ADX周期（交叉模式用）
        ('h4_adx_strong_threshold', None),    # 兼容参数
        ('h4_adx_min_threshold', None),       # 兼容参数
        ('h1_ema_fast', None),
        ('h1_ema_slow', None),
        ('h1_rsi_period', None),
        ('h1_macd_fast', None),               # 1H MACD快线（交叉模式用）
        ('h1_macd_slow', None),               # 1H MACD慢线
        ('h1_macd_signal', None),             # 1H MACD信号线
        ('h1_atr_period', None),              # 1H ATR（交叉模式距离计算）
        ('m15_ema_period', None),
        ('m15_atr_period', None),
        ('m15_rsi_period', None),
        ('m15_volume_ma_period', None),       # 兼容参数（不使用）
        ('m15_breakout_lookback', None),

        # 风控与仓位
        ('risk_per_trade', None),
        ('max_position_size', None),
        ('strong_trend_boost', None),         # 兼容参数（不使用）
        ('deep_pullback_scale', None),
        ('pullback_deep_band', None),
        ('stop_loss_atr_multiplier', None),   # 止损距离=1.5×ATR（同S3）
        ('min_holding_bars', None),
        ('ema_exit_confirm_bars', None),
        ('ema_exit_buffer_atr', None),

        # 追踪止盈参数（兼容参数，不使用渐进追踪）
        ('tp1_r_multiplier', None),
        ('tp2_r_multiplier', None),
        ('tp3_r_multiplier', None),
        ('tp4_r_multiplier', None),
        ('trailing_stop_atr_multiplier', None),
        ('trailing_tighten1_multiplier', None),
        ('trailing_tighten2_multiplier', None),

        # 动量模式参数（兼容参数，不使用）
        ('momentum_atr_distance', None),
        ('momentum_position_scale', None),
        ('momentum_adx_threshold', None),

        # 趋势交叉模式参数
        ('crossover_atr_distance', None),     # 交叉模式：EMA21附近ATR距离
        ('crossover_position_scale', None),   # 交叉模式仓位缩放
        ('crossover_adx_threshold', None),    # 交叉模式ADX阈值

        # 震荡市模式参数（兼容参数，不使用）
        ('sideways_enabled', None),
        ('sideways_ema_distance', None),
        ('sideways_position_scale', None),
        ('sideways_stop_atr_multiplier', None),
        ('sideways_adx_threshold', None),
        ('sideways_rsi_long_low', None),
        ('sideways_rsi_long_high', None),
        ('sideways_rsi_short_low', None),
        ('sideways_rsi_short_high', None),
        ('sideways_volume_threshold', None),
        ('sideways_trailing_atr_multiplier', None),

        # 杠杆约束
        ('leverage', None),
        ('max_leverage_ratio', None),

        # 风险限制
        ('max_positions', None),
        ('max_consecutive_losses', None),
        ('max_daily_loss_pct', None),
        ('max_drawdown_pct', None),
        ('drawdown_position_scale', None),
        ('hard_drawdown_limit', None),        # 兼容参数（不使用）

        # 入场过滤（同S3）
        ('h1_rsi_long_low', None),
        ('h1_rsi_long_high', None),
        ('h1_rsi_short_low', None),
        ('h1_rsi_short_high', None),
        ('m15_rsi_bias_long', None),
        ('m15_rsi_bias_short', None),
        ('volume_ratio_threshold', None),     # 兼容参数（不使用）
        ('momentum_volume_threshold', None),  # 兼容参数（不使用）

        # 兼容参数
        ('volatility_scaling', None),
        ('dynamic_risk_adjustment', None),
    )

    def __init__(self):
        # 多时间周期数据引用
        self.data_4h = self.datas[0]
        self.data_1h = self.datas[1]
        self.data_15m = self.datas[2]

        # 4小时图指标
        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema55 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_slow)
        self.h4_adx = bt.indicators.DMI(self.data_4h, period=self.params.h4_adx_period).adx

        # 1小时图指标
        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_fast)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_slow)
        self.h1_rsi = bt.indicators.RSI(self.data_1h.close, period=self.params.h1_rsi_period)
        self.h1_macd = bt.indicators.MACD(
            self.data_1h.close,
            period_me1=self.params.h1_macd_fast,
            period_me2=self.params.h1_macd_slow,
            period_signal=self.params.h1_macd_signal,
        )
        self.h1_atr = bt.indicators.ATR(self.data_1h, period=self.params.h1_atr_period)

        # 15分钟图指标
        self.m15_ema21 = bt.indicators.EMA(self.data_15m.close, period=self.params.m15_ema_period)
        self.m15_atr = bt.indicators.ATR(self.data_15m, period=self.params.m15_atr_period)
        self.m15_rsi = bt.indicators.RSI(self.data_15m.close, period=self.params.m15_rsi_period)

        # 订单和仓位状态变量
        self.order = None
        self.current_position = None
        self.entry_direction = None
        self.entry_price = None
        self.entry_time = None
        self.stop_loss = None
        self.take_profit = None
        self.stop_moved_to_cost = False
        self.partial_take_profit_done = False

        # 价格结构跟踪变量
        self.m15_last_high = None
        self.m15_last_low = None
        self.h1_last_high = None
        self.h1_last_low = None
        self.pullback_scale = 1.0

        # 交易统计和风险管理变量
        self.trade_count = 0
        self.win_count = 0
        self.consecutive_losses = 0
        self.daily_consecutive_losses = 0

        # 日级别和回撤管理变量
        self.current_day = self.data_15m.datetime.date(0)
        self.daily_start_value = self.broker.getvalue()
        self.max_portfolio_value = self.broker.getvalue()
        self.drawdown_position_scale_val = 1.0
        self.bars_since_entry = 0
        self.ema_break_count = 0
        self.signal_price = None

        # 入场模式标记
        self.entry_mode = None  # 'pullback' 或 'crossover'

        self.log('=== Strategy5 v4 (S3+交叉) 初始化完成 ===', force=True)

    def log(self, txt, dt=None, force=False):
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_15m.datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def update_levels(self):
        if len(self.data_15m) >= 11:
            highs = list(self.data_15m.high.get(size=11))
            lows = list(self.data_15m.low.get(size=11))
            self.m15_last_high = max(highs[:-1])
            self.m15_last_low = min(lows[:-1])

        if len(self.data_1h) >= 21:
            h1_highs = list(self.data_1h.high.get(size=21))
            h1_lows = list(self.data_1h.low.get(size=21))
            self.h1_last_high = max(h1_highs[:-1])
            self.h1_last_low = min(h1_lows[:-1])

    def get_entry_mode_label(self, mode):
        mode_map = {
            'pullback': '标准回调',
            'crossover': '趋势交叉',
        }
        return mode_map.get(mode, '标准回调')

    def get_trend_direction(self):
        """判断趋势方向 — 同S3：4H横盘时不交易"""
        if len(self.data_4h) < self.params.h4_ema_slow:
            return None

        price = self.data_4h.close[0]
        e21 = self.h4_ema21[0]
        e55 = self.h4_ema55[0]

        if price > e21 > e55:
            return 'bullish'
        if price < e21 < e55:
            return 'bearish'
        return 'sideways'

    def check_pullback_condition(self, trend_direction):
        """
        检查1H入场条件 — 两模式

        模式A - 标准回调（同S3）：价格在EMA21-EMA55带内
        模式C - 趋势交叉：1H EMA21刚穿越EMA55 + 严格确认
        """
        if len(self.data_1h) < self.params.h1_ema_slow + 5:
            return False

        price = self.data_1h.close[0]
        e21 = self.h1_ema21[0]
        e55 = self.h1_ema55[0]
        rsi = self.h1_rsi[0]
        macd_hist = self.h1_macd.macd[0] - self.h1_macd.signal[0]
        prev_macd_hist = self.h1_macd.macd[-1] - self.h1_macd.signal[-1]
        h1_atr = self.h1_atr[0]
        adx = self.h4_adx[0]

        self.pullback_scale = 1.0
        self.entry_mode = None

        zone_low = min(e21, e55)
        zone_high = max(e21, e55)

        if trend_direction == 'bullish':
            # 结构破坏
            if price < zone_low:
                return False

            # 回调 vs 反转
            if self.h1_last_low is not None and price < self.h1_last_low:
                return False

            # EMA21必须向上
            if self.h1_ema21[0] <= self.h1_ema21[-1]:
                return False

            # ── 模式A：标准回调（EMA55 ≤ price ≤ EMA21）──
            if zone_low <= price <= zone_high:
                if not (self.params.h1_rsi_long_low <= rsi <= self.params.h1_rsi_long_high):
                    return False
                # 深回调检测
                dist_55 = abs(price - e55) / e55 if e55 > 0 else 0
                if dist_55 <= self.params.pullback_deep_band:
                    self.pullback_scale = self.params.deep_pullback_scale
                self.entry_mode = 'pullback'
                return True

            # ── 模式C：趋势交叉（1H EMA21刚上穿EMA55）──
            if h1_atr > 0:
                if self.h1_ema21[0] > self.h1_ema55[0] and self.h1_ema21[-1] <= self.h1_ema55[-1]:
                    crossover_upper = e21 + self.params.crossover_atr_distance * h1_atr
                    crossover_lower = e21 - 0.3 * h1_atr
                    if crossover_lower <= price <= crossover_upper:
                        # ADX确认趋势启动
                        if adx >= self.params.crossover_adx_threshold:
                            # MACD确认动量方向
                            if macd_hist > 0 and macd_hist > prev_macd_hist:
                                # RSI同S3标准范围（不放宽）
                                if self.params.h1_rsi_long_low <= rsi <= self.params.h1_rsi_long_high:
                                    self.pullback_scale = self.params.crossover_position_scale
                                    self.entry_mode = 'crossover'
                                    return True

            return False

        if trend_direction == 'bearish':
            # 结构破坏
            if price > zone_high:
                return False

            if self.h1_last_high is not None and price > self.h1_last_high:
                return False

            if self.h1_ema21[0] >= self.h1_ema21[-1]:
                return False

            # ── 模式A：标准回调（EMA21 ≤ price ≤ EMA55）──
            if zone_low <= price <= zone_high:
                if not (self.params.h1_rsi_short_low <= rsi <= self.params.h1_rsi_short_high):
                    return False
                dist_55 = abs(price - e55) / e55 if e55 > 0 else 0
                if dist_55 <= self.params.pullback_deep_band:
                    self.pullback_scale = self.params.deep_pullback_scale
                self.entry_mode = 'pullback'
                return True

            # ── 模式C：趋势交叉（1H EMA21刚下穿EMA55）──
            if h1_atr > 0:
                if self.h1_ema21[0] < self.h1_ema55[0] and self.h1_ema21[-1] >= self.h1_ema55[-1]:
                    crossover_lower = e21 - self.params.crossover_atr_distance * h1_atr
                    crossover_upper = e21 + 0.3 * h1_atr
                    if crossover_lower <= price <= crossover_upper:
                        if adx >= self.params.crossover_adx_threshold:
                            if macd_hist < 0 and macd_hist < prev_macd_hist:
                                if self.params.h1_rsi_short_low <= rsi <= self.params.h1_rsi_short_high:
                                    self.pullback_scale = self.params.crossover_position_scale
                                    self.entry_mode = 'crossover'
                                    return True

            return False

        return False

    def check_entry_signal(self, trend_direction):
        """
        检查15M入场信号 — 同S3：structure_trigger OR rsi_trigger
        无成交量门槛
        """
        lookback = self.params.m15_breakout_lookback
        if len(self.data_15m) < lookback + 2:
            return False

        highs = list(self.data_15m.high.get(size=lookback + 1))
        lows = list(self.data_15m.low.get(size=lookback + 1))
        recent_high = max(highs[:-1])
        recent_low = min(lows[:-1])

        rsi_now = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]

        if trend_direction == 'bullish':
            structure_trigger = self.data_15m.close[0] > recent_high
            rsi_trigger = rsi_now > 50 and rsi_prev <= 50
            rsi_bias_ok = rsi_now >= self.params.m15_rsi_bias_long
            # 同S3：structure OR (rsi_trigger OR rsi_bias)
            return structure_trigger or rsi_trigger or rsi_bias_ok
        elif trend_direction == 'bearish':
            structure_trigger = self.data_15m.close[0] < recent_low
            rsi_trigger = rsi_now < 50 and rsi_prev >= 50
            rsi_bias_ok = rsi_now <= self.params.m15_rsi_bias_short
            return structure_trigger or rsi_trigger or rsi_bias_ok

        return False

    def update_drawdown_scale(self):
        """更新回撤仓位缩放 — 同S3"""
        equity = self.broker.getvalue()
        if equity > self.max_portfolio_value:
            self.max_portfolio_value = equity
        drawdown = (self.max_portfolio_value - equity) / self.max_portfolio_value if self.max_portfolio_value > 0 else 0
        if drawdown >= self.params.max_drawdown_pct:
            self.drawdown_position_scale_val = self.params.drawdown_position_scale
        else:
            self.drawdown_position_scale_val = 1.0

    def risk_management_check(self):
        """风险检查 — 同S3"""
        equity = self.broker.getvalue()

        if self.daily_consecutive_losses >= self.params.max_consecutive_losses:
            return False

        daily_loss = (self.daily_start_value - equity) / self.daily_start_value if self.daily_start_value > 0 else 0
        if daily_loss >= self.params.max_daily_loss_pct:
            self.log(f'日亏损限制触发: {daily_loss*100:.2f}%', force=True)
            return False

        self.update_drawdown_scale()

        position_count = 1 if abs(self.getposition(self.data_15m).size) > 1e-8 else 0
        if position_count >= self.params.max_positions:
            return False

        return True

    def calculate_position_size(self):
        """计算仓位大小 — 同S3"""
        price = self.data_15m.close[0]
        equity = self.broker.getvalue()
        if price <= 0 or equity <= 0:
            return 0

        stop_distance = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if stop_distance <= 0:
            return 0

        risk_pct = min(self.params.risk_per_trade, 0.03)
        risk_amount = equity * risk_pct
        risk_size = risk_amount / stop_distance

        cash_cap = (equity * self.params.max_position_size) / price
        lev_cap = (equity * self.params.leverage * self.params.max_leverage_ratio) / price

        size = min(risk_size, cash_cap, lev_cap)
        size *= self.drawdown_position_scale_val
        size *= self.pullback_scale

        return max(0, size)

    def set_stop_loss_take_profit(self, direction, entry_price):
        """设置止损和止盈 — 同S3：简单阶梯止盈，无追踪止损"""
        r = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if direction == 'long':
            self.stop_loss = entry_price - r
            self.take_profit = [entry_price + r, entry_price + 3 * r]
        else:
            self.stop_loss = entry_price + r
            self.take_profit = [entry_price - r, entry_price - 3 * r]

    def check_exit_conditions(self):
        """检查出场条件 — 同S3：止损→保本→部分止盈→EMA破位"""
        pos_size = self.getposition(self.data_15m).size
        if self.current_position is None or abs(pos_size) <= 1e-8:
            return None

        price = self.data_15m.close[0]
        ema = self.m15_ema21[0]
        atr = self.m15_atr[0]
        ema_buffer = atr * self.params.ema_exit_buffer_atr if atr > 0 else 0

        if self.entry_direction == 'long':
            # 1. 止损
            if price <= self.stop_loss:
                return ('stop_loss', None)

            # 2. +1R保本
            if price >= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做多 +1R，止损移到成本')

            # 3. +3R部分止盈
            if price >= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return ('take_profit_partial', None)

            # 4. EMA破位出场
            if self.bars_since_entry >= self.params.min_holding_bars and price < (ema - ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    break_amount = (ema - ema_buffer) - price
                    self.log(f'多头EMA破位: EMA({ema:.2f})-缓冲({ema_buffer:.2f}) - 价格({price:.2f}) = 破位{break_amount:.2f}点', force=True)
                    return ('ema_break_exit', break_amount)
            else:
                self.ema_break_count = 0

        else:
            # 空头逻辑
            # 1. 止损
            if price >= self.stop_loss:
                return ('stop_loss', None)

            # 2. +1R保本
            if price <= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做空 +1R，止损移到成本')

            # 3. +3R部分止盈
            if price <= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return ('take_profit_partial', None)

            # 4. EMA破位出场
            if self.bars_since_entry >= self.params.min_holding_bars and price > (ema + ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    break_amount = price - (ema + ema_buffer)
                    self.log(f'空头EMA破位: 价格({price:.2f}) - (EMA({ema:.2f})+缓冲({ema_buffer:.2f})) = 破位{break_amount:.2f}点', force=True)
                    return ('ema_break_exit', break_amount)
            else:
                self.ema_break_count = 0

        return None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            pos_size = self.getposition(self.data_15m).size
            if self.current_position is None:
                self.entry_direction = 'long' if order.isbuy() else 'short'
                self.current_position = self.entry_direction
                self.entry_price = order.executed.price
                self.entry_time = bt.num2date(order.executed.dt)
                self.stop_moved_to_cost = False
                self.partial_take_profit_done = False
                self.bars_since_entry = 0
                self.ema_break_count = 0
                if self.signal_price is not None:
                    diff = order.executed.price - self.signal_price
                    self.log(f'价格差异: 信号价{self.signal_price:.2f} 成交价{order.executed.price:.2f} 差异{diff:.2f}')
                mode_text = self.get_entry_mode_label(self.entry_mode)
                self.log(
                    f'{"做多" if self.entry_direction == "long" else "做空"}入场[{mode_text}]: '
                    f'价格{order.executed.price:.2f} 数量{abs(order.executed.size):.4f} '
                    f'止损{self.stop_loss:.2f} 止盈{self.take_profit[1]:.2f}'
                )
                self.signal_price = None
            else:
                if abs(pos_size) > 1e-8:
                    self.log(f'部分平仓: 价格{order.executed.price:.2f} 数量{abs(order.executed.size):.4f}')
                else:
                    self.log(f'全平仓: 价格{order.executed.price:.2f} 数量{abs(order.executed.size):.4f}')
                    self.current_position = None
                    self.entry_direction = None
                    self.entry_price = None
                    self.entry_time = None
                    self.stop_loss = None
                    self.take_profit = None
                    self.stop_moved_to_cost = False
                    self.partial_take_profit_done = False
                    self.pullback_scale = 1.0
                    self.bars_since_entry = 0
                    self.ema_break_count = 0
                    self.entry_mode = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒单', force=True)

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.trade_count += 1
        pnl = trade.pnlcomm
        if pnl > 0:
            self.win_count += 1
            self.consecutive_losses = 0
            self.daily_consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.daily_consecutive_losses += 1

        win_rate = self.win_count / self.trade_count * 100 if self.trade_count else 0
        if hasattr(trade, 'size') and trade.size != 0:
            price_diff = pnl / abs(trade.size)
        else:
            price_diff = 0
        self.log(f'交易关闭: 净盈亏{pnl:.2f} 点数{price_diff:.2f} 累计{self.trade_count} 胜率{win_rate:.2f}%', force=True)

    def build_entry_context(self, trend_direction, size):
        signal_price = self.data_15m.close[0]
        stop_distance = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        equity = self.broker.getvalue()
        risk_pct = min(self.params.risk_per_trade, 0.03)
        risk_amount = equity * risk_pct
        risk_size = risk_amount / stop_distance if stop_distance > 0 else 0
        cash_cap = (equity * self.params.max_position_size) / signal_price if signal_price > 0 else 0
        lev_cap = (equity * self.params.leverage * self.params.max_leverage_ratio) / signal_price if signal_price > 0 else 0
        base_size = min(risk_size, cash_cap, lev_cap) if signal_price > 0 else 0

        return {
            'trend_direction': trend_direction,
            'entry_mode': self.entry_mode,
            'signal_price': signal_price,
            'stop_distance': stop_distance,
            'stop_loss': self.stop_loss,
            'take_profit_1': self.take_profit[0] if self.take_profit else None,
            'take_profit_2': self.take_profit[1] if self.take_profit else None,
            'equity': equity,
            'risk_pct': risk_pct,
            'risk_amount': risk_amount,
            'risk_size': risk_size,
            'cash_cap': cash_cap,
            'lev_cap': lev_cap,
            'base_size': base_size,
            'final_size': size,
            'pullback_scale': self.pullback_scale,
            'drawdown_scale': self.drawdown_position_scale_val,
            'h4_price': self.data_4h.close[0],
            'h4_ema21': self.h4_ema21[0],
            'h4_ema55': self.h4_ema55[0],
            'h4_adx': self.h4_adx[0],
            'h1_price': self.data_1h.close[0],
            'h1_ema21': self.h1_ema21[0],
            'h1_ema55': self.h1_ema55[0],
            'h1_rsi': self.h1_rsi[0],
            'h1_macd_hist': self.h1_macd.macd[0] - self.h1_macd.signal[0],
            'h1_atr': self.h1_atr[0],
            'm15_price': signal_price,
            'm15_rsi': self.m15_rsi[0],
        }

    def log_entry_context(self, context):
        direction_text = '多头' if context['trend_direction'] == 'bullish' else '空头'
        mode_text = self.get_entry_mode_label(context['entry_mode'])
        self.log(
            f'{direction_text}入场理由[{mode_text}]: '
            f'4H价格{context["h4_price"]:.2f}/EMA21 {context["h4_ema21"]:.2f}/EMA55 {context["h4_ema55"]:.2f}/ADX {context["h4_adx"]:.1f}; '
            f'1H价格{context["h1_price"]:.2f}/EMA21 {context["h1_ema21"]:.2f}/EMA55 {context["h1_ema55"]:.2f}/'
            f'RSI {context["h1_rsi"]:.2f}/MACD柱 {context["h1_macd_hist"]:.4f}/ATR {context["h1_atr"]:.2f}; '
            f'15M价格{context["m15_price"]:.2f}/RSI {context["m15_rsi"]:.2f}',
            force=True
        )
        self.log(
            f'{direction_text}仓位: 权益{context["equity"]:.2f} 基础{context["base_size"]:.4f} '
            f'×回撤{context["drawdown_scale"]:.2f} ×模式{context["pullback_scale"]:.2f} = {context["final_size"]:.4f}',
            force=True
        )

    def next(self):
        """主策略逻辑"""
        current_date = self.data_15m.datetime.date(0)
        if current_date != self.current_day:
            self.current_day = current_date
            self.daily_start_value = self.broker.getvalue()
            self.daily_consecutive_losses = 0

        self.update_levels()

        if self.order:
            return

        if self.current_position:
            self.bars_since_entry += 1

        exit_result = self.check_exit_conditions()
        if exit_result:
            if isinstance(exit_result, tuple):
                reason = exit_result[0]
                break_amount = exit_result[1]
            else:
                reason = exit_result
                break_amount = None

            reason_map = {
                'stop_loss': '止损触发',
                'take_profit_partial': '部分止盈',
                'ema_break_exit': 'EMA破位出场',
            }
            reason_text = reason_map.get(reason, reason)

            if break_amount is not None:
                self.log(f'触发退出: {reason_text} 破位{break_amount:.2f}点')
            else:
                self.log(f'触发退出: {reason_text}')

            if reason == 'take_profit_partial':
                pos = self.getposition(self.data_15m).size
                half = abs(pos) / 2
                if half > 0:
                    self.order = self.sell(data=self.data_15m, size=half) if pos > 0 else self.buy(data=self.data_15m, size=half)
                else:
                    self.order = self.close(data=self.data_15m)
            else:
                self.order = self.close(data=self.data_15m)
            return

        if self.current_position:
            return

        if not self.risk_management_check():
            return

        trend_direction = self.get_trend_direction()
        if trend_direction in [None, 'sideways']:
            return

        if not self.check_pullback_condition(trend_direction):
            return

        if not self.check_entry_signal(trend_direction):
            return

        size = self.calculate_position_size()
        if size <= 0:
            return

        if trend_direction == 'bullish':
            self.signal_price = self.data_15m.close[0]
            self.order = self.buy(data=self.data_15m, size=size)
            self.set_stop_loss_take_profit('long', self.data_15m.close[0])
            context = self.build_entry_context(trend_direction, size)
            self.log_entry_context(context)
            self.log('多头入场信号确认', force=True)
        elif trend_direction == 'bearish':
            self.signal_price = self.data_15m.close[0]
            self.order = self.sell(data=self.data_15m, size=size)
            self.set_stop_loss_take_profit('short', self.data_15m.close[0])
            context = self.build_entry_context(trend_direction, size)
            self.log_entry_context(context)
            self.log('空头入场信号确认', force=True)

    def stop(self):
        if self.trade_count > 0:
            win_rate = self.win_count / self.trade_count * 100
            self.log(f'策略结束统计: 交易次数{self.trade_count}, 胜率{win_rate:.1f}%', force=True)