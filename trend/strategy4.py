import backtrader as bt


class Strategy4(bt.Strategy):
    """
    策略4：1H趋势 + 15M突破入场 + ATR风控 + RSI动量确认 (优化版v4 - 参数自动切换)
    
    优化内容：
        1. 增加参数自动切换机制 - 根据ADX动态切换A/B/C三套参数
        2. 增加EMA位置确认 - 价格需要在EMA之上做多，之下做空
        3. 增加RSI趋势确认 - 不仅看当前值，还要看趋势方向
        4. 增加1H和15M趋势共振确认 - 两个时间框架方向一致
        5. 优化止损逻辑 - 增加初始保护止损
    
    参数切换逻辑：
        ADX > 25: 组合B（趋势强化）
        ADX < 18: 组合C（防守型）
        其他: 组合A（平衡型）
    
    核心逻辑：
        1H 判断趋势方向
        15M 捕捉突破入场
        ATR 控制风险
        RSI 确认动量
        仓位按风险动态分配
    
    时间周期分工：
        趋势判断: 1H
        入场执行: 15M
        风控计算: 15M
    """

    # 三套风控参数组合定义（指标参数固定，只切换风控）
    RISK_PARAM_SETS = {
        'A': {  # 平衡型 - 盈亏比2:1
            'stop_loss_atr_multiplier': 1.5,
            'take_profit_1_atr': 1.5,
            'take_profit_2_atr': 3.0,
            'trailing_stop_atr': 1.5,
            'atr_price_ratio_min': 0.003,
        },
        'B': {  # 趋势强化 - 盈亏比2.5:1
            'stop_loss_atr_multiplier': 1.8,
            'take_profit_1_atr': 2.0,
            'take_profit_2_atr': 4.5,
            'trailing_stop_atr': 2.0,
            'atr_price_ratio_min': 0.004,
        },
        'C': {  # 防守型 - 盈亏比1.5:1
            'stop_loss_atr_multiplier': 1.0,
            'take_profit_1_atr': 1.0,
            'take_profit_2_atr': 1.5,
            'trailing_stop_atr': 1.0,
            'atr_price_ratio_min': 0.0025,
        },
    }

    params = (
        # 日志控制
        ('printlog', False),
        ('eventlog', True),

        # 1H趋势指标参数（默认使用组合A）
        ('h1_ema_fast', 21),
        ('h1_ema_slow', 55),
        ('h1_adx_period', 14),
        ('h1_adx_threshold', 25),

        # 15M入场指标参数
        ('m15_donchian_period', 20),
        ('m15_rsi_period', 14),
        ('m15_atr_period', 14),
        ('m15_volume_ma_period', 20),
        ('m15_ema_period', 21),

        # 市场过滤参数
        ('atr_price_ratio_min', 0.002),
        ('volume_ratio_threshold', 1.2),
        ('candle_body_ratio_min', 0.4),

        # 突破参数
        ('breakout_atr_offset', 0.1),

        # RSI动量确认参数
        ('rsi_long_min', 55),
        ('rsi_short_max', 45),

        # 风控参数
        ('stop_loss_atr_multiplier', 2.5),
        ('take_profit_1_atr', 2.0),
        ('take_profit_2_atr', 4.0),
        ('trailing_stop_atr', 2.5),
        ('ema_exit_buffer_atr', 0.5),
        ('ema_exit_confirm_bars', 3),
        ('min_holding_bars', 5),

        # 新增过滤参数
        ('min_trend_bars', 3),
        ('rsi_overbought', 70),
        ('rsi_oversold', 30),
        ('breakout_confirm_bars', 2),
        ('volume_confirm_bars', 2),

        # 仓位管理参数
        ('risk_per_trade', 0.02),
        ('max_position_size', 0.55),
        ('leverage', 7),
        ('max_leverage_ratio', 0.92),
        ('max_drawdown_pct', 0.15),
        ('drawdown_position_scale', 0.5),

        # 风险控制
        ('max_consecutive_losses', 5),
        ('max_daily_loss_pct', 0.08),

        # 参数切换阈值
        ('adx_high_threshold', 25),
        ('adx_low_threshold', 18),
        ('min_bars_between_switch', 50),
    )

    def __init__(self):
        # 多时间周期数据引用
        self.data_1h = self.datas[0]
        self.data_15m = self.datas[1]

        # 当前使用的参数组合（默认A）
        self.current_param_set = 'A'
        self.active_risk_params = self.RISK_PARAM_SETS[self.current_param_set].copy()
        self.last_switch_bar = 0
        self.bar_count = 0

        # 1H趋势指标
        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_fast)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_slow)
        self.h1_adx = bt.indicators.DMI(
            self.data_1h,
            period=self.params.h1_adx_period
        ).adx

        # 15M入场指标
        self.m15_donchian_high = bt.indicators.Highest(
            self.data_15m.high,
            period=self.params.m15_donchian_period
        )
        self.m15_donchian_low = bt.indicators.Lowest(
            self.data_15m.low,
            period=self.params.m15_donchian_period
        )
        self.m15_rsi = bt.indicators.RSI(
            self.data_15m.close,
            period=self.params.m15_rsi_period
        )
        self.m15_atr = bt.indicators.ATR(
            self.data_15m,
            period=self.params.m15_atr_period
        )
        self.m15_volume_ma = bt.indicators.SMA(
            self.data_15m.volume,
            period=self.params.m15_volume_ma_period
        )
        self.m15_ema21 = bt.indicators.EMA(
            self.data_15m.close,
            period=self.params.m15_ema_period
        )

        # 订单和仓位状态
        self.order = None
        self.current_position = None
        self.entry_price = None
        self.entry_direction = None
        self.stop_loss = None
        self.take_profit_1 = None
        self.take_profit_2 = None
        self.stop_moved_to_cost = False
        self.partial_take_profit_done = False

        # 交易统计
        self.trade_count = 0
        self.win_count = 0
        self.consecutive_losses = 0
        self.daily_profit = 0
        self.last_trade_date = None

        # 持仓管理
        self.bars_since_entry = 0
        self.ema_break_count = 0
        self.max_portfolio_value = self.broker.getvalue()
        self.drawdown_scale = 1.0

        # 趋势持续跟踪
        self.trend_bars = 0
        self.last_trend = 'sideways'

        # 突破持续跟踪
        self.breakout_bars = 0
        self.last_breakout_direction = None

        self.log('=== Strategy4 初始化完成 (参数自动切换版) ===', force=True)

    def get_active_params(self):
        """根据ADX值获取当前应使用的参数组合"""
        adx = self.h1_adx[0]
        if adx > self.params.adx_high_threshold:
            return 'B'
        elif adx < self.params.adx_low_threshold:
            return 'C'
        else:
            return 'A'

    def update_params_if_needed(self):
        """检查并更新风控参数组合"""
        self.bar_count += 1

        bars_since_switch = self.bar_count - self.last_switch_bar
        if bars_since_switch < self.params.min_bars_between_switch:
            return

        new_set = self.get_active_params()
        if new_set != self.current_param_set:
            old_set = self.current_param_set
            self.current_param_set = new_set
            self.last_switch_bar = self.bar_count
            params = self.RISK_PARAM_SETS[new_set]
            self.active_risk_params = params.copy()

            self.log(f'风控切换: {old_set} -> {new_set} (ADX: {self.h1_adx[0]:.2f}, SL: {params["stop_loss_atr_multiplier"]}x, TP2: {params["take_profit_2_atr"]}x)', force=True)

    def get_risk_param(self, key):
        """读取当前生效的风控参数（优先使用动态参数集）"""
        return self.active_risk_params.get(key, getattr(self.params, key))

    def log(self, txt, dt=None, force=False):
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_15m.datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def get_trend_direction(self):
        price = self.data_1h.close[0]
        ema21 = self.h1_ema21[0]
        ema55 = self.h1_ema55[0]
        adx = self.h1_adx[0]

        ema21_prev = self.h1_ema21[-1]
        ema21_slope = ema21 - ema21_prev

        if (price > ema21 > ema55
                and ema21_slope > 0
                and adx > self.params.h1_adx_threshold):
            return 'bullish'

        if (price < ema21 < ema55
                and ema21_slope < 0
                and adx > self.params.h1_adx_threshold):
            return 'bearish'

        return 'sideways'

    def check_market_filter(self):
        price = self.data_15m.close[0]
        atr = self.m15_atr[0]
        volume = self.data_15m.volume[0]
        volume_ma = self.m15_volume_ma[0]
        high = self.data_15m.high[0]
        low = self.data_15m.low[0]
        open_price = self.data_15m.open[0]
        close_price = self.data_15m.close[0]

        atr_ratio = atr / price if price > 0 else 0
        volume_ratio = volume / volume_ma if volume_ma > 0 else 0
        candle_range = high - low
        candle_body = abs(close_price - open_price)
        body_ratio = candle_body / candle_range if candle_range > 0 else 0

        volatility_ok = atr_ratio > self.get_risk_param('atr_price_ratio_min')
        volume_ok = volume_ratio > self.params.volume_ratio_threshold
        candle_quality_ok = body_ratio >= self.params.candle_body_ratio_min

        return volatility_ok and volume_ok and candle_quality_ok

    def check_breakout(self):
        close = self.data_15m.close[0]
        atr = self.m15_atr[0]
        offset = atr * self.params.breakout_atr_offset

        recent_high = self.m15_donchian_high[-1]
        recent_low = self.m15_donchian_low[-1]

        bullish_breakout = close > recent_high + offset
        bearish_breakout = close < recent_low - offset

        # 额外确认：突破需要有一定的幅度
        if bullish_breakout:
            breakout_strength = (close - recent_high) / atr if atr > 0 else 0
            bullish_breakout = breakout_strength >= 0.3

        if bearish_breakout:
            breakout_strength = (recent_low - close) / atr if atr > 0 else 0
            bearish_breakout = breakout_strength >= 0.3

        return bullish_breakout, bearish_breakout

    def check_rsi_momentum(self):
        rsi_now = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]

        bullish_rsi = rsi_now >= self.params.rsi_long_min and rsi_now > rsi_prev
        bearish_rsi = rsi_now <= self.params.rsi_short_max and rsi_now < rsi_prev

        return bullish_rsi, bearish_rsi

    def check_ema_position(self):
        price = self.data_15m.close[0]
        ema21 = self.m15_ema21[0]

        price_above_ema = price > ema21
        price_below_ema = price < ema21

        return price_above_ema, price_below_ema

    def check_trend_resonance(self, direction):
        h1_price = self.data_1h.close[0]
        h1_ema21 = self.h1_ema21[0]
        h1_ema55 = self.h1_ema55[0]

        m15_price = self.data_15m.close[0]
        m15_ema21 = self.m15_ema21[0]

        if direction == 'long':
            h1_bullish = h1_price > h1_ema21 > h1_ema55
            m15_bullish = m15_price > m15_ema21
            return h1_bullish and m15_bullish
        elif direction == 'short':
            h1_bearish = h1_price < h1_ema21 < h1_ema55
            m15_bearish = m15_price < m15_ema21
            return h1_bearish and m15_bearish
        return False

    def check_trend_duration(self, trend):
        current_trend = self.get_trend_direction()
        if current_trend == trend:
            if self.last_trend == trend:
                self.trend_bars += 1
            else:
                self.trend_bars = 1
                self.last_trend = trend
            return self.trend_bars >= self.params.min_trend_bars
        else:
            self.trend_bars = 0
            self.last_trend = current_trend
            return False

    def check_rsi_extreme(self, direction):
        rsi_now = self.m15_rsi[0]
        if direction == 'long':
            return rsi_now < self.params.rsi_overbought
        elif direction == 'short':
            return rsi_now > self.params.rsi_oversold
        return False

    def check_breakout_persistence(self, direction, bullish_breakout=None, bearish_breakout=None):
        if bullish_breakout is None or bearish_breakout is None:
            bullish_breakout, bearish_breakout = self.check_breakout()
        current_direction = 'long' if bullish_breakout else ('short' if bearish_breakout else None)

        if current_direction == direction:
            if self.last_breakout_direction == direction:
                self.breakout_bars += 1
            else:
                self.breakout_bars = 1
                self.last_breakout_direction = direction
            return self.breakout_bars >= self.params.breakout_confirm_bars
        else:
            self.breakout_bars = 0
            self.last_breakout_direction = current_direction
            return False

    def check_volume_confirmation(self):
        """成交量连续确认"""
        volume_ok_count = 0
        for i in range(self.params.volume_confirm_bars):
            vol = self.data_15m.volume[-i]
            vol_ma = self.m15_volume_ma[-i]
            if vol > vol_ma * self.params.volume_ratio_threshold:
                volume_ok_count += 1
        return volume_ok_count >= self.params.volume_confirm_bars

    def calculate_position_size(self, direction):
        signal_price = self.data_15m.close[0]
        atr = self.m15_atr[0]
        equity = self.broker.getvalue()
        stop_distance = atr * self.get_risk_param('stop_loss_atr_multiplier')

        risk_amount = equity * self.params.risk_per_trade
        risk_size = risk_amount / stop_distance if stop_distance > 0 else 0

        cash_cap = (equity * self.params.max_position_size) / signal_price if signal_price > 0 else 0
        lev_cap = (equity * self.params.leverage * self.params.max_leverage_ratio) / signal_price if signal_price > 0 else 0

        base_size = min(risk_size, cash_cap, lev_cap) if signal_price > 0 else 0

        current_drawdown = (self.max_portfolio_value - equity) / self.max_portfolio_value if self.max_portfolio_value > 0 else 0
        if current_drawdown >= self.params.max_drawdown_pct:
            self.drawdown_scale = self.params.drawdown_position_scale
        else:
            self.drawdown_scale = 1.0

        final_size = base_size * self.drawdown_scale

        return final_size

    def check_ema_exit(self):
        if self.bars_since_entry < self.params.min_holding_bars:
            return False

        price = self.data_15m.close[0]
        ema21 = self.m15_ema21[0]
        atr = self.m15_atr[0]
        buffer = atr * self.params.ema_exit_buffer_atr

        if self.entry_direction == 'long':
            if price < ema21 - buffer:
                self.ema_break_count += 1
            else:
                self.ema_break_count = 0
        elif self.entry_direction == 'short':
            if price > ema21 + buffer:
                self.ema_break_count += 1
            else:
                self.ema_break_count = 0

        return self.ema_break_count >= self.params.ema_exit_confirm_bars

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            prev_direction = self.entry_direction

            if order.isbuy():
                if prev_direction == 'short':
                    self.log(
                        f'买入平仓(空头) | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    if self.position.size == 0:
                        self.entry_price = None
                        self.entry_direction = None
                        self.stop_loss = None
                        self.take_profit_1 = None
                        self.take_profit_2 = None
                elif prev_direction == 'long':
                    self.log(
                        f'买入平仓(多头部分) | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    if self.position.size == 0:
                        self.entry_price = None
                        self.entry_direction = None
                        self.stop_loss = None
                        self.take_profit_1 = None
                        self.take_profit_2 = None
                else:
                    self.log(
                        f'买入开仓(多头) | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    self.entry_price = order.executed.price
                    self.entry_direction = 'long'
                    self.bars_since_entry = 0
                    self.stop_moved_to_cost = False
                    self.partial_take_profit_done = False
                    self.ema_break_count = 0

                    atr = self.m15_atr[0]
                    self.stop_loss = self.entry_price - atr * self.get_risk_param('stop_loss_atr_multiplier')
                    self.take_profit_1 = self.entry_price + atr * self.get_risk_param('take_profit_1_atr')
                    self.take_profit_2 = self.entry_price + atr * self.get_risk_param('take_profit_2_atr')

                    self.log(f'止损: {self.stop_loss:.2f} | TP1: {self.take_profit_1:.2f} | TP2: {self.take_profit_2:.2f}', force=True)
            else:
                if prev_direction == 'long':
                    self.log(
                        f'卖出平仓(多头) | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    if self.position.size == 0:
                        self.entry_price = None
                        self.entry_direction = None
                        self.stop_loss = None
                        self.take_profit_1 = None
                        self.take_profit_2 = None
                elif prev_direction == 'short':
                    self.log(
                        f'卖出平仓(空头部分) | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    if self.position.size == 0:
                        self.entry_price = None
                        self.entry_direction = None
                        self.stop_loss = None
                        self.take_profit_1 = None
                        self.take_profit_2 = None
                else:
                    self.log(
                        f'卖出开仓(空头) | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f} | 手续费: {order.executed.comm:.4f}',
                        force=True
                    )
                    self.entry_price = order.executed.price
                    self.entry_direction = 'short'
                    self.bars_since_entry = 0
                    self.stop_moved_to_cost = False
                    self.partial_take_profit_done = False
                    self.ema_break_count = 0

                    atr = self.m15_atr[0]
                    self.stop_loss = self.entry_price + atr * self.get_risk_param('stop_loss_atr_multiplier')
                    self.take_profit_1 = self.entry_price - atr * self.get_risk_param('take_profit_1_atr')
                    self.take_profit_2 = self.entry_price - atr * self.get_risk_param('take_profit_2_atr')

                    self.log(f'止损: {self.stop_loss:.2f} | TP1: {self.take_profit_1:.2f} | TP2: {self.take_profit_2:.2f}', force=True)

            self.trade_count += 1
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/被拒绝')

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.win_count += 1 if trade.pnl > 0 else 0
        if trade.pnl <= 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

        current_date = self.data_15m.datetime.date(0)
        if self.last_trade_date != current_date:
            self.daily_profit = 0
            self.last_trade_date = current_date
        self.daily_profit += trade.pnl

        result = '盈利' if trade.pnl > 0 else '亏损'
        self.log(f'交易完成 | {result} | 净利润: {trade.pnl:.2f} | 连续亏损: {self.consecutive_losses}', force=True)

    def next(self):
        if self.order:
            return

        # 检查并更新参数组合
        self.update_params_if_needed()

        if self.consecutive_losses >= self.params.max_consecutive_losses:
            return

        if self.last_trade_date == self.data_15m.datetime.date(0):
            if self.daily_profit < -self.params.max_daily_loss_pct * self.broker.getvalue():
                return

        equity = self.broker.getvalue()
        if equity > self.max_portfolio_value:
            self.max_portfolio_value = equity

        if self.position.size == 0:
            self.current_position = None
        elif self.position.size > 0:
            self.current_position = 'long'
        else:
            self.current_position = 'short'

        if self.current_position is None:
            trend = self.get_trend_direction()

            if trend == 'sideways':
                return

            market_filter_ok = self.check_market_filter()
            if not market_filter_ok:
                return

            bullish_breakout, bearish_breakout = self.check_breakout()
            bullish_rsi, bearish_rsi = self.check_rsi_momentum()
            price_above_ema, price_below_ema = self.check_ema_position()

            if trend == 'bullish' and bullish_breakout and bullish_rsi and price_above_ema:
                if self.check_trend_resonance('long'):
                    if self.check_trend_duration('bullish'):
                        if self.check_rsi_extreme('long'):
                            if self.check_breakout_persistence('long', bullish_breakout, bearish_breakout):
                                if self.check_volume_confirmation():
                                    size = self.calculate_position_size('long')
                                    if size > 0:
                                        self.log(f'多头信号触发 | 仓位: {size:.4f}', force=True)
                                        self.order = self.buy(size=size)

            elif trend == 'bearish' and bearish_breakout and bearish_rsi and price_below_ema:
                if self.check_trend_resonance('short'):
                    if self.check_trend_duration('bearish'):
                        if self.check_rsi_extreme('short'):
                            if self.check_breakout_persistence('short', bullish_breakout, bearish_breakout):
                                if self.check_volume_confirmation():
                                    size = self.calculate_position_size('short')
                                    if size > 0:
                                        self.log(f'空头信号触发 | 仓位: {size:.4f}', force=True)
                                        self.order = self.sell(size=size)

        else:
            self.bars_since_entry += 1

            if self.entry_direction == 'long':
                if not self.stop_moved_to_cost:
                    if self.data_15m.close[0] >= self.take_profit_1:
                        self.stop_loss = self.entry_price
                        self.stop_moved_to_cost = True
                        self.log('止损移动到成本价(保本)', force=True)
                else:
                    new_stop = self.data_15m.close[0] - self.m15_atr[0] * self.get_risk_param('trailing_stop_atr')
                    if new_stop > self.stop_loss:
                        self.stop_loss = new_stop

                if not self.partial_take_profit_done:
                    if self.data_15m.close[0] >= self.take_profit_2:
                        half_size = abs(self.position.size) / 2
                        self.log(f'部分止盈50% | 数量: {half_size:.4f}', force=True)
                        self.order = self.sell(size=half_size)
                        self.partial_take_profit_done = True
                        return

                if self.check_ema_exit():
                    self.log('EMA破位出场', force=True)
                    self.order = self.sell(size=abs(self.position.size))
                    self.ema_break_count = 0
                    return

                if self.data_15m.low[0] <= self.stop_loss:
                    self.log('止损触发(多头)', force=True)
                    self.order = self.sell(size=abs(self.position.size))
                    return

                if self.data_15m.high[0] >= self.take_profit_2:
                    self.log('止盈触发(多头)', force=True)
                    self.order = self.sell(size=abs(self.position.size))
                    return

            elif self.entry_direction == 'short':
                if not self.stop_moved_to_cost:
                    if self.data_15m.close[0] <= self.take_profit_1:
                        self.stop_loss = self.entry_price
                        self.stop_moved_to_cost = True
                        self.log('止损移动到成本价(保本)', force=True)
                else:
                    new_stop = self.data_15m.close[0] + self.m15_atr[0] * self.get_risk_param('trailing_stop_atr')
                    if new_stop < self.stop_loss:
                        self.stop_loss = new_stop

                if not self.partial_take_profit_done:
                    if self.data_15m.close[0] <= self.take_profit_2:
                        half_size = abs(self.position.size) / 2
                        self.log(f'部分止盈50% | 数量: {half_size:.4f}', force=True)
                        self.order = self.buy(size=half_size)
                        self.partial_take_profit_done = True
                        return

                if self.check_ema_exit():
                    self.log('EMA破位出场', force=True)
                    self.order = self.buy(size=abs(self.position.size))
                    self.ema_break_count = 0
                    return

                if self.data_15m.high[0] >= self.stop_loss:
                    self.log('止损触发(空头)', force=True)
                    self.order = self.buy(size=abs(self.position.size))
                    return

                if self.data_15m.low[0] <= self.take_profit_2:
                    self.log('止盈触发(空头)', force=True)
                    self.order = self.buy(size=abs(self.position.size))
                    return
