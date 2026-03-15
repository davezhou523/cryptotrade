import backtrader as bt
from trend.dmi import DMI


class AdvancedStrategy(bt.Strategy):
    """多周期市场结构策略：周线定趋势，日线定状态，4H出信号，1H执行。"""

    params = (
        ('printlog', False),  # 是否打印日志
        ('eventlog', False),  # 是否打印事件日志
        ('weekly_ema_fast', 21),  # 周线快速EMA周期
        ('weekly_ema_slow', 55),  # 周线慢速EMA周期
        ('weekly_adx_trend_threshold', 25),  # 周线ADX趋势阈值
        ('weekly_adx_weak_threshold', 20),  # 周线ADX弱趋势阈值
        ('daily_ema_fast', 21),  # 日线快速EMA周期
        ('daily_ema_slow', 55),  # 日线慢速EMA周期
        ('daily_boll_period', 20),  # 日线布林带周期
        ('daily_boll_dev', 2.0),  # 日线布林带标准差倍数
        ('daily_adx_trend_threshold', 25),  # 日线ADX趋势阈值
        ('daily_adx_sideways_threshold', 20),  # 日线ADX震荡阈值
        ('daily_boll_compression_threshold', 0.05),  # 日线布林带压缩阈值
        ('daily_boll_expansion_threshold', 0.10),  # 日线布林带扩张阈值
        ('dmi_period', 14),  # DMI指标周期
        ('h4_donchian_period', 20),  # 4小时唐奇安通道周期
        ('h4_boll_period', 20),  # 4小时布林带周期
        ('h4_boll_dev', 2.0),  # 4小时布林带标准差倍数
        ('h4_ema_period', 21),  # 4小时EMA周期
        ('volume_ma_period', 20),  # 成交量移动平均周期
        ('atr_period', 14),  # ATR周期
        ('atr_ma_period', 14),  # ATR移动平均周期
        ('h4_volume_ratio_threshold', 1.20),  # 4小时成交量比率阈值
        ('h4_breakout_buffer', 0.0015),  # 4小时突破缓冲比例
        ('h4_breakout_body_ratio', 0.45),  # 4小时突破K线实体比例
        ('h4_breakout_close_strength', 0.65),  # 4小时突破收盘强度
        ('h4_pullback_close_strength', 0.55),  # 4小时回撤收盘强度
        ('h4_pullback_volume_ratio', 0.90),  # 4小时回撤成交量比率
        ('h1_donchian_period', 10),  # 1小时唐奇安通道周期
        ('h1_boll_period', 20),  # 1小时布林带周期
        ('h1_boll_dev', 2.0),  # 1小时布林带标准差倍数
        ('h1_stop_atr_multiplier', 2.0),  # 1小时止损ATR倍数
        ('h1_volume_ratio_threshold', 1.00),  # 1小时成交量比率阈值
        ('h1_breakout_buffer', 0.0008),  # 1小时突破缓冲比例
        ('h1_breakout_body_ratio', 0.35),  # 1小时突破K线实体比例
        ('h1_breakout_close_strength', 0.60),  # 1小时突破收盘强度
        ('require_breakout_retest', True),  # 是否需要突破回踩确认
        ('h1_retest_touch_buffer', 0.0015),  # 1小时回踩触碰缓冲
        ('h1_retest_hold_buffer', 0.0005),  # 1小时回踩保持缓冲
        ('h1_retest_confirm_buffer', 0.0003),  # 1小时回踩确认缓冲
        ('h1_retest_body_ratio', 0.25),  # 1小时回踩K线实体比例
        ('h1_retest_close_strength', 0.55),  # 1小时回踩收盘强度
        ('h1_retest_volume_ratio_threshold', 1.10),  # 1小时回踩成交量比率阈值
        ('h1_reversal_close_strength', 0.55),  # 1小时反转收盘强度
        ('risk_per_trade', 0.02),  # 每笔交易风险比例
        ('rr_ratio', 2.0),  # 风险回报比率
        ('signal_valid_bars', 4),  # 信号有效K线数量
        ('trend_breakeven_rr', 1.0),  # 趋势保本风险回报比
        ('trend_trailing_activation_rr', 2.0),  # 趋势跟踪止损激活风险回报比
        ('trend_trailing_atr_multiplier', 3.0),  # 趋势跟踪止损ATR倍数
        ('trend_ema_exit_buffer', 0.0020),  # 趋势EMA退出缓冲比例
        # 交易费用参数
        ('trading_fee', 0.001),  # 交易手续费 0.100%
        ('slippage', 0.0005),  # 滑点 0.05%
    )

    def __init__(self):
        self.data_weekly = self.datas[0]
        self.data_daily = self.datas[1]
        self.data_4h = self.datas[2]
        self.data_1h = self.datas[3]

        self.order = None
        self.pending_signal = None
        self.pending_entry_signal = None
        self.entry_context = None
        self.entry_price = None
        self.entry_time = None
        self.entry_side = None
        self.entry_exec_price = None
        self.entry_reason = None
        self.pending_exit_reason = None
        self.entry_stop_distance = None
        self.stop_loss = None
        self.take_profit = None
        self.highest_since_entry = None
        self.lowest_since_entry = None
        self.last_4h_bar_time = None
        self.last_macro_snapshot = None
        self.last_market_snapshot = None
        
        # 交易费用跟踪
        self.total_fees = 0.0
        self.current_trade_fees = 0.0
        self.trade_count = 0
        self.last_closed_trade = None
        
        # 打印交易费用设置
        self.log('\n=== 交易费用设置 ===')
        self.log(f'交易手续费: {self.params.trading_fee * 100:.3f}%')
        self.log(f'滑点: {self.params.slippage * 100:.3f}%')
        
        # 打印指标参数设置
        self.log('\n=== 指标参数设置 ===')
        self.log(f'周线EMA21周期: {self.params.weekly_ema_fast}')
        self.log(f'周线EMA55周期: {self.params.weekly_ema_slow}')
        self.log(f'周线ADX趋势阈值: {self.params.weekly_adx_trend_threshold}')
        self.log(f'周线ADX弱趋势阈值: {self.params.weekly_adx_weak_threshold}')
        self.log(f'日线EMA21周期: {self.params.daily_ema_fast}')
        self.log(f'日线EMA55周期: {self.params.daily_ema_slow}')
        self.log(f'日线布林带周期: {self.params.daily_boll_period}, 标准差: {self.params.daily_boll_dev}')
        self.log(f'日线ADX趋势阈值: {self.params.daily_adx_trend_threshold}')
        self.log(f'日线ADX震荡阈值: {self.params.daily_adx_sideways_threshold}')
        self.log(f'DMI周期: {self.params.dmi_period}')
        self.log(f'4H Donchian通道周期: {self.params.h4_donchian_period}')
        self.log(f'4H布林带周期: {self.params.h4_boll_period}, 标准差: {self.params.h4_boll_dev}')
        self.log(f'4H EMA21周期: {self.params.h4_ema_period}')
        self.log(f'4H ATR周期: {self.params.atr_period} (与Binance一致)')
        self.log(f'4H ATR MA周期: {self.params.atr_ma_period}')
        self.log(f'1H Donchian通道周期: {self.params.h1_donchian_period}')
        self.log(f'1H布林带周期: {self.params.h1_boll_period}, 标准差: {self.params.h1_boll_dev}')
        self.log(f'1H ATR周期: {self.params.atr_period} (与Binance一致)')
        self.log(f'成交量MA周期: {self.params.volume_ma_period}')

        self.weekly_ema_fast = bt.indicators.EMA(self.data_weekly.close, period=self.params.weekly_ema_fast)
        self.weekly_ema_slow = bt.indicators.EMA(self.data_weekly.close, period=self.params.weekly_ema_slow)
        self.weekly_dmi = DMI(self.data_weekly, period=self.params.dmi_period)

        self.daily_ema_fast = bt.indicators.EMA(self.data_daily.close, period=self.params.daily_ema_fast)
        self.daily_ema_slow = bt.indicators.EMA(self.data_daily.close, period=self.params.daily_ema_slow)
        self.daily_dmi = DMI(self.data_daily, period=self.params.dmi_period)
        self.daily_boll = bt.indicators.BBands(
            self.data_daily,
            period=self.params.daily_boll_period,
            devfactor=self.params.daily_boll_dev,
        )
        self.daily_boll_width = (self.daily_boll.top - self.daily_boll.bot) / self.daily_boll.mid

        self.h4_donchian_high = bt.indicators.Highest(self.data_4h.high, period=self.params.h4_donchian_period)
        self.h4_donchian_low = bt.indicators.Lowest(self.data_4h.low, period=self.params.h4_donchian_period)
        self.h4_boll = bt.indicators.BBands(
            self.data_4h,
            period=self.params.h4_boll_period,
            devfactor=self.params.h4_boll_dev,
        )
        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_period)
        self.h4_volume_ma = bt.indicators.SMA(self.data_4h.volume, period=self.params.volume_ma_period)
        self.h4_atr = bt.indicators.ATR(self.data_4h, period=self.params.atr_period)
        self.h4_atr_ma = bt.indicators.SMA(self.h4_atr, period=self.params.atr_ma_period)

        self.h1_donchian_high = bt.indicators.Highest(self.data_1h.high, period=self.params.h1_donchian_period)
        self.h1_donchian_low = bt.indicators.Lowest(self.data_1h.low, period=self.params.h1_donchian_period)
        self.h1_boll = bt.indicators.BBands(
            self.data_1h,
            period=self.params.h1_boll_period,
            devfactor=self.params.h1_boll_dev,
        )
        self.h1_atr = bt.indicators.ATR(self.data_1h, period=self.params.atr_period)
        self.h1_volume_ma = bt.indicators.SMA(self.data_1h.volume, period=self.params.volume_ma_period)

        self.weekly_min_bars = max(self.params.weekly_ema_slow, self.params.dmi_period * 2)
        self.daily_min_bars = max(
            self.params.daily_ema_slow,
            self.params.daily_boll_period,
            self.params.dmi_period * 2,
        )
        self.h4_min_bars = max(
            self.params.h4_donchian_period + 1,
            self.params.h4_boll_period,
            self.params.h4_ema_period,
            self.params.volume_ma_period,
            self.params.atr_period + self.params.atr_ma_period,
        )
        self.h1_min_bars = max(
            self.params.h1_donchian_period + 1,
            self.params.h1_boll_period,
            self.params.volume_ma_period,
            self.params.atr_period,
        )

    def log(self, txt, dt=None, force=False):
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_1h.datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    @staticmethod
    def candle_stats(data):
        high = data.high[0]
        low = data.low[0]
        open_price = data.open[0]
        close = data.close[0]
        candle_range = max(high - low, 1e-8)
        body_ratio = abs(close - open_price) / candle_range
        bull_close_strength = (close - low) / candle_range
        bear_close_strength = (high - close) / candle_range
        return {
            'range': candle_range,
            'body_ratio': body_ratio,
            'bull_close_strength': bull_close_strength,
            'bear_close_strength': bear_close_strength,
            'is_bullish': close > open_price,
            'is_bearish': close < open_price,
        }

    def get_trade_position(self):
        return self.getposition(self.data_1h)

    def reset_trade_state(self):
        self.entry_price = None
        self.entry_time = None
        self.entry_side = None
        self.entry_exec_price = None
        self.entry_reason = None
        self.pending_exit_reason = None
        self.entry_stop_distance = None
        self.stop_loss = None
        self.take_profit = None
        self.entry_context = None
        self.highest_since_entry = None
        self.lowest_since_entry = None

    @staticmethod
    def format_price(value):
        return f'{value:.2f}' if value is not None else '动态跟踪'

    @staticmethod
    def format_dt(value):
        return value.strftime('%Y-%m-%d %H:%M:%S') if value is not None else '-'

    def get_entry_risk(self):
        return max(self.entry_stop_distance or self.get_stop_distance(), 1e-8)

    def update_trade_extremes(self):
        if self.entry_price is None:
            return
        self.highest_since_entry = max(self.highest_since_entry or self.entry_price, self.data_1h.high[0])
        self.lowest_since_entry = min(self.lowest_since_entry or self.entry_price, self.data_1h.low[0])

    def get_trend_profit_rr(self, direction, current_price):
        entry_risk = self.get_entry_risk()
        if direction == 'long':
            return (current_price - self.entry_price) / entry_risk
        return (self.entry_price - current_price) / entry_risk

    def update_trend_stop(self, direction, current_price):
        if self.entry_price is None:
            return

        self.update_trade_extremes()
        entry_risk = self.get_entry_risk()
        profit_rr = self.get_trend_profit_rr(direction, current_price)

        if direction == 'long':
            candidate_stop = self.stop_loss if self.stop_loss is not None else self.entry_price - entry_risk
            if profit_rr >= self.params.trend_breakeven_rr:
                candidate_stop = max(candidate_stop, self.entry_price)
            if profit_rr >= self.params.trend_trailing_activation_rr:
                trailing_stop = self.highest_since_entry - self.h1_atr[0] * self.params.trend_trailing_atr_multiplier
                candidate_stop = max(candidate_stop, self.entry_price + entry_risk, trailing_stop)
            self.stop_loss = candidate_stop
            return

        candidate_stop = self.stop_loss if self.stop_loss is not None else self.entry_price + entry_risk
        if profit_rr >= self.params.trend_breakeven_rr:
            candidate_stop = min(candidate_stop, self.entry_price)
        if profit_rr >= self.params.trend_trailing_activation_rr:
            trailing_stop = self.lowest_since_entry + self.h1_atr[0] * self.params.trend_trailing_atr_multiplier
            candidate_stop = min(candidate_stop, self.entry_price - entry_risk, trailing_stop)
        self.stop_loss = candidate_stop

    def trend_ema_exit_confirmed(self, direction):
        if len(self.data_4h) < 2:
            return False

        buffer = self.params.trend_ema_exit_buffer
        if direction == 'long':
            return (
                self.data_4h.close[0] < self.h4_ema21[0] * (1 - buffer)
                and self.data_4h.close[-1] < self.h4_ema21[-1] * (1 - buffer)
            )

        return (
            self.data_4h.close[0] > self.h4_ema21[0] * (1 + buffer)
            and self.data_4h.close[-1] > self.h4_ema21[-1] * (1 + buffer)
        )

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            executed_dt = bt.num2date(order.executed.dt) if order.executed.dt else self.data_1h.datetime.datetime(0)
            executed_value = order.executed.price * abs(order.executed.size)
            fee = executed_value * self.params.trading_fee
            self.total_fees += fee

            position = self.get_trade_position()
            if position.size == 0:
                self.current_trade_fees += fee
                exit_reason = self.pending_exit_reason or '信号平仓'
                self.last_closed_trade = {
                    'direction': self.entry_side,
                    'entry_time': self.entry_time,
                    'entry_price': self.entry_exec_price,
                    'entry_reason': self.entry_reason,
                    'exit_time': executed_dt,
                    'exit_price': order.executed.price,
                    'exit_reason': exit_reason,
                    'size': abs(order.executed.size),
                }
                action = '卖出' if order.issell() else '买入'
                self.log(
                    f'{action}成交 | 时间: {self.format_dt(executed_dt)} | 价格: {order.executed.price:.2f} | '
                    f'数量: {abs(order.executed.size):.4f} | 手续费: {fee:.2f} | 平仓原因: {exit_reason} | '
                    f'累计费用: {self.total_fees:.2f}',
                    force=True,
                )
                self.log(f'成交: {action}平仓 | 原因: {exit_reason}', force=True)
                self.reset_trade_state()
            elif position.size > 0:
                actual_price = order.executed.price * (1 + self.params.slippage)
                signal = self.pending_entry_signal or {}
                self.current_trade_fees = fee
                self.entry_time = executed_dt
                self.entry_side = 'long'
                self.entry_exec_price = order.executed.price
                self.entry_reason = signal.get('confirm_reason') or f'{signal.get("strategy")} / {signal.get("trigger")}'
                self.entry_price = actual_price
                self.entry_stop_distance = self.get_stop_distance()
                self.stop_loss = self.entry_price - self.entry_stop_distance
                self.highest_since_entry = self.entry_price
                self.lowest_since_entry = self.entry_price
                if signal.get('strategy') == 'mean_reversion':
                    self.take_profit = self.h4_boll.mid[0]
                else:
                    self.take_profit = None
                self.entry_context = signal
                self.log(
                    f'买入成交 | 时间: {self.format_dt(executed_dt)} | 价格: {order.executed.price:.2f} | '
                    f'数量: {abs(order.executed.size):.4f} | 手续费: {fee:.2f} | 开仓原因: {self.entry_reason} | '
                    f'累计费用: {self.total_fees:.2f}',
                    force=True,
                )
                self.log(f'成交: 多头开仓 | 原因: {self.entry_reason}', force=True)
                self.log(
                    f'多头开仓 | 策略: {signal.get("strategy")} | 触发: {signal.get("trigger")} | '
                    f'价格: {self.entry_price:.2f} | 止损: {self.stop_loss:.2f} | 止盈: {self.format_price(self.take_profit)}',
                    force=True,
                )
            else:
                actual_price = order.executed.price * (1 - self.params.slippage)
                signal = self.pending_entry_signal or {}
                self.current_trade_fees = fee
                self.entry_time = executed_dt
                self.entry_side = 'short'
                self.entry_exec_price = order.executed.price
                self.entry_reason = signal.get('confirm_reason') or f'{signal.get("strategy")} / {signal.get("trigger")}'
                self.entry_price = actual_price
                self.entry_stop_distance = self.get_stop_distance()
                self.stop_loss = self.entry_price + self.entry_stop_distance
                self.highest_since_entry = self.entry_price
                self.lowest_since_entry = self.entry_price
                if signal.get('strategy') == 'mean_reversion':
                    self.take_profit = self.h4_boll.mid[0]
                else:
                    self.take_profit = None
                self.entry_context = signal
                self.log(f'成交: 空头开仓 | 原因: {self.entry_reason}', force=True)
                self.log(
                    f'空头开仓 | 策略: {signal.get("strategy")} | 触发: {signal.get("trigger")} | '
                    f'价格: {self.entry_price:.2f} | 止损: {self.stop_loss:.2f} | 止盈: {self.format_price(self.take_profit)}',
                    force=True,
                )
                self.log(
                    f'卖出成交 | 时间: {self.format_dt(executed_dt)} | 价格: {order.executed.price:.2f} | '
                    f'数量: {abs(order.executed.size):.4f} | 手续费: {fee:.2f} | 开仓原因: {self.entry_reason} | '
                    f'累计费用: {self.total_fees:.2f}',
                    force=True,
                )

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/被拒绝', force=True)
            self.log('没有成交: 订单被取消/保证金不足/被拒绝', force=True)

        self.pending_entry_signal = None
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_count += 1
            closed_trade = self.last_closed_trade or {}
            direction = closed_trade.get('direction') or ('long' if getattr(trade, 'long', True) else 'short')
            entry_time = closed_trade.get('entry_time')
            entry_price = closed_trade.get('entry_price')
            entry_reason = closed_trade.get('entry_reason') or '-'
            exit_time = closed_trade.get('exit_time')
            exit_price = closed_trade.get('exit_price')
            exit_reason = closed_trade.get('exit_reason') or '-'
            size = closed_trade.get('size') or 0
            trade_fee = self.current_trade_fees
            net_profit = trade.pnl - trade_fee
            entry_value = abs(entry_price * size) if entry_price is not None else 0
            return_pct = (net_profit / entry_value * 100) if entry_value else 0

            if direction == 'short':
                profit_loss_str = f'盈利: {net_profit:.2f}' if net_profit >= 0 else f'亏损: {abs(net_profit):.2f}'
                summary = (
                    f'第{self.trade_count}笔交易完成（空头） | 卖出时间: {self.format_dt(entry_time)} | '
                    f'卖出价: {self.format_price(entry_price)} | 买入时间: {self.format_dt(exit_time)} | '
                    f'买入价: {self.format_price(exit_price)} | {profit_loss_str} | 收益率: {return_pct:.2f}% | '
                    f'开仓原因: {entry_reason} | 平仓原因: {exit_reason}'
                )
            else:
                profit_loss_str = f'盈利: {net_profit:.2f}' if net_profit >= 0 else f'亏损: {abs(net_profit):.2f}'
                summary = (
                    f'第{self.trade_count}笔交易完成（多头） | 买入时间: {self.format_dt(entry_time)} | '
                    f'买入价: {self.format_price(entry_price)} | 卖出时间: {self.format_dt(exit_time)} | '
                    f'卖出价: {self.format_price(exit_price)} | {profit_loss_str} | 收益率: {return_pct:.2f}% | '
                    f'开仓原因: {entry_reason} | 平仓原因: {exit_reason}'
                )

            self.log(summary, force=True)
            self.log(
                f'交易明细 | 毛利润: {trade.pnl:.2f} | 交易费用: {trade_fee:.2f} | 净利润: {net_profit:.2f}',
                force=True,
            )
            self.current_trade_fees = 0.0
            self.last_closed_trade = None

    def is_ready(self):
        return (
            len(self.data_weekly) >= self.weekly_min_bars
            and len(self.data_daily) >= self.daily_min_bars
            and len(self.data_4h) >= self.h4_min_bars
            and len(self.data_1h) >= self.h1_min_bars
        )

    def get_weekly_context(self):
        adx = self.weekly_dmi.adx[0]
        if self.weekly_ema_fast[0] > self.weekly_ema_slow[0]:
            trend = 'bull'
        elif self.weekly_ema_fast[0] < self.weekly_ema_slow[0]:
            trend = 'bear'
        else:
            trend = 'neutral'

        if adx > self.params.weekly_adx_trend_threshold:
            strength = 'strong'
        elif adx < self.params.weekly_adx_weak_threshold:
            strength = 'weakening'
        else:
            strength = 'normal'

        return {
            'trend': trend,
            'strength': strength,
            'adx': adx,
        }

    def get_daily_market_state(self, weekly_context):
        adx = self.daily_dmi.adx[0]
        boll_width = self.daily_boll_width[0]
        bullish = self.daily_ema_fast[0] > self.daily_ema_slow[0]
        bearish = self.daily_ema_fast[0] < self.daily_ema_slow[0]

        if boll_width < self.params.daily_boll_compression_threshold:
            state = 'breakout_setup'
        elif adx < self.params.daily_adx_sideways_threshold:
            state = 'sideways'
        elif bullish and adx > self.params.daily_adx_trend_threshold:
            state = 'bullish_trend'
        elif bearish and adx > self.params.daily_adx_trend_threshold:
            state = 'bearish_trend'
        elif bullish and boll_width > self.params.daily_boll_expansion_threshold:
            state = 'bullish_trend'
        elif bearish and boll_width > self.params.daily_boll_expansion_threshold:
            state = 'bearish_trend'
        elif weekly_context['trend'] == 'bull' and bullish:
            state = 'bullish_trend'
        elif weekly_context['trend'] == 'bear' and bearish:
            state = 'bearish_trend'
        else:
            state = 'transition'

        return {
            'state': state,
            'adx': adx,
            'boll_width': boll_width,
            'bullish': bullish,
            'bearish': bearish,
        }

    def log_context_change(self, weekly_context, market_state):
        macro_snapshot = (weekly_context['trend'], weekly_context['strength'])
        market_snapshot = market_state['state']

        if macro_snapshot != self.last_macro_snapshot:
            self.last_macro_snapshot = macro_snapshot
            self.log(
                f'周线趋势切换 | 趋势: {weekly_context["trend"]} | 强度: {weekly_context["strength"]} | '
                f'ADX: {weekly_context["adx"]:.2f}',
                force=True,
            )

        if market_snapshot != self.last_market_snapshot:
            self.last_market_snapshot = market_snapshot
            self.log(
                f'日线市场状态切换 | 状态: {market_state["state"]} | ADX: {market_state["adx"]:.2f} | '
                f'BollWidth: {market_state["boll_width"]:.4f}',
                force=True,
            )

    def h4_volume_ok(self, ratio_threshold=None):
        ratio_threshold = ratio_threshold if ratio_threshold is not None else self.params.h4_volume_ratio_threshold
        return self.data_4h.volume[0] >= self.h4_volume_ma[0] * ratio_threshold

    def h4_atr_ok(self):
        return self.h4_atr[0] > self.h4_atr_ma[0]

    def h1_volume_ok(self, ratio_threshold=None):
        ratio_threshold = ratio_threshold if ratio_threshold is not None else self.params.h1_volume_ratio_threshold
        return self.data_1h.volume[0] >= self.h1_volume_ma[0] * ratio_threshold

    def valid_h4_breakout(self, direction, breakout_level):
        stats = self.candle_stats(self.data_4h)
        if direction == 'long':
            return (
                self.data_4h.close[0] > breakout_level * (1 + self.params.h4_breakout_buffer)
                and stats['body_ratio'] >= self.params.h4_breakout_body_ratio
                and stats['bull_close_strength'] >= self.params.h4_breakout_close_strength
                and stats['is_bullish']
                and self.h4_volume_ok()
                and self.h4_atr_ok()
            )

        return (
            self.data_4h.close[0] < breakout_level * (1 - self.params.h4_breakout_buffer)
            and stats['body_ratio'] >= self.params.h4_breakout_body_ratio
            and stats['bear_close_strength'] >= self.params.h4_breakout_close_strength
            and stats['is_bearish']
            and self.h4_volume_ok()
            and self.h4_atr_ok()
        )

    def valid_h4_pullback(self, direction):
        stats = self.candle_stats(self.data_4h)
        if direction == 'long':
            return (
                self.data_4h.low[0] <= self.h4_ema21[0]
                and self.data_4h.close[0] > self.h4_ema21[0]
                and stats['bull_close_strength'] >= self.params.h4_pullback_close_strength
                and stats['is_bullish']
                and self.data_4h.volume[0] >= self.h4_volume_ma[0] * self.params.h4_pullback_volume_ratio
                and self.h4_atr_ok()
            )

        return (
            self.data_4h.high[0] >= self.h4_ema21[0]
            and self.data_4h.close[0] < self.h4_ema21[0]
            and stats['bear_close_strength'] >= self.params.h4_pullback_close_strength
            and stats['is_bearish']
            and self.data_4h.volume[0] >= self.h4_volume_ma[0] * self.params.h4_pullback_volume_ratio
            and self.h4_atr_ok()
        )

    def valid_h4_mean_reversion(self, direction):
        stats = self.candle_stats(self.data_4h)
        if direction == 'long':
            return (
                self.data_4h.close[-1] <= self.h4_boll.bot[-1]
                and self.data_4h.close[0] > self.h4_boll.bot[0]
                and stats['bull_close_strength'] >= self.params.h4_pullback_close_strength
                and stats['is_bullish']
            )

        return (
            self.data_4h.close[-1] >= self.h4_boll.top[-1]
            and self.data_4h.close[0] < self.h4_boll.top[0]
            and stats['bear_close_strength'] >= self.params.h4_pullback_close_strength
            and stats['is_bearish']
        )

    def generate_h4_signal(self, weekly_context, market_state):
        state = market_state['state']
        signal = None
        breakout_high = self.h4_donchian_high[-1]
        breakout_low = self.h4_donchian_low[-1]

        if state == 'bullish_trend' and weekly_context['trend'] == 'bull' and weekly_context['strength'] != 'weakening':
            if self.valid_h4_breakout('long', breakout_high):
                signal = {
                    'direction': 'long',
                    'strategy': 'trend_follow',
                    'trigger': 'breakout',
                    'breakout_level': breakout_high,
                }
            elif self.valid_h4_pullback('long'):
                signal = {
                    'direction': 'long',
                    'strategy': 'trend_follow',
                    'trigger': 'pullback',
                    'reference_level': self.h4_ema21[0],
                }
        elif state == 'bearish_trend' and weekly_context['trend'] == 'bear' and weekly_context['strength'] != 'weakening':
            if self.valid_h4_breakout('short', breakout_low):
                signal = {
                    'direction': 'short',
                    'strategy': 'trend_follow',
                    'trigger': 'breakout',
                    'breakout_level': breakout_low,
                }
            elif self.valid_h4_pullback('short'):
                signal = {
                    'direction': 'short',
                    'strategy': 'trend_follow',
                    'trigger': 'pullback',
                    'reference_level': self.h4_ema21[0],
                }
        elif state == 'sideways':
            if self.valid_h4_mean_reversion('long'):
                signal = {
                    'direction': 'long',
                    'strategy': 'mean_reversion',
                    'trigger': 'pullback',
                    'reference_level': self.h4_boll.bot[0],
                }
            elif self.valid_h4_mean_reversion('short'):
                signal = {
                    'direction': 'short',
                    'strategy': 'mean_reversion',
                    'trigger': 'pullback',
                    'reference_level': self.h4_boll.top[0],
                }
        elif state == 'breakout_setup' and weekly_context['strength'] != 'weakening':
            if weekly_context['trend'] == 'bull' and market_state['bullish'] and self.valid_h4_breakout('long', breakout_high):
                signal = {
                    'direction': 'long',
                    'strategy': 'breakout',
                    'trigger': 'breakout',
                    'breakout_level': breakout_high,
                }
            elif weekly_context['trend'] == 'bear' and market_state['bearish'] and self.valid_h4_breakout('short', breakout_low):
                signal = {
                    'direction': 'short',
                    'strategy': 'breakout',
                    'trigger': 'breakout',
                    'breakout_level': breakout_low,
                }

        if signal is None:
            return None

        signal.update({
            'state': state,
            'created_4h_time': self.data_4h.datetime.datetime(0),
            'created_h1_len': len(self.data_1h),
            'expiry_bar': len(self.data_1h) + self.params.signal_valid_bars,
        })
        self.log(
            f'4H 信号生成 | 状态: {state} | 策略: {signal["strategy"]} | 方向: {signal["direction"]} | 触发: {signal["trigger"]}',
            force=True,
        )
        # 添加指标数值显示
        self.log(
            f'4H 指标数值 | 价格: {self.data_4h.close[0]:.2f} | '
            f'Donchian高: {self.h4_donchian_high[-1]:.2f} | Donchian低: {self.h4_donchian_low[-1]:.2f} | '
            f'布林上轨: {self.h4_boll.top[0]:.2f} | 布林中轨: {self.h4_boll.mid[0]:.2f} | 布林下轨: {self.h4_boll.bot[0]:.2f} | '
            f'EMA21: {self.h4_ema21[0]:.2f} | ATR: {self.h4_atr[0]:.2f} | 成交量: {self.data_4h.volume[0]:.2f} | 成交量MA: {self.h4_volume_ma[0]:.2f}',
            force=True,
        )
        return signal

    def signal_expired(self):
        return self.pending_signal and len(self.data_1h) > self.pending_signal['expiry_bar']

    def breakout_signal_invalidated(self, signal):
        breakout_level = signal.get('breakout_level')
        if breakout_level is None:
            return False, ''

        if signal['direction'] == 'long':
            if self.data_1h.close[0] < breakout_level * (1 - self.params.h1_retest_hold_buffer):
                return True, '1H 收盘跌回突破位下方，撤销多头突破信号'
            return False, ''

        if self.data_1h.close[0] > breakout_level * (1 + self.params.h1_retest_hold_buffer):
            return True, '1H 收盘重新站回突破位上方，撤销空头突破信号'
        return False, ''

    def confirm_h1_breakout_retest(self, signal):
        breakout_level = signal.get('breakout_level')
        created_h1_len = signal.get('created_h1_len', 0)
        stats = self.candle_stats(self.data_1h)
        if breakout_level is None or len(self.data_1h) <= created_h1_len:
            return False, ''

        if signal['direction'] == 'long':
            confirmed = (
                self.data_1h.low[0] <= breakout_level * (1 + self.params.h1_retest_touch_buffer)
                and self.data_1h.low[0] >= breakout_level * (1 - self.params.h1_retest_hold_buffer)
                and self.data_1h.close[0] >= breakout_level * (1 + self.params.h1_retest_confirm_buffer)
                and stats['body_ratio'] >= self.params.h1_retest_body_ratio
                and stats['bull_close_strength'] >= self.params.h1_retest_close_strength
                and stats['is_bullish']
                and self.h1_volume_ok(self.params.h1_retest_volume_ratio_threshold)
            )
            # 添加指标数值和判断逻辑日志
            self.log(
                f'1H 回踩突破判断 | 方向: long | 价格: {self.data_1h.close[0]:.2f} | 最低价: {self.data_1h.low[0]:.2f} | '
                f'回踩区间: [{breakout_level * (1 - self.params.h1_retest_hold_buffer):.2f} - {breakout_level * (1 + self.params.h1_retest_touch_buffer):.2f}] | '
                f'确认要求: >={breakout_level * (1 + self.params.h1_retest_confirm_buffer):.2f} | '
                f'实体比例: {stats["body_ratio"]:.3f} (要求>={self.params.h1_retest_body_ratio:.3f}) | '
                f'多头收盘强度: {stats["bull_close_strength"]:.3f} (要求>={self.params.h1_retest_close_strength:.3f}) | '
                f'是否看涨: {stats["is_bullish"]} | 成交量OK: {self.h1_volume_ok(self.params.h1_retest_volume_ratio_threshold)}',
                force=True,
            )
            return confirmed, '1H 回踩突破位不破，多头二次确认通过'

        confirmed = (
            self.data_1h.high[0] >= breakout_level * (1 - self.params.h1_retest_touch_buffer)
            and self.data_1h.high[0] <= breakout_level * (1 + self.params.h1_retest_hold_buffer)
            and self.data_1h.close[0] <= breakout_level * (1 - self.params.h1_retest_confirm_buffer)
            and stats['body_ratio'] >= self.params.h1_retest_body_ratio
            and stats['bear_close_strength'] >= self.params.h1_retest_close_strength
            and stats['is_bearish']
            and self.h1_volume_ok(self.params.h1_retest_volume_ratio_threshold)
        )
        # 添加指标数值和判断逻辑日志
        self.log(
            f'1H 回踩突破判断 | 方向: short | 价格: {self.data_1h.close[0]:.2f} | 最高价: {self.data_1h.high[0]:.2f} | '
            f'回踩区间: [{breakout_level * (1 - self.params.h1_retest_touch_buffer):.2f} - {breakout_level * (1 + self.params.h1_retest_hold_buffer):.2f}] | '
            f'确认要求: <={breakout_level * (1 - self.params.h1_retest_confirm_buffer):.2f} | '
            f'实体比例: {stats["body_ratio"]:.3f} (要求>={self.params.h1_retest_body_ratio:.3f}) | '
            f'空头收盘强度: {stats["bear_close_strength"]:.3f} (要求>={self.params.h1_retest_close_strength:.3f}) | '
            f'是否看跌: {stats["is_bearish"]} | 成交量OK: {self.h1_volume_ok(self.params.h1_retest_volume_ratio_threshold)}',
            force=True,
        )
        return confirmed, '1H 回踩突破位不破，空头二次确认通过'

    def confirm_h1_breakout(self, signal):
        invalidated, invalid_reason = self.breakout_signal_invalidated(signal)
        if invalidated:
            signal['invalidated'] = True
            return False, invalid_reason

        if self.params.require_breakout_retest:
            return self.confirm_h1_breakout_retest(signal)

        stats = self.candle_stats(self.data_1h)
        breakout_level = signal.get('breakout_level')
        if breakout_level is None:
            return False, ''

        if signal['direction'] == 'long':
            confirmed = (
                self.data_1h.close[0] > max(self.h1_donchian_high[-1], breakout_level) * (1 + self.params.h1_breakout_buffer)
                and stats['body_ratio'] >= self.params.h1_breakout_body_ratio
                and stats['bull_close_strength'] >= self.params.h1_breakout_close_strength
                and stats['is_bullish']
                and self.h1_volume_ok()
            )
            # 添加指标数值和判断逻辑日志
            self.log(
                f'1H 突破判断 | 方向: long | 价格: {self.data_1h.close[0]:.2f} | '
                f'突破要求: >{max(self.h1_donchian_high[-1], breakout_level) * (1 + self.params.h1_breakout_buffer):.2f} | '
                f'实体比例: {stats["body_ratio"]:.3f} (要求>={self.params.h1_breakout_body_ratio:.3f}) | '
                f'多头收盘强度: {stats["bull_close_strength"]:.3f} (要求>={self.params.h1_breakout_close_strength:.3f}) | '
                f'是否看涨: {stats["is_bullish"]} | 成交量OK: {self.h1_volume_ok()}',
                force=True,
            )
            return confirmed, '1H Donchian 放量向上确认'

        confirmed = (
            self.data_1h.close[0] < min(self.h1_donchian_low[-1], breakout_level) * (1 - self.params.h1_breakout_buffer)
            and stats['body_ratio'] >= self.params.h1_breakout_body_ratio
            and stats['bear_close_strength'] >= self.params.h1_breakout_close_strength
            and stats['is_bearish']
            and self.h1_volume_ok()
        )
        # 添加指标数值和判断逻辑日志
        self.log(
            f'1H 突破判断 | 方向: short | 价格: {self.data_1h.close[0]:.2f} | '
            f'突破要求: <{min(self.h1_donchian_low[-1], breakout_level) * (1 - self.params.h1_breakout_buffer):.2f} | '
            f'实体比例: {stats["body_ratio"]:.3f} (要求>={self.params.h1_breakout_body_ratio:.3f}) | '
            f'空头收盘强度: {stats["bear_close_strength"]:.3f} (要求>={self.params.h1_breakout_close_strength:.3f}) | '
            f'是否看跌: {stats["is_bearish"]} | 成交量OK: {self.h1_volume_ok()}',
            force=True,
        )
        return confirmed, '1H Donchian 放量向下确认'

    def confirm_h1_reversal(self, signal):
        stats = self.candle_stats(self.data_1h)
        if signal['direction'] == 'long':
            confirmed = (
                self.data_1h.close[-1] <= self.h1_boll.bot[-1]
                and self.data_1h.close[0] > self.h1_boll.bot[0]
                and stats['bull_close_strength'] >= self.params.h1_reversal_close_strength
                and stats['is_bullish']
            )
            # 添加指标数值和判断逻辑日志
            self.log(
                f'1H 反转判断 | 方向: long | 价格: {self.data_1h.close[0]:.2f} | '
                f'上根K线收盘: {self.data_1h.close[-1]:.2f} (要求<={self.h1_boll.bot[-1]:.2f}) | '
                f'当前布林下轨: {self.h1_boll.bot[0]:.2f} (要求>{self.h1_boll.bot[0]:.2f}) | '
                f'多头收盘强度: {stats["bull_close_strength"]:.3f} (要求>={self.params.h1_reversal_close_strength:.3f}) | '
                f'是否看涨: {stats["is_bullish"]}',
                force=True,
            )
            return confirmed, '1H 下轨反弹确认'

        confirmed = (
            self.data_1h.close[-1] >= self.h1_boll.top[-1]
            and self.data_1h.close[0] < self.h1_boll.top[0]
            and stats['bear_close_strength'] >= self.params.h1_reversal_close_strength
            and stats['is_bearish']
        )
        # 添加指标数值和判断逻辑日志
        self.log(
            f'1H 反转判断 | 方向: short | 价格: {self.data_1h.close[0]:.2f} | '
            f'上根K线收盘: {self.data_1h.close[-1]:.2f} (要求>={self.h1_boll.top[-1]:.2f}) | '
            f'当前布林上轨: {self.h1_boll.top[0]:.2f} (要求<{self.h1_boll.top[0]:.2f}) | '
            f'空头收盘强度: {stats["bear_close_strength"]:.3f} (要求>={self.params.h1_reversal_close_strength:.3f}) | '
            f'是否看跌: {stats["is_bearish"]}',
            force=True,
        )
        return confirmed, '1H 上轨回落确认'

    def confirm_h1_entry(self, signal):
        if signal['trigger'] == 'breakout':
            return self.confirm_h1_breakout(signal)
        return self.confirm_h1_reversal(signal)

    def get_stop_distance(self):
        return max(self.h1_atr[0] * self.params.h1_stop_atr_multiplier, 1e-8)

    def calculate_position_size(self, direction):
        entry_price = self.data_1h.close[0]
        stop_distance = self.get_stop_distance()
        risk_amount = self.broker.getvalue() * self.params.risk_per_trade
        size = risk_amount / stop_distance

        # 考虑交易费用和滑点
        fee_adjustment = 1.0 / (1.0 - self.params.trading_fee - self.params.slippage)
        size *= fee_adjustment

        if direction == 'long':
            max_size = max((self.broker.getcash() * 0.95) / max(entry_price, 1e-8), 0)
        else:
            max_size = max((self.broker.getvalue() * 0.95) / max(entry_price, 1e-8), 0)

        return max(min(size, max_size), 0)

    def place_entry_order(self, signal):
        size = self.calculate_position_size(signal['direction'])
        if size <= 0:
            self.log('仓位计算结果为0，跳过本次信号', force=True)
            self.log('没有成交: 仓位计算结果为0', force=True)
            self.pending_signal = None
            return

        self.pending_exit_reason = None
        self.pending_entry_signal = signal.copy()
        self.log(
            f'1H 入场确认 | 方向: {signal["direction"]} | 策略: {signal["strategy"]} | 数量: {size:.4f} | '
            f'开仓原因: {signal.get("confirm_reason", "-")}',
            force=True,
        )
        if signal['direction'] == 'long':
            self.order = self.buy(data=self.data_1h, size=size)
            self.log('已提交买入订单', force=True)
        else:
            self.order = self.sell(data=self.data_1h, size=size)
            self.log('已提交卖出订单', force=True)

    def submit_close_order(self, reason):
        self.pending_exit_reason = reason
        self.order = self.close(data=self.data_1h)
        self.log(f'已提交平仓订单 | 原因: {reason}', force=True)

    def manage_position(self, market_state):
        position = self.get_trade_position()
        if not position or not position.size or self.order:
            return

        current_price = self.data_1h.close[0]
        stop_distance = self.get_stop_distance()
        strategy = (self.entry_context or {}).get('strategy')
        is_trend_trade = strategy != 'mean_reversion'

        if position.size > 0:
            if is_trend_trade:
                self.update_trend_stop('long', current_price)
            else:
                trailing_stop = current_price - stop_distance
                if self.stop_loss is None or trailing_stop > self.stop_loss:
                    self.stop_loss = trailing_stop

            if self.stop_loss is not None and current_price <= self.stop_loss:
                reason = f'触发多头止损 | 当前价: {current_price:.2f} | 止损价: {self.stop_loss:.2f}'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif strategy == 'mean_reversion' and self.take_profit is not None and current_price >= self.take_profit:
                reason = f'震荡多头止盈 | 当前价: {current_price:.2f} | 目标价: {self.take_profit:.2f}'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif is_trend_trade and market_state['state'] == 'bearish_trend':
                reason = '日线切换为空头结构，平掉多头仓位'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif is_trend_trade and self.trend_ema_exit_confirmed('long'):
                reason = '4H 连续跌破 EMA21 缓冲区，趋势多头止盈/止退'
                self.log(reason, force=True)
                self.submit_close_order(reason)
        else:
            if is_trend_trade:
                self.update_trend_stop('short', current_price)
            else:
                trailing_stop = current_price + stop_distance
                if self.stop_loss is None or trailing_stop < self.stop_loss:
                    self.stop_loss = trailing_stop

            if self.stop_loss is not None and current_price >= self.stop_loss:
                reason = f'触发空头止损 | 当前价: {current_price:.2f} | 止损价: {self.stop_loss:.2f}'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif strategy == 'mean_reversion' and self.take_profit is not None and current_price <= self.take_profit:
                reason = f'震荡空头止盈 | 当前价: {current_price:.2f} | 目标价: {self.take_profit:.2f}'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif is_trend_trade and market_state['state'] == 'bullish_trend':
                reason = '日线切换为多头结构，平掉空头仓位'
                self.log(reason, force=True)
                self.submit_close_order(reason)
            elif is_trend_trade and self.trend_ema_exit_confirmed('short'):
                reason = '4H 连续站上 EMA21 缓冲区，趋势空头止盈/止退'
                self.log(reason, force=True)
                self.submit_close_order(reason)

    def next(self):
        if not self.is_ready():
            return

        weekly_context = self.get_weekly_context()
        market_state = self.get_daily_market_state(weekly_context)
        self.log_context_change(weekly_context, market_state)
        
        # 打印关键指标值
        self.log('\n=== 指标数值 ===')
        self.log(f'周线日期: {self.data_weekly.datetime.datetime(0)} | 周线EMA21: {self.weekly_ema_fast[0]:.2f}，周线EMA55: {self.weekly_ema_slow[0]:.2f}，周线ADX: {self.weekly_dmi.adx[0]:.2f}')
        self.log(f'日线日期: {self.data_daily.datetime.datetime(0)} | 日线EMA21: {self.daily_ema_fast[0]:.2f}，日线EMA55: {self.daily_ema_slow[0]:.2f}，日线ADX: {self.daily_dmi.adx[0]:.2f}')
        self.log(f'4H 日期: {self.data_4h.datetime.datetime(0)} | 4H ATR: {self.h4_atr[0]:.2f}，4H EMA21: {self.h4_ema21[0]:.2f}')
        self.log(f'1H 日期: {self.data_1h.datetime.datetime(0)} 1H price: {self.data_1h.close[0]:.2f} | 1H ATR: {self.h1_atr[0]:.2f}')

        position = self.get_trade_position()

        if position and position.size:
            self.manage_position(market_state)
            if self.order:
                return

        current_4h_time = self.data_4h.datetime.datetime(0)
        if (not position or not position.size) and self.last_4h_bar_time != current_4h_time:
            self.last_4h_bar_time = current_4h_time
            new_signal = self.generate_h4_signal(weekly_context, market_state)
            if new_signal is not None:
                self.pending_signal = new_signal
            else:
                self.log('没有信号生成: 市场条件不满足', force=True)

        if not self.pending_signal or (position and position.size) or self.order:
            return

        if self.pending_signal['state'] != market_state['state']:
            self.log('市场状态发生变化，撤销待执行信号', force=True)
            self.log('没有成交: 市场状态发生变化', force=True)
            self.pending_signal = None
            return

        if self.signal_expired():
            self.log('1H 未在有效期内完成确认，信号失效', force=True)
            self.log('没有成交: 信号过期', force=True)
            self.pending_signal = None
            return

        confirmed, reason = self.confirm_h1_entry(self.pending_signal)
        if self.pending_signal and self.pending_signal.get('invalidated'):
            self.log(reason, force=True)
            self.log(f'没有成交: {reason}', force=True)
            self.pending_signal = None
            return

        if not confirmed:
            if reason:
                self.log(f'没有成交: {reason}', force=True)
            else:
                self.log('没有成交: 信号未确认', force=True)
            return

        self.pending_signal['confirm_reason'] = reason
        self.log(reason, force=True)
        self.place_entry_order(self.pending_signal)
        if self.order:
            self.pending_signal = None
