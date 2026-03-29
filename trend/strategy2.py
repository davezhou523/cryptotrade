import backtrader as bt
from trend.stochasticRSI import StochasticRSI


class Strategy2(bt.Strategy):
    """策略2：4H趋势 + 1H回调 + 15M触发"""

    params = (
        ('printlog', False),
        ('eventlog', True),

        # 周期参数
        ('h4_ema_fast', 21),
        ('h4_ema_slow', 55),
        ('h4_atr_period', 14),
        ('h4_atr_ma_period', 20),
        ('h1_rsi_period', 14),
        ('m15_atr_period', 14),
        ('m15_rsi_period', 14),
        ('m15_stoch_rsi_period', 14),

        # 资金与风控
        ('risk_per_trade', 0.01),
        ('max_position_size', 0.20),
        ('stop_loss_atr_multiplier', 2.0),
        ('leverage', 5.0),
        ('max_leverage_ratio', 0.8),
        ('max_positions', 3),

        # 过滤阈值
        ('atr_low_threshold', 0.8),
        ('atr_high_threshold', 1.2),
        ('atr_filter_log_interval_bars', 96),
        ('ema_entangle_threshold', 0.003),
        ('overextend_to_ema21', 0.02),
        ('no_trend_rsi_band', 3.0),

        # 风险限制
        ('max_consecutive_losses', 3),
        ('max_daily_loss_pct', 0.05),
        ('max_drawdown_pct', 0.10),
        ('drawdown_position_scale', 0.5),

        # 退出
        ('momentum_weak_threshold', 82),
        ('momentum_weak_confirm_bars', 2),
        ('min_holding_bars', 4),
        ('trend_end_min_holding_bars', 8),
        ('trend_end_confirm_bars', 2),
        ('require_both_entry_signals', True),

        # 兼容旧测试参数（可不启用）
        ('volatility_scaling', True),
        ('dynamic_risk_adjustment', False),
    )

    def __init__(self):
        self.data_4h = self.datas[0]
        self.data_1h = self.datas[1]
        self.data_15m = self.datas[2]

        self.order = None
        self.current_position = None
        self.entry_direction = None
        self.entry_price = None
        self.entry_time = None
        self.stop_loss = None
        self.take_profit = None
        self.stop_moved_to_cost = False
        self.partial_take_profit_done = False
        self.bars_since_entry = 0
        self.momentum_weak_count = 0
        self.trend_reversal_count = 0
        self.last_low_vol_log_bar = -10**9

        self.m15_last_low = None
        self.m15_last_high = None

        self.trade_count = 0
        self.win_count = 0
        self.consecutive_losses = 0
        self.daily_consecutive_losses = 0
        self.current_day = self.data_15m.datetime.date(0)
        self.daily_start_value = self.broker.getvalue()
        self.max_portfolio_value = self.broker.getvalue()
        self.drawdown_position_scale = 1.0

        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema55 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_slow)
        self.h4_atr = bt.indicators.ATR(self.data_4h, period=self.params.h4_atr_period)
        self.h4_atr_ma = bt.indicators.SMA(self.h4_atr, period=self.params.h4_atr_ma_period)

        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=21)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=55)
        self.h1_rsi = bt.indicators.RSI(self.data_1h.close, period=self.params.h1_rsi_period)

        self.m15_atr = bt.indicators.ATR(self.data_15m, period=self.params.m15_atr_period)
        self.m15_rsi = bt.indicators.RSI(self.data_15m.close, period=self.params.m15_rsi_period)
        self.m15_stoch_rsi = StochasticRSI(self.data_15m, period=self.params.m15_stoch_rsi_period)

        self.log('=== Strategy2 初始化完成 ===', force=True)

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
                self.bars_since_entry = 0
                self.momentum_weak_count = 0
                self.trend_reversal_count = 0
                self.stop_moved_to_cost = False
                self.partial_take_profit_done = False
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
                    self.bars_since_entry = 0
                    self.momentum_weak_count = 0
                    self.trend_reversal_count = 0

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

    def update_structure_levels(self):
        if len(self.data_15m) >= 11:
            recent_lows = list(self.data_15m.low.get(size=11))
            recent_highs = list(self.data_15m.high.get(size=11))
            self.m15_last_low = min(recent_lows[:-1])
            self.m15_last_high = max(recent_highs[:-1])

    def get_trend_direction(self):
        if len(self.data_4h) < max(self.params.h4_ema_slow, self.params.h4_atr_ma_period):
            return None

        ema_gap = abs(self.h4_ema21[0] - self.h4_ema55[0]) / self.data_4h.close[0] if self.data_4h.close[0] else 0
        atr_ratio = self.h4_atr[0] / self.h4_atr_ma[0] if self.h4_atr_ma[0] > 0 else 1.0

        if atr_ratio < self.params.atr_low_threshold and ema_gap <= self.params.ema_entangle_threshold:
            return 'sideways'

        if self.h4_ema21[0] > self.h4_ema55[0]:
            return 'bullish'
        if self.h4_ema21[0] < self.h4_ema55[0]:
            return 'bearish'
        return 'sideways'

    def atr_trade_filter(self):
        if len(self.data_4h) < self.params.h4_atr_ma_period:
            return False
        atr_avg = self.h4_atr_ma[0]
        if atr_avg <= 0:
            return False
        atr_ratio = self.h4_atr[0] / atr_avg
        if atr_ratio < self.params.atr_low_threshold:
            current_bar = len(self.data_15m)
            if current_bar - self.last_low_vol_log_bar >= self.params.atr_filter_log_interval_bars:
                self.log(f'低波动过滤: ATR比率{atr_ratio:.2f} < {self.params.atr_low_threshold:.2f}')
                self.last_low_vol_log_bar = current_bar
            return False
        return True

    def check_pullback_condition(self, trend_direction):
        if len(self.data_1h) < 60:
            return False

        current_price = self.data_1h.close[0]
        rsi = self.h1_rsi[0]

        if trend_direction == 'bullish':
            return (
                current_price <= self.h1_ema21[0] * 1.005 and
                current_price >= self.h1_ema55[0] and
                40 <= rsi <= 50 and
                self.h1_rsi[0] > self.h1_rsi[-1]
            )

        if trend_direction == 'bearish':
            return (
                current_price >= self.h1_ema21[0] * 0.995 and
                current_price <= self.h1_ema55[0] and
                50 <= rsi <= 60 and
                self.h1_rsi[0] < self.h1_rsi[-1]
            )

        return False

    def check_entry_signal(self, trend_direction):
        if len(self.data_15m) < 15:
            return False

        if trend_direction == 'bullish':
            rsi_trigger = self.m15_rsi[0] > 50 and self.m15_rsi[-1] <= 50
            structure_trigger = self.m15_last_high is not None and self.data_15m.close[0] > self.m15_last_high
        else:
            rsi_trigger = self.m15_rsi[0] < 50 and self.m15_rsi[-1] >= 50
            structure_trigger = self.m15_last_low is not None and self.data_15m.close[0] < self.m15_last_low

        if self.params.require_both_entry_signals:
            return rsi_trigger and structure_trigger
        return rsi_trigger or structure_trigger

    def anti_chase_and_no_trend_filter(self, trend_direction):
        # 无趋势过滤：RSI在50附近乱动
        if abs(self.m15_rsi[0] - 50.0) <= self.params.no_trend_rsi_band:
            return False

        # 超涨/超跌不过度追价：价格远离1H EMA21
        base = self.h1_ema21[0]
        if base <= 0:
            return True
        dist = abs(self.data_1h.close[0] - base) / base
        if dist > self.params.overextend_to_ema21:
            if trend_direction == 'bullish' and self.data_1h.close[0] > base:
                return False
            if trend_direction == 'bearish' and self.data_1h.close[0] < base:
                return False
        return True

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

        # 同时持仓 <= 3
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

        # 单笔风险 1~2%（默认1%）
        risk_amount = equity * self.params.risk_per_trade
        risk_size = risk_amount / stop_distance

        # 最大仓位 20%资金 + 杠杆约束
        cash_cap_size = (equity * self.params.max_position_size) / price
        leverage_cap_size = (equity * self.params.leverage * self.params.max_leverage_ratio) / price

        size = min(risk_size, cash_cap_size, leverage_cap_size)
        size *= self.drawdown_position_scale

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

        self.bars_since_entry += 1
        price = self.data_15m.close[0]

        if self.entry_direction == 'long':
            if price <= self.stop_loss:
                return 'stop_loss'

            if price >= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做多 1R达成，止损移到成本')

            if price >= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return 'take_profit_partial'

            if self.data_4h.close[0] < self.h4_ema21[0]:
                self.trend_reversal_count += 1
                if self.bars_since_entry >= self.params.trend_end_min_holding_bars and self.trend_reversal_count >= self.params.trend_end_confirm_bars:
                    return 'trend_end'
            else:
                self.trend_reversal_count = 0

            k_now = self.m15_stoch_rsi.percK[0]
            k_prev = self.m15_stoch_rsi.percK[-1]
            if self.bars_since_entry >= self.params.min_holding_bars and k_now > self.params.momentum_weak_threshold and k_now < k_prev:
                self.momentum_weak_count += 1
                if self.momentum_weak_count >= self.params.momentum_weak_confirm_bars:
                    return 'momentum_weak'
            else:
                self.momentum_weak_count = 0

        else:
            if price >= self.stop_loss:
                return 'stop_loss'

            if price <= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做空 1R达成，止损移到成本')

            if price <= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return 'take_profit_partial'

            if self.data_4h.close[0] > self.h4_ema21[0]:
                self.trend_reversal_count += 1
                if self.bars_since_entry >= self.params.trend_end_min_holding_bars and self.trend_reversal_count >= self.params.trend_end_confirm_bars:
                    return 'trend_end'
            else:
                self.trend_reversal_count = 0

            low_threshold = 100 - self.params.momentum_weak_threshold
            k_now = self.m15_stoch_rsi.percK[0]
            k_prev = self.m15_stoch_rsi.percK[-1]
            if self.bars_since_entry >= self.params.min_holding_bars and k_now < low_threshold and k_now > k_prev:
                self.momentum_weak_count += 1
                if self.momentum_weak_count >= self.params.momentum_weak_confirm_bars:
                    return 'momentum_weak'
            else:
                self.momentum_weak_count = 0

        return None

    def next(self):
        current_date = self.data_15m.datetime.date(0)
        if current_date != self.current_day:
            self.current_day = current_date
            self.daily_start_value = self.broker.getvalue()
            self.daily_consecutive_losses = 0

        self.update_structure_levels()

        if self.order:
            return

        exit_reason = self.check_exit_conditions()
        if exit_reason:
            self.log(f'触发退出: {exit_reason}')
            if exit_reason == 'take_profit_partial':
                pos = self.getposition(self.data_15m).size
                half_size = abs(pos) / 2
                if half_size > 0:
                    self.order = self.sell(data=self.data_15m, size=half_size) if pos > 0 else self.buy(data=self.data_15m, size=half_size)
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

        if not self.atr_trade_filter():
            return

        if not self.check_pullback_condition(trend_direction):
            return

        if not self.check_entry_signal(trend_direction):
            return

        if not self.anti_chase_and_no_trend_filter(trend_direction):
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
