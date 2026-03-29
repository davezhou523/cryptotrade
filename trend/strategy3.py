import backtrader as bt


class Strategy3(bt.Strategy):
    """策略3：4H趋势 + 1H回调 + 15M确认"""

    params = (
        ('printlog', False),
        ('eventlog', True),

        # 周期参数
        ('h4_ema_fast', 21),
        ('h4_ema_slow', 55),
        ('h1_ema_fast', 21),
        ('h1_ema_slow', 55),
        ('h1_rsi_period', 14),
        ('m15_ema_period', 21),
        ('m15_atr_period', 14),
        ('m15_rsi_period', 14),

        # 风控与仓位
        ('risk_per_trade', 0.015),          # 单笔风险 <=2%
        ('max_position_size', 0.28),        # 普通上限（小幅提升资金利用率）
        ('deep_pullback_scale', 0.6),       # 深回调轻仓
        ('pullback_deep_band', 0.003),      # 贴近EMA55判定带
        ('stop_loss_atr_multiplier', 2.0),  # 止损=2ATR
        ('min_holding_bars', 4),            # 最小持仓K线，避免刚入场被EMA噪音洗出
        ('ema_exit_confirm_bars', 2),       # EMA破位连续确认
        ('ema_exit_buffer_atr', 0.2),       # EMA破位缓冲（ATR倍数）

        # 杠杆约束
        ('leverage', 5.0),
        ('max_leverage_ratio', 0.85),

        # 风险限制
        ('max_positions', 1),
        ('max_consecutive_losses', 3),
        ('max_daily_loss_pct', 0.05),
        ('max_drawdown_pct', 0.10),
        ('drawdown_position_scale', 0.5),

        # 过滤
        ('require_both_entry_signals', True),
        ('h1_rsi_long_low', 42),
        ('h1_rsi_long_high', 60),
        ('h1_rsi_short_low', 40),
        ('h1_rsi_short_high', 58),
        ('m15_breakout_lookback', 6),
        ('m15_rsi_bias_long', 52),
        ('m15_rsi_bias_short', 48),

        # 兼容测试脚本参数
        ('volatility_scaling', True),
        ('dynamic_risk_adjustment', True),
    )

    def __init__(self):
        self.data_4h = self.datas[0]
        self.data_1h = self.datas[1]
        self.data_15m = self.datas[2]

        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema55 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_slow)

        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_fast)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_slow)
        self.h1_rsi = bt.indicators.RSI(self.data_1h.close, period=self.params.h1_rsi_period)

        self.m15_ema21 = bt.indicators.EMA(self.data_15m.close, period=self.params.m15_ema_period)
        self.m15_atr = bt.indicators.ATR(self.data_15m, period=self.params.m15_atr_period)
        self.m15_rsi = bt.indicators.RSI(self.data_15m.close, period=self.params.m15_rsi_period)

        self.order = None
        self.current_position = None
        self.entry_direction = None
        self.entry_price = None
        self.entry_time = None
        self.stop_loss = None
        self.take_profit = None
        self.stop_moved_to_cost = False
        self.partial_take_profit_done = False

        self.m15_last_high = None
        self.m15_last_low = None
        self.h1_last_high = None
        self.h1_last_low = None
        self.pullback_scale = 1.0

        self.trade_count = 0
        self.win_count = 0
        self.consecutive_losses = 0
        self.daily_consecutive_losses = 0

        self.current_day = self.data_15m.datetime.date(0)
        self.daily_start_value = self.broker.getvalue()
        self.max_portfolio_value = self.broker.getvalue()
        self.drawdown_position_scale = 1.0
        self.bars_since_entry = 0
        self.ema_break_count = 0

        self.log('=== Strategy3 初始化完成 ===', force=True)

    def log(self, txt, dt=None, force=False):
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_15m.datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

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
                self.log(
                    f'{"做多" if self.entry_direction == "long" else "做空"}入场: '
                    f'价格{order.executed.price:.2f} 数量{abs(order.executed.size):.4f} '
                    f'止损{self.stop_loss:.2f} 止盈{self.take_profit[1]:.2f}'
                )
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
        self.log(f'交易关闭: 净盈亏{pnl:.2f} 累计{self.trade_count} 胜率{win_rate:.2f}%', force=True)

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

    def get_trend_direction(self):
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
        if len(self.data_1h) < self.params.h1_ema_slow + 5:
            return False

        price = self.data_1h.close[0]
        e21 = self.h1_ema21[0]
        e55 = self.h1_ema55[0]
        rsi = self.h1_rsi[0]
        self.pullback_scale = 1.0

        zone_low = min(e21, e55)
        zone_high = max(e21, e55)

        if trend_direction == 'bullish':
            # 不追涨：强趋势区等待
            if price > zone_high:
                return False
            # 结构破坏：放弃
            if price < zone_low:
                return False
            # 健康回调：落在EMA带内
            if not (zone_low <= price <= zone_high):
                return False
            # 回调 vs 反转
            if self.h1_last_low is not None and price < self.h1_last_low:
                return False
            if self.h1_ema21[0] <= self.h1_ema21[-1]:
                return False
            if not (self.params.h1_rsi_long_low <= rsi <= self.params.h1_rsi_long_high):
                return False

            dist_55 = abs(price - e55) / e55 if e55 > 0 else 0
            if dist_55 <= self.params.pullback_deep_band:
                self.pullback_scale = self.params.deep_pullback_scale
            return True

        if trend_direction == 'bearish':
            # 不追空：强趋势区等待
            if price < zone_low:
                return False
            # 结构破坏：放弃
            if price > zone_high:
                return False
            # 健康反弹：落在EMA带内
            if not (zone_low <= price <= zone_high):
                return False
            # 回调 vs 反转
            if self.h1_last_high is not None and price > self.h1_last_high:
                return False
            if self.h1_ema21[0] >= self.h1_ema21[-1]:
                return False
            if not (self.params.h1_rsi_short_low <= rsi <= self.params.h1_rsi_short_high):
                return False

            dist_55 = abs(price - e55) / e55 if e55 > 0 else 0
            if dist_55 <= self.params.pullback_deep_band:
                self.pullback_scale = self.params.deep_pullback_scale
            return True

        return False

    def check_entry_signal(self, trend_direction):
        lookback = self.params.m15_breakout_lookback
        if len(self.data_15m) < lookback + 2:
            return False

        highs = list(self.data_15m.high.get(size=lookback + 1))
        lows = list(self.data_15m.low.get(size=lookback + 1))
        recent_high = max(highs[:-1])
        recent_low = min(lows[:-1])

        if trend_direction == 'bullish':
            rsi_trigger = self.m15_rsi[0] > 50 and self.m15_rsi[-1] <= 50
            rsi_bias_ok = self.m15_rsi[0] >= self.params.m15_rsi_bias_long
            structure_trigger = self.data_15m.close[0] > recent_high
        else:
            rsi_trigger = self.m15_rsi[0] < 50 and self.m15_rsi[-1] >= 50
            rsi_bias_ok = self.m15_rsi[0] <= self.params.m15_rsi_bias_short
            structure_trigger = self.data_15m.close[0] < recent_low

        if self.params.require_both_entry_signals:
            return structure_trigger and (rsi_trigger or rsi_bias_ok)
        return rsi_trigger or structure_trigger

    def update_drawdown_scale(self):
        equity = self.broker.getvalue()
        if equity > self.max_portfolio_value:
            self.max_portfolio_value = equity
        drawdown = (self.max_portfolio_value - equity) / self.max_portfolio_value if self.max_portfolio_value > 0 else 0
        self.drawdown_position_scale = self.params.drawdown_position_scale if drawdown >= self.params.max_drawdown_pct else 1.0

    def risk_management_check(self):
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
        price = self.data_15m.close[0]
        equity = self.broker.getvalue()
        if price <= 0 or equity <= 0:
            return 0

        stop_distance = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if stop_distance <= 0:
            return 0

        risk_pct = min(self.params.risk_per_trade, 0.02)
        risk_amount = equity * risk_pct
        risk_size = risk_amount / stop_distance

        cash_cap = (equity * self.params.max_position_size) / price
        lev_cap = (equity * self.params.leverage * self.params.max_leverage_ratio) / price

        size = min(risk_size, cash_cap, lev_cap)
        size *= self.drawdown_position_scale
        size *= self.pullback_scale

        return max(0, size)

    def set_stop_loss_take_profit(self, direction, entry_price):
        r = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if direction == 'long':
            self.stop_loss = entry_price - r
            self.take_profit = [entry_price + r, entry_price + 2 * r]
        else:
            self.stop_loss = entry_price + r
            self.take_profit = [entry_price - r, entry_price - 2 * r]

    def check_exit_conditions(self):
        pos_size = self.getposition(self.data_15m).size
        if self.current_position is None or abs(pos_size) <= 1e-8:
            return None

        price = self.data_15m.close[0]
        ema = self.m15_ema21[0]
        atr = self.m15_atr[0]
        ema_buffer = atr * self.params.ema_exit_buffer_atr if atr > 0 else 0

        if self.entry_direction == 'long':
            if price <= self.stop_loss:
                return 'stop_loss'

            if price >= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做多 +1R，止损移到成本')

            if price >= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return 'take_profit_partial'

            if self.bars_since_entry >= self.params.min_holding_bars and price < (ema - ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    return 'ema_break_exit'
            else:
                self.ema_break_count = 0

        else:
            if price >= self.stop_loss:
                return 'stop_loss'

            if price <= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做空 +1R，止损移到成本')

            if price <= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return 'take_profit_partial'

            if self.bars_since_entry >= self.params.min_holding_bars and price > (ema + ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    return 'ema_break_exit'
            else:
                self.ema_break_count = 0

        return None

    def next(self):
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

        exit_reason = self.check_exit_conditions()
        if exit_reason:
            self.log(f'触发退出: {exit_reason}')
            if exit_reason == 'take_profit_partial':
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
            self.order = self.buy(data=self.data_15m, size=size)
            self.set_stop_loss_take_profit('long', self.data_15m.close[0])
            self.log('多头入场信号确认', force=True)
        else:
            self.order = self.sell(data=self.data_15m, size=size)
            self.set_stop_loss_take_profit('short', self.data_15m.close[0])
            self.log('空头入场信号确认', force=True)

    def stop(self):
        if self.trade_count > 0:
            win_rate = self.win_count / self.trade_count * 100
            self.log(f'策略结束统计: 交易次数{self.trade_count}, 胜率{win_rate:.1f}%', force=True)
