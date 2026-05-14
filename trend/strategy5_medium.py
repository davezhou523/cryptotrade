import backtrader as bt

from trend.strategy5 import Strategy5


class Strategy5Medium(Strategy5):
    """策略5中频版：温和放宽1H入场位置，目标提升到中频交易节奏"""

    params = (
        ('medium_shallow_atr_distance', None),
        ('medium_rsi_long_low', None),
        ('medium_rsi_long_high', None),
        ('medium_rsi_short_low', None),
        ('medium_rsi_short_high', None),
        ('medium_position_scale', None),
        ('medium_recent_crossover_lookback', None),
        ('medium_recent_crossover_atr_distance', None),
        ('medium_recent_crossover_adx_threshold', None),
        ('medium_recent_crossover_position_scale', None),
        ('medium_recent_crossover_spread_max_atr', None),
    )

    def __init__(self):
        super().__init__()
        self.log('=== Strategy5 Medium 初始化完成 ===', force=True)

    def get_entry_mode_label(self, mode):
        mode_map = {
            'pullback': '标准回调',
            'crossover': '趋势交叉',
            'shallow_pullback': '浅回踩',
            'crossover_follow': '交叉跟随',
        }
        return mode_map.get(mode, '标准回调')

    def has_recent_h1_crossover(self, trend_direction):
        lookback_bars = self.params.medium_recent_crossover_lookback
        if lookback_bars <= 0:
            return False

        if len(self.data_1h) < self.params.h1_ema_slow + lookback_bars + 3:
            return False

        for bars_ago in range(1, lookback_bars + 1):
            current_idx = -bars_ago
            prev_idx = -bars_ago - 1
            if trend_direction == 'bullish':
                crossed = (
                    self.h1_ema21[current_idx] > self.h1_ema55[current_idx]
                    and self.h1_ema21[prev_idx] <= self.h1_ema55[prev_idx]
                )
            else:
                crossed = (
                    self.h1_ema21[current_idx] < self.h1_ema55[current_idx]
                    and self.h1_ema21[prev_idx] >= self.h1_ema55[prev_idx]
                )

            if crossed:
                return True

        return False

    def is_crossover_spread_valid(self, e21, e55, h1_atr):
        if h1_atr <= 0:
            return False

        ema_spread_atr = abs(e21 - e55) / h1_atr
        return ema_spread_atr <= self.params.medium_recent_crossover_spread_max_atr

    def check_pullback_condition(self, trend_direction):
        if super().check_pullback_condition(trend_direction):
            return True

        if len(self.data_1h) < self.params.h1_ema_slow + self.params.medium_recent_crossover_lookback + 5:
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

        if h1_atr <= 0:
            return False

        if trend_direction == 'bullish':
            if price < zone_low:
                return False

            if self.h1_last_low is not None and price < self.h1_last_low:
                return False

            if self.h1_ema21[0] <= self.h1_ema21[-1]:
                return False

            shallow_upper = e21 + self.params.medium_shallow_atr_distance * h1_atr
            if zone_high < price <= shallow_upper:
                if (
                    self.params.medium_rsi_long_low <= rsi <= self.params.medium_rsi_long_high
                    and macd_hist > 0
                    and macd_hist >= prev_macd_hist
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                ):
                    self.pullback_scale = self.params.medium_position_scale
                    self.entry_mode = 'shallow_pullback'
                    return True

            if self.has_recent_h1_crossover('bullish'):
                crossover_upper = e21 + self.params.medium_recent_crossover_atr_distance * h1_atr
                if (
                    e21 <= price <= crossover_upper
                    and self.is_crossover_spread_valid(e21, e55, h1_atr)
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                    and macd_hist > 0
                    and prev_macd_hist > 0
                    and macd_hist >= prev_macd_hist
                    and self.params.h1_rsi_long_low <= rsi <= self.params.h1_rsi_long_high
                ):
                    self.pullback_scale = self.params.medium_recent_crossover_position_scale
                    self.entry_mode = 'crossover_follow'
                    return True

            return False

        if trend_direction == 'bearish':
            if price > zone_high:
                return False

            if self.h1_last_high is not None and price > self.h1_last_high:
                return False

            if self.h1_ema21[0] >= self.h1_ema21[-1]:
                return False

            shallow_lower = e21 - self.params.medium_shallow_atr_distance * h1_atr
            if shallow_lower <= price < zone_low:
                if (
                    self.params.medium_rsi_short_low <= rsi <= self.params.medium_rsi_short_high
                    and macd_hist < 0
                    and macd_hist <= prev_macd_hist
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                ):
                    self.pullback_scale = self.params.medium_position_scale
                    self.entry_mode = 'shallow_pullback'
                    return True

            if self.has_recent_h1_crossover('bearish'):
                crossover_lower = e21 - self.params.medium_recent_crossover_atr_distance * h1_atr
                if (
                    crossover_lower <= price <= e21
                    and self.is_crossover_spread_valid(e21, e55, h1_atr)
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                    and macd_hist < 0
                    and prev_macd_hist < 0
                    and macd_hist <= prev_macd_hist
                    and self.params.h1_rsi_short_low <= rsi <= self.params.h1_rsi_short_high
                ):
                    self.pullback_scale = self.params.medium_recent_crossover_position_scale
                    self.entry_mode = 'crossover_follow'
                    return True

            return False

        return False


class Strategy5MediumV2(Strategy5Medium):
    """策略5中频版V2：进一步提升触发密度，目标靠近 120-180 笔/年"""

    params = (
        ('medium_shallow_atr_distance', 0.32),
        ('medium_rsi_long_low', 46),
        ('medium_rsi_long_high', 64),
        ('medium_rsi_short_low', 36),
        ('medium_rsi_short_high', 54),
        ('medium_position_scale', 0.92),
        ('medium_recent_crossover_lookback', 2),
        ('medium_recent_crossover_atr_distance', 0.55),
        ('medium_recent_crossover_adx_threshold', 22),
        ('medium_recent_crossover_position_scale', 0.88),
        ('medium_recent_crossover_spread_max_atr', 0.95),
    )

    def __init__(self):
        super().__init__()
        self.log('=== Strategy5 Medium V2 初始化完成 ===', force=True)

    def check_pullback_condition(self, trend_direction):
        if super().check_pullback_condition(trend_direction):
            return True

        if len(self.data_1h) < self.params.h1_ema_slow + self.params.medium_recent_crossover_lookback + 5:
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

        if h1_atr <= 0:
            return False

        if trend_direction == 'bullish':
            if price < zone_low:
                return False

            if self.h1_last_low is not None and price < self.h1_last_low:
                return False

            if self.h1_ema21[0] < self.h1_ema21[-1]:
                return False

            shallow_upper = e21 + self.params.medium_shallow_atr_distance * h1_atr
            if zone_high < price <= shallow_upper:
                if (
                    self.params.medium_rsi_long_low <= rsi <= self.params.medium_rsi_long_high
                    and macd_hist > 0
                    and macd_hist >= prev_macd_hist
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                ):
                    self.pullback_scale = self.params.medium_position_scale
                    self.entry_mode = 'shallow_pullback'
                    return True

            if self.has_recent_h1_crossover('bullish'):
                crossover_lower = e21 - 0.12 * h1_atr
                crossover_upper = e21 + self.params.medium_recent_crossover_atr_distance * h1_atr
                if (
                    crossover_lower <= price <= crossover_upper
                    and self.is_crossover_spread_valid(e21, e55, h1_atr)
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                    and macd_hist > 0
                    and macd_hist >= prev_macd_hist
                    and self.params.medium_rsi_long_low <= rsi <= self.params.medium_rsi_long_high
                ):
                    self.pullback_scale = self.params.medium_recent_crossover_position_scale
                    self.entry_mode = 'crossover_follow'
                    return True

            return False

        if trend_direction == 'bearish':
            if price > zone_high:
                return False

            if self.h1_last_high is not None and price > self.h1_last_high:
                return False

            if self.h1_ema21[0] > self.h1_ema21[-1]:
                return False

            shallow_lower = e21 - self.params.medium_shallow_atr_distance * h1_atr
            if shallow_lower <= price < zone_low:
                if (
                    self.params.medium_rsi_short_low <= rsi <= self.params.medium_rsi_short_high
                    and macd_hist < 0
                    and macd_hist <= prev_macd_hist
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                ):
                    self.pullback_scale = self.params.medium_position_scale
                    self.entry_mode = 'shallow_pullback'
                    return True

            if self.has_recent_h1_crossover('bearish'):
                crossover_lower = e21 - self.params.medium_recent_crossover_atr_distance * h1_atr
                crossover_upper = e21 + 0.12 * h1_atr
                if (
                    crossover_lower <= price <= crossover_upper
                    and self.is_crossover_spread_valid(e21, e55, h1_atr)
                    and adx >= self.params.medium_recent_crossover_adx_threshold
                    and macd_hist < 0
                    and macd_hist <= prev_macd_hist
                    and self.params.medium_rsi_short_low <= rsi <= self.params.medium_rsi_short_high
                ):
                    self.pullback_scale = self.params.medium_recent_crossover_position_scale
                    self.entry_mode = 'crossover_follow'
                    return True

            return False

        return False


class Strategy5MediumV3(Strategy5MediumV2):
    """策略5中频版V3：轻放松4H趋势，放大1H观察区，强化15M连续动量触发"""

    params = (
        ('medium_h4_trend_midpoint_ratio', 0.5),
        ('medium_continuation_rsi_long', 50),
        ('medium_continuation_rsi_short', 50),
        ('medium_continuation_ema_distance_atr', 0.8),
    )

    def __init__(self):
        super().__init__()
        self.log('=== Strategy5 Medium V3 初始化完成 ===', force=True)

    def get_trend_direction(self):
        if len(self.data_4h) < self.params.h4_ema_slow:
            return None

        price = self.data_4h.close[0]
        e21 = self.h4_ema21[0]
        e55 = self.h4_ema55[0]

        midpoint = e55 + (e21 - e55) * self.params.medium_h4_trend_midpoint_ratio

        if e21 > e55 and price >= midpoint:
            return 'bullish'
        if e21 < e55 and price <= midpoint:
            return 'bearish'
        return 'sideways'

    def check_entry_signal(self, trend_direction):
        lookback = self.params.m15_breakout_lookback
        if len(self.data_15m) < max(lookback + 2, 4):
            return False

        highs = list(self.data_15m.high.get(size=lookback + 1))
        lows = list(self.data_15m.low.get(size=lookback + 1))
        recent_high = max(highs[:-1])
        recent_low = min(lows[:-1])

        price = self.data_15m.close[0]
        prev_price = self.data_15m.close[-1]
        ema = self.m15_ema21[0]
        atr = self.m15_atr[0]
        rsi_now = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]
        rsi_prev2 = self.m15_rsi[-2]

        ema_distance_ok = True
        if atr > 0:
            ema_distance_ok = abs(price - ema) <= self.params.medium_continuation_ema_distance_atr * atr

        if trend_direction == 'bullish':
            structure_trigger = price > recent_high
            rsi_trigger = rsi_now > 50 and rsi_prev <= 50
            rsi_bias_ok = rsi_now >= self.params.m15_rsi_bias_long
            continuation_trigger = (
                price >= ema
                and price >= prev_price
                and ema_distance_ok
                and rsi_now >= self.params.medium_continuation_rsi_long
                and rsi_now >= rsi_prev >= rsi_prev2
            )
            return structure_trigger or rsi_trigger or rsi_bias_ok or continuation_trigger

        if trend_direction == 'bearish':
            structure_trigger = price < recent_low
            rsi_trigger = rsi_now < 50 and rsi_prev >= 50
            rsi_bias_ok = rsi_now <= self.params.m15_rsi_bias_short
            continuation_trigger = (
                price <= ema
                and price <= prev_price
                and ema_distance_ok
                and rsi_now <= self.params.medium_continuation_rsi_short
                and rsi_now <= rsi_prev <= rsi_prev2
            )
            return structure_trigger or rsi_trigger or rsi_bias_ok or continuation_trigger

        return False


class Strategy5MediumV31(Strategy5MediumV3):
    """策略5中频版V3.1：保留V3频率，重点收紧BTC/BNB的连续动量噪音"""

    params = (
        ('medium_continuation_min_price_move_atr', 0.0),
        ('medium_continuation_min_rsi_step', 0.0),
        ('medium_continuation_require_ema_slope', False),
        ('medium_continuation_price_streak_bars', 1),
    )

    def __init__(self):
        super().__init__()
        self.log('=== Strategy5 Medium V3.1 初始化完成 ===', force=True)

    def has_price_streak(self, direction):
        streak_bars = max(1, int(self.params.medium_continuation_price_streak_bars))
        if len(self.data_15m) < streak_bars + 1:
            return False

        for idx in range(streak_bars):
            current_close = self.data_15m.close[-idx]
            prev_close = self.data_15m.close[-idx - 1]
            if direction == 'bullish':
                if current_close < prev_close:
                    return False
            else:
                if current_close > prev_close:
                    return False
        return True

    def check_entry_signal(self, trend_direction):
        lookback = self.params.m15_breakout_lookback
        if len(self.data_15m) < max(lookback + 2, 5):
            return False

        highs = list(self.data_15m.high.get(size=lookback + 1))
        lows = list(self.data_15m.low.get(size=lookback + 1))
        recent_high = max(highs[:-1])
        recent_low = min(lows[:-1])

        price = self.data_15m.close[0]
        prev_price = self.data_15m.close[-1]
        ema = self.m15_ema21[0]
        prev_ema = self.m15_ema21[-1]
        atr = self.m15_atr[0]
        rsi_now = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]
        rsi_prev2 = self.m15_rsi[-2]

        ema_distance_ok = True
        price_move_ok = True
        if atr > 0:
            ema_distance_ok = abs(price - ema) <= self.params.medium_continuation_ema_distance_atr * atr
            price_move_ok = abs(price - prev_price) >= self.params.medium_continuation_min_price_move_atr * atr

        rsi_step_ok = abs(rsi_now - rsi_prev) >= self.params.medium_continuation_min_rsi_step

        if trend_direction == 'bullish':
            structure_trigger = price > recent_high
            rsi_trigger = rsi_now > 50 and rsi_prev <= 50
            rsi_bias_ok = rsi_now >= self.params.m15_rsi_bias_long
            ema_slope_ok = (not self.params.medium_continuation_require_ema_slope) or ema >= prev_ema
            continuation_trigger = (
                price >= ema
                and price >= prev_price
                and ema_distance_ok
                and price_move_ok
                and rsi_step_ok
                and ema_slope_ok
                and self.has_price_streak('bullish')
                and rsi_now >= self.params.medium_continuation_rsi_long
                and rsi_now >= rsi_prev >= rsi_prev2
            )
            return structure_trigger or rsi_trigger or rsi_bias_ok or continuation_trigger

        if trend_direction == 'bearish':
            structure_trigger = price < recent_low
            rsi_trigger = rsi_now < 50 and rsi_prev >= 50
            rsi_bias_ok = rsi_now <= self.params.m15_rsi_bias_short
            ema_slope_ok = (not self.params.medium_continuation_require_ema_slope) or ema <= prev_ema
            continuation_trigger = (
                price <= ema
                and price <= prev_price
                and ema_distance_ok
                and price_move_ok
                and rsi_step_ok
                and ema_slope_ok
                and self.has_price_streak('bearish')
                and rsi_now <= self.params.medium_continuation_rsi_short
                and rsi_now <= rsi_prev <= rsi_prev2
            )
            return structure_trigger or rsi_trigger or rsi_bias_ok or continuation_trigger

        return False


class Strategy5HighFrequency(Strategy5MediumV31):
    """当前高频主线策略：按币种自动套参数的正式版本。"""

    def __init__(self):
        super().__init__()
        self.log('=== Strategy5 High Frequency 初始化完成 ===', force=True)