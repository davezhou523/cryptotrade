"""
震荡策略 v4 (Volatility Strategy v4)

多周期架构：
1. 4H 判断震荡（评分制）
   - ADX < 20 → +1
   - EMA21 与 EMA55 接近 → +1
   - ATR 下降 → +1
   - score >= 2 → 震荡

2. 1H 找区间（布林带）
   - 上轨 = 压力
   - 下轨 = 支撑
   - 中线 = 中性位

3. 15M 入场执行
   做多：4H震荡 + 价格接近1H下轨(支撑) + 15M信号
   做空：4H震荡 + 价格接近1H上轨(压力) + 15M信号

4. 假突破（插针）
   价格突破1H区间但4H ADX仍<20 → 反向做
"""

import backtrader as bt
import math


class StrategyVolatility(bt.Strategy):
    params = (
        ('printlog', None), ('eventlog', None), ('debuglog', None),

        # 4H 震荡判断
        ('h4_adx_period', None),       # ADX周期
        ('h4_adx_threshold', None),    # ADX阈值（如20）
        ('h4_ema_fast', None),         # 快速EMA（如21）
        ('h4_ema_slow', None),         # 慢速EMA（如55）
        ('h4_ema_closeness', None),    # EMA接近度阈值（如0.005=0.5%）
        ('h4_atr_period', None),       # ATR周期
        ('h4_osc_score_min', None),    # 震荡最低评分（如2）

        # 1H 区间（BB）
        ('h1_bb_period', None),
        ('h1_bb_dev', None),

        # 15M 入场信号
        ('m15_bb_period', None), ('m15_bb_dev', None),
        ('m15_rsi_period', None),
        ('m15_rsi_long', None),       # RSI超卖阈值
        ('m15_rsi_short', None),      # RSI超买阈值
        ('m15_rsi_confirm_long', None),  # RSI确认回升阈值
        ('m15_rsi_confirm_short', None), # RSI确认回落阈值

        # 15M K线形态
        ('use_pin_bar', None),         # 使用Pin Bar信号
        ('use_engulfing', None),       # 使用吞没形态信号
        ('pin_bar_ratio', None),       # Pin Bar影线/实体比（如2.0）

        # 入场信号强度
        ('min_signals', None),         # 最少需要的15M信号数（如2）
        ('require_bb_bounce', None),   # 是否必须BB反弹确认

        # 1H区间接近度
        ('zone_proximity', None),      # 接近1H BB轨的距离比例（如0.2=20%带宽内）

        # 假突破
        ('fake_breakout', None),       # 启用假突破检测

        # 1H K线方向过滤
        ('use_h1_candle_filter', None),  # 做多须1H阳线，做空须1H阴线

        # 4H趋势方向过滤
        ('use_h4_trend_filter', None),   # EMA21>EMA55只做多,反之只做空

        # 止损（基于1H BB区间）
        ('sl_method', None),           # 'h1bb'=1H BB轨道止损, 'm15bb'=15M BB轨道止损
        ('sl_atr_offset', None),       # 止损距BB轨道的ATR偏移

        # 移动止损
        ('use_trailing_stop', None),   # 启用移动止损
        ('trail_atr_mult', None),      # 移动止损ATR倍数（如1.5）
        ('trail_activate', None),      # 激活移动止损的盈利ATR倍数（如1.0）

        # R:R过滤
        ('min_rr', None),              # 最低风险回报比（如1.5）

        # 时间止损
        ('use_time_stop', None),       # 启用时间止损
        ('max_bars', None),            # 最大持仓K线数（如32=8小时）

        # 连亏过滤
        ('use_consec_loss_filter', None),  # 启用连亏过滤
        ('max_consec_losses', None),       # 连亏N次后暂停

        # 保本止损
        ('use_breakeven_stop', None),      # 启用保本止损
        ('breakeven_activate', None),      # 盈利达到TP的X%时移动SL到成本（如0.5=50%）

        # 阶梯追踪（保本后）
        ('use_stepped_trail', None),       # 启用阶梯追踪
        ('trail_step1_pct', None),         # 第一阶梯：价格达TP的X%时SL移到利润的Y%
        ('trail_step1_sl', None),          # 第一阶梯SL位置（占TP距离的%，如0.3=30%）
        ('trail_step2_pct', None),         # 第二阶梯：价格达TP的X%时SL移到利润的Y%
        ('trail_step2_sl', None),          # 第二阶梯SL位置（占TP距离的%，如0.6=60%）

        # 1H BB宽度过滤
        ('min_h1_bb_width', None),         # 1H BB最小宽度（占价格%，如0.03=3%）

        # 1H RSI过滤
        ('use_h1_rsi_filter', None),       # 1H RSI超买不做多，超卖不做空
        ('h1_rsi_period', None),
        ('h1_rsi_long_max', None),         # 做多时1H RSI上限
        ('h1_rsi_short_min', None),        # 做空时1H RSI下限

        # 止盈
        ('tp_method', None),           # 'mid'=1H BB中线, 'band'=1H对侧轨道, 'rsi'=RSI反向, 'split'=分批
        ('tp_atr_offset', None),
        ('split_tp_ratio', None),      # 分批止盈：第一批在中轨止盈的比例（如0.5=50%）

        # 仓位
        ('risk_per_trade', None),
        ('risk_after_win', None),       # 赢后风险比例（如0.02）
        ('risk_after_loss', None),      # 亏后风险比例（如0.01）
        ('m15_atr_period', None),
        ('leverage', None), ('max_leverage_ratio', None),
        ('max_positions', None),

        # ML信号过滤
        ('use_ml_filter', None),        # 启用ML过滤
        ('ml_model_path', None),        # ML模型路径
        ('ml_prob_threshold', None),    # ML概率阈值（如0.55=概率>55%才入场）

        # ML训练数据收集
        ('ml_collect_data', None),      # 启用ML数据收集模式
    )

    def __init__(self):
        required = [
            'printlog', 'eventlog', 'debuglog',
            'h4_adx_period', 'h4_adx_threshold',
            'h4_ema_fast', 'h4_ema_slow', 'h4_ema_closeness',
            'h4_atr_period', 'h4_osc_score_min',
            'h1_bb_period', 'h1_bb_dev',
            'm15_bb_period', 'm15_bb_dev',
            'm15_rsi_period', 'm15_rsi_long', 'm15_rsi_short',
            'm15_rsi_confirm_long', 'm15_rsi_confirm_short',
            'use_pin_bar', 'use_engulfing', 'pin_bar_ratio',
            'min_signals', 'require_bb_bounce', 'zone_proximity', 'fake_breakout',
            'use_h1_candle_filter',
            'use_h4_trend_filter',
            'sl_method', 'sl_atr_offset',
            'use_trailing_stop', 'trail_atr_mult', 'trail_activate',
            'min_rr',
            'use_time_stop', 'max_bars',
            'use_consec_loss_filter', 'max_consec_losses',
            'use_breakeven_stop', 'breakeven_activate',
            'use_stepped_trail', 'trail_step1_pct', 'trail_step1_sl', 'trail_step2_pct', 'trail_step2_sl',
            'min_h1_bb_width',
            'use_h1_rsi_filter', 'h1_rsi_period', 'h1_rsi_long_max', 'h1_rsi_short_min',
            'tp_method', 'tp_atr_offset', 'split_tp_ratio', 'tp_method', 'tp_atr_offset',
            'risk_per_trade', 'risk_after_win', 'risk_after_loss', 'm15_atr_period',
            'leverage', 'max_leverage_ratio', 'max_positions',
            'use_ml_filter', 'ml_model_path', 'ml_prob_threshold', 'ml_collect_data',
        ]
        for p in required:
            if getattr(self.params, p) is None:
                raise ValueError(f"参数 '{p}' 未传入")

        self.data_15m = self.datas[0]  # 主(15M)
        self.data_1h = self.datas[1]   # 辅(1H)
        self.data_4h = self.datas[2]   # 辅(4H)

        # ========== 4H 指标 ==========
        self.h4_adx = bt.indicators.AverageDirectionalMovementIndex(
            self.data_4h, period=self.params.h4_adx_period)
        self.h4_ema_fast = bt.indicators.ExponentialMovingAverage(
            self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema_slow = bt.indicators.ExponentialMovingAverage(
            self.data_4h.close, period=self.params.h4_ema_slow)
        self.h4_atr = bt.indicators.ATR(
            self.data_4h, period=self.params.h4_atr_period)

        # ========== 1H 指标 ==========
        self.h1_bb = bt.indicators.BollingerBands(
            self.data_1h.close, period=self.params.h1_bb_period,
            devfactor=self.params.h1_bb_dev)
        self.h1_atr = bt.indicators.ATR(self.data_1h, period=14)
        self.h1_rsi = bt.indicators.RSI(
            self.data_1h.close, period=self.params.h1_rsi_period)

        # ========== 15M 指标 ==========
        self.m15_bb = bt.indicators.BollingerBands(
            self.data_15m.close, period=self.params.m15_bb_period,
            devfactor=self.params.m15_bb_dev)
        self.m15_rsi = bt.indicators.RSI(
            self.data_15m.close, period=self.params.m15_rsi_period)
        self.m15_atr = bt.indicators.ATR(
            self.data_15m, period=self.params.m15_atr_period)

        # BB宽度
        self.m15_bb_width = (self.m15_bb.lines.top - self.m15_bb.lines.bot) / self.m15_bb.lines.mid
        self.h1_bb_width = (self.h1_bb.lines.top - self.h1_bb.lines.bot) / self.h1_bb.lines.mid

        # 状态
        self.order = None
        self.stop_loss = None
        self.take_profit = None
        self.entry_price = None
        self.highest_profit = 0.0  # 跟踪最大盈利（用于移动止损）
        self.entry_bar = 0         # 入场K线索引
        self.consec_losses = 0     # 连续亏损计数
        self.partial_closed = False  # 分批止盈：是否已关闭第一批
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self._ready = False

        # ML信号过滤
        self._ml_filter = None
        self._ml_features_list = []   # 收集特征（训练模式）
        self._ml_labels_list = []     # 收集标签（训练模式）
        self._pending_entry_features = None  # 待匹配的入场特征

        # 初始化ML过滤模型
        if self.params.use_ml_filter and self.params.ml_model_path:
            try:
                import joblib
                loaded = joblib.load(self.params.ml_model_path)
                self._ml_filter = loaded
                self.log(f'ML模型已加载: {self.params.ml_model_path}', doprint=True)
            except Exception as e:
                self.log(f'ML模型加载失败: {e}', doprint=True)

        # 追踪：前几根K线是否触及15M BB
        self._touched_lower = False
        self._touched_upper = False
        self._touch_lower_bar = -999
        self._touch_upper_bar = -999
        self._bar_count = 0

    def log(self, txt, dt=None, doprint=False):
        if doprint or self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            t = self.datas[0].datetime.time(0)
            print(f'[{dt.isoformat()} {t}] {txt}')

    def dlog(self, txt):
        if self.params.debuglog:
            self.log(txt, doprint=True)

    @staticmethod
    def is_valid(v):
        if v is None:
            return False
        try:
            return not math.isnan(float(v))
        except (ValueError, TypeError):
            return False

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'BUY @ {order.executed.price:.2f} x {order.executed.size:.4f}',
                        doprint=self.params.eventlog)
            elif order.issell():
                self.log(f'SELL @ {order.executed.price:.2f} x {order.executed.size:.4f}',
                        doprint=self.params.eventlog)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected', doprint=self.params.eventlog)
        self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_count += 1
            if trade.pnl > 0:
                self.wins += 1
                self.consec_losses = 0
            else:
                self.losses += 1
                self.consec_losses += 1
            self.log(f'TRADE: PnL={trade.pnl:.2f}', doprint=self.params.eventlog)

            # ML训练数据收集：将交易结果与入场特征配对
            if self.params.ml_collect_data and self._pending_entry_features is not None:
                label = 1 if trade.pnl > 0 else 0
                self._ml_features_list.append(self._pending_entry_features)
                self._ml_labels_list.append(label)
                self._pending_entry_features = None

    def ready(self):
        if self._ready:
            return True
        if (self.is_valid(self.h4_adx[0]) and
            self.is_valid(self.h4_ema_fast[0]) and
            self.is_valid(self.h1_bb.lines.top[0]) and
            self.is_valid(self.m15_rsi[0])):
            self._ready = True
        return self._ready

    # ========== ML 特征提取与过滤 ==========

    def _extract_features(self, direction, signals, reason):
        """
        提取ML特征向量（入场时刻调用）
        direction: 'up' or 'down'
        signals: 15M信号列表
        reason: 入场原因字符串
        注意：不包含RR/SL/TP等事后信息，避免信息泄漏
        """
        import numpy as np
        features = []

        # 1. 4H特征
        h4_adx = self.h4_adx[0] if self.is_valid(self.h4_adx[0]) else 25.0
        features.append(h4_adx)

        ema_f = self.h4_ema_fast[0] if self.is_valid(self.h4_ema_fast[0]) else 0
        ema_s = self.h4_ema_slow[0] if self.is_valid(self.h4_ema_slow[0]) else 1
        ema_closeness = abs(ema_f - ema_s) / ema_s if ema_s > 0 else 0
        features.append(ema_closeness)

        h4_atr_cur = self.h4_atr[0] if self.is_valid(self.h4_atr[0]) else 0
        h4_atr_prev = self.h4_atr[-1] if self.is_valid(self.h4_atr[-1]) else 0
        atr_ratio = h4_atr_cur / h4_atr_prev if h4_atr_prev > 0 else 1
        features.append(atr_ratio)

        score, _ = self._h4_oscillation_score()
        features.append(score)

        # 2. 1H特征
        h1_bw = self.h1_bb_width[0] if self.is_valid(self.h1_bb_width[0]) else 0
        features.append(h1_bw)

        h1_rsi = self.h1_rsi[0] if self.is_valid(self.h1_rsi[0]) else 50
        features.append(h1_rsi)

        zone_pos, zone_pct = self._h1_zone_position()
        features.append(zone_pct)

        h1_atr = self.h1_atr[0] if self.is_valid(self.h1_atr[0]) else 0
        price = self.data_15m.close[0] if self.is_valid(self.data_15m.close[0]) else 1
        features.append(h1_atr / price if price > 0 else 0)

        # 3. 15M特征
        m15_rsi = self.m15_rsi[0] if self.is_valid(self.m15_rsi[0]) else 50
        features.append(m15_rsi)

        m15_bw = self.m15_bb_width[0] if self.is_valid(self.m15_bb_width[0]) else 0
        features.append(m15_bw)

        # 15M BB位置（价格在BB中的相对位置）
        m15_top = self.m15_bb.lines.top[0] if self.is_valid(self.m15_bb.lines.top[0]) else price
        m15_bot = self.m15_bb.lines.bot[0] if self.is_valid(self.m15_bb.lines.bot[0]) else price
        m15_mid = self.m15_bb.lines.mid[0] if self.is_valid(self.m15_bb.lines.mid[0]) else price
        m15_range = m15_top - m15_bot
        m15_pos = (price - m15_bot) / m15_range if m15_range > 0 else 0.5
        features.append(m15_pos)

        m15_atr = self.m15_atr[0] if self.is_valid(self.m15_atr[0]) else 0
        features.append(m15_atr / price if price > 0 else 0)

        # 4. 信号特征
        features.append(len(signals))  # 信号数量
        features.append(1 if direction == 'up' else 0)  # 方向（1=多，0=空）
        features.append(1 if 'RSI_bounce' in signals else 0)
        features.append(1 if 'PinBar' in signals else 0)
        features.append(1 if 'Engulfing' in signals else 0)
        features.append(1 if reason == 'FakeBreakout' else 0)

        # 5. 上下文特征
        features.append(self.consec_losses)
        features.append(self.wins / self.trade_count if self.trade_count > 0 else 0.5)  # 近期胜率

        return np.array(features, dtype=np.float32)

    def _ml_predict(self, features):
        """使用ML模型预测信号质量，返回(是否通过, 概率)"""
        if self._ml_filter is None:
            return True, 1.0
        try:
            model = self._ml_filter['model']
            scaler = self._ml_filter['scaler']
            X = features.reshape(1, -1)
            X_scaled = scaler.transform(X)
            prob = model.predict_proba(X_scaled)[0][1]
            passed = prob >= self.params.ml_prob_threshold
            return passed, prob
        except Exception as e:
            self.dlog(f'ML预测出错: {e}')
            return True, 1.0

    # ========== 第一步：4H 震荡评分 ==========

    def _h4_oscillation_score(self):
        """
        4H震荡评分（0-3分）：
        - ADX < threshold → +1
        - EMA21 与 EMA55 接近 → +1
        - ATR 下降 → +1
        score >= h4_osc_score_min → 震荡
        返回 (score, is_oscillation)
        """
        score = 0

        # 条件1: ADX < threshold
        adx = self.h4_adx[0]
        if self.is_valid(adx) and adx < self.params.h4_adx_threshold:
            score += 1

        # 条件2: EMA21 与 EMA55 接近（差距/价格 < closeness）
        ema_f = self.h4_ema_fast[0]
        ema_s = self.h4_ema_slow[0]
        if self.is_valid(ema_f) and self.is_valid(ema_s) and ema_s > 0:
            closeness = abs(ema_f - ema_s) / ema_s
            if closeness < self.params.h4_ema_closeness:
                score += 1

        # 条件3: ATR 下降（当前ATR < 前一根ATR）
        atr_cur = self.h4_atr[0]
        atr_prev = self.h4_atr[-1]
        if self.is_valid(atr_cur) and self.is_valid(atr_prev):
            if atr_cur < atr_prev:
                score += 1

        return score, score >= self.params.h4_osc_score_min

    # ========== 第二步：1H 区间定位 ==========

    def _h1_zone_position(self):
        """
        判断15M价格在1H BB区间中的位置
        返回 'lower'(接近支撑), 'upper'(接近压力), 'middle'(中间), 'breakout_up', 'breakout_down'
        """
        h1_top = self.h1_bb.lines.top[0]
        h1_bot = self.h1_bb.lines.bot[0]
        h1_mid = self.h1_bb.lines.mid[0]
        price = self.data_15m.close[0]

        if not (self.is_valid(h1_top) and self.is_valid(h1_bot) and self.is_valid(h1_mid)):
            return 'middle', 0.0

        band_width = h1_top - h1_bot
        if band_width <= 0:
            return 'middle', 0.0

        # 价格在区间中的位置百分比 (0=下轨, 1=上轨)
        position = (price - h1_bot) / band_width

        prox = self.params.zone_proximity

        if price < h1_bot:
            return 'breakout_down', position
        elif price > h1_top:
            return 'breakout_up', position
        elif position < prox:
            return 'lower', position    # 接近支撑
        elif position > (1 - prox):
            return 'upper', position    # 接近压力
        else:
            return 'middle', position

    # ========== 第三步：15M 入场信号 ==========

    def _update_touch_tracking(self):
        """追踪近期K线是否触及15M BB轨道"""
        self._bar_count += 1
        bb_bot = self.m15_bb.lines.bot[0]
        bb_top = self.m15_bb.lines.top[0]

        if not (self.is_valid(bb_bot) and self.is_valid(bb_top)):
            return

        low = self.data_15m.low[0]
        high = self.data_15m.high[0]

        if low <= bb_bot:
            self._touched_lower = True
            self._touch_lower_bar = self._bar_count
        if high >= bb_top:
            self._touched_upper = True
            self._touch_upper_bar = self._bar_count

        # 超过8根K线未再次触及则重置
        if self._bar_count - self._touch_lower_bar > 8:
            self._touched_lower = False
        if self._bar_count - self._touch_upper_bar > 8:
            self._touched_upper = False

    def _check_rsi_bounce_long(self):
        """RSI从超卖区回升"""
        rsi = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]
        if not (self.is_valid(rsi) and self.is_valid(rsi_prev)):
            return False
        return rsi_prev < self.params.m15_rsi_long and rsi > self.params.m15_rsi_confirm_long

    def _check_rsi_bounce_short(self):
        """RSI从超买区回落"""
        rsi = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]
        if not (self.is_valid(rsi) and self.is_valid(rsi_prev)):
            return False
        return rsi_prev > self.params.m15_rsi_short and rsi < self.params.m15_rsi_confirm_short

    def _check_rsi_oversold(self):
        """RSI超卖（简单信号）"""
        rsi = self.m15_rsi[0]
        return self.is_valid(rsi) and rsi < self.params.m15_rsi_long

    def _check_rsi_overbought(self):
        """RSI超买（简单信号）"""
        rsi = self.m15_rsi[0]
        return self.is_valid(rsi) and rsi > self.params.m15_rsi_short

    def _check_bb_bounce_long(self):
        """15M BB下轨反弹确认"""
        if not self._touched_lower:
            return False
        bb_bot = self.m15_bb.lines.bot[0]
        close = self.data_15m.close[0]
        return self.is_valid(bb_bot) and close > bb_bot

    def _check_bb_bounce_short(self):
        """15M BB上轨回落确认"""
        if not self._touched_upper:
            return False
        bb_top = self.m15_bb.lines.top[0]
        close = self.data_15m.close[0]
        return self.is_valid(bb_top) and close < bb_top

    def _check_pin_bar_long(self):
        """
        看涨Pin Bar：
        - 下影线长，实体小
        - 下影线 >= pin_bar_ratio * 实体
        - 上影线短
        """
        if not self.params.use_pin_bar:
            return False
        o = self.data_15m.open[0]
        h = self.data_15m.high[0]
        l = self.data_15m.low[0]
        c = self.data_15m.close[0]
        if not all(self.is_valid(x) for x in [o, h, l, c]):
            return False

        body = abs(c - o)
        if body < 0.01:  # 十字星也算
            body = 0.01
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        return lower_wick >= self.params.pin_bar_ratio * body and upper_wick < body

    def _check_pin_bar_short(self):
        """
        看跌Pin Bar：
        - 上影线长，实体小
        - 上影线 >= pin_bar_ratio * 实体
        - 下影线短
        """
        if not self.params.use_pin_bar:
            return False
        o = self.data_15m.open[0]
        h = self.data_15m.high[0]
        l = self.data_15m.low[0]
        c = self.data_15m.close[0]
        if not all(self.is_valid(x) for x in [o, h, l, c]):
            return False

        body = abs(c - o)
        if body < 0.01:
            body = 0.01
        lower_wick = min(o, c) - l
        upper_wick = h - max(o, c)

        return upper_wick >= self.params.pin_bar_ratio * body and lower_wick < body

    def _check_engulfing_long(self):
        """看涨吞没：当前阳线完全包含前一根阴线"""
        if not self.params.use_engulfing:
            return False
        o0 = self.data_15m.open[0]
        c0 = self.data_15m.close[0]
        o1 = self.data_15m.open[-1]
        c1 = self.data_15m.close[-1]
        if not all(self.is_valid(x) for x in [o0, c0, o1, c1]):
            return False
        # 前一根阴线，当前阳线，且当前实体包含前一根实体
        return c1 < o1 and c0 > o0 and c0 > o1 and o0 < c1

    def _check_engulfing_short(self):
        """看跌吞没：当前阴线完全包含前一根阳线"""
        if not self.params.use_engulfing:
            return False
        o0 = self.data_15m.open[0]
        c0 = self.data_15m.close[0]
        o1 = self.data_15m.open[-1]
        c1 = self.data_15m.close[-1]
        if not all(self.is_valid(x) for x in [o0, c0, o1, c1]):
            return False
        # 前一根阳线，当前阴线，且当前实体包含前一根实体
        return c1 > o1 and c0 < o0 and c0 < o1 and o0 > c1

    def _m15_long_signal(self):
        """15M做多信号（满足min_signals个即可）"""
        signals = []

        if self._check_rsi_bounce_long():
            signals.append('RSI_bounce')
        if self._check_bb_bounce_long():
            signals.append('BB_bounce')
        if self._check_pin_bar_long():
            signals.append('PinBar')
        if self._check_engulfing_long():
            signals.append('Engulfing')
        if self._check_rsi_oversold():
            signals.append('RSI_oversold')

        # 必须有BB反弹确认
        if self.params.require_bb_bounce and 'BB_bounce' not in signals:
            return []

        # 信号数不足
        if len(signals) < self.params.min_signals:
            return []

        return signals

    def _m15_short_signal(self):
        """15M做空信号（满足min_signals个即可）"""
        signals = []

        if self._check_rsi_bounce_short():
            signals.append('RSI_bounce')
        if self._check_bb_bounce_short():
            signals.append('BB_bounce')
        if self._check_pin_bar_short():
            signals.append('PinBar')
        if self._check_engulfing_short():
            signals.append('Engulfing')
        if self._check_rsi_overbought():
            signals.append('RSI_overbought')

        if self.params.require_bb_bounce and 'BB_bounce' not in signals:
            return []

        if len(signals) < self.params.min_signals:
            return []

        return signals

    # ========== 假突破检测 ==========

    def _check_h1_candle(self, direction):
        """1H K线方向过滤：做多须1H阳线，做空须1H阴线"""
        if not self.params.use_h1_candle_filter:
            return True
        h1_open = self.data_1h.open[0]
        h1_close = self.data_1h.close[0]
        if not (self.is_valid(h1_open) and self.is_valid(h1_close)):
            return True
        if direction == 'up':
            return h1_close >= h1_open  # 阳线
        else:
            return h1_close <= h1_open  # 阴线

    def _check_h4_trend(self, direction):
        """4H趋势方向过滤：EMA21>EMA55只做多，反之只做空"""
        if not self.params.use_h4_trend_filter:
            return True
        ema_f = self.h4_ema_fast[0]
        ema_s = self.h4_ema_slow[0]
        if not (self.is_valid(ema_f) and self.is_valid(ema_s)):
            return True
        # EMA接近（震荡区间）→ 允许双向
        closeness = abs(ema_f - ema_s) / ema_s if ema_s > 0 else 0
        if closeness < self.params.h4_ema_closeness:
            return True
        if direction == 'up':
            return ema_f > ema_s  # 上升趋势只做多
        else:
            return ema_f < ema_s  # 下降趋势只做空

    def _check_h1_rsi(self, direction):
        """1H RSI过滤：做多时1H RSI不过高，做空时1H RSI不过低"""
        if not self.params.use_h1_rsi_filter:
            return True
        rsi = self.h1_rsi[0]
        if not self.is_valid(rsi):
            return True
        if direction == 'up':
            return rsi < self.params.h1_rsi_long_max
        else:
            return rsi > self.params.h1_rsi_short_min

    def _check_h1_bb_width(self):
        """1H BB宽度过滤：BB太窄时不交易（R:R不够）"""
        if not self.params.min_h1_bb_width or self.params.min_h1_bb_width <= 0:
            return True
        bw = self.h1_bb_width[0]
        if not self.is_valid(bw):
            return True
        return bw >= self.params.min_h1_bb_width

    def _check_fake_breakout_long(self):
        """
        假突破做多：价格向下突破1H下轨，但4H ADX仍<20
        → 插针后反弹，做多
        """
        if not self.params.fake_breakout:
            return False
        zone_pos, _ = self._h1_zone_position()
        if zone_pos != 'breakout_down':
            return False
        # 4H仍然低ADX → 假突破
        adx = self.h4_adx[0]
        if not self.is_valid(adx):
            return False
        if adx >= self.params.h4_adx_threshold:
            return False
        # 15M有反弹信号
        signals = self._m15_long_signal()
        return len(signals) > 0

    def _check_fake_breakout_short(self):
        """
        假突破做空：价格向上突破1H上轨，但4H ADX仍<20
        → 插针后回落，做空
        """
        if not self.params.fake_breakout:
            return False
        zone_pos, _ = self._h1_zone_position()
        if zone_pos != 'breakout_up':
            return False
        adx = self.h4_adx[0]
        if not self.is_valid(adx):
            return False
        if adx >= self.params.h4_adx_threshold:
            return False
        signals = self._m15_short_signal()
        return len(signals) > 0

    # ========== 止盈计算 ==========

    def _calc_take_profit(self, direction):
        """
        止盈目标基于1H BB区间：
        - 'mid': 1H BB中线
        - 'band': 1H BB对侧轨道
        - 'rsi': RSI反向信号动态止盈
        """
        method = self.params.tp_method
        h1_mid = self.h1_bb.lines.mid[0]
        h1_top = self.h1_bb.lines.top[0]
        h1_bot = self.h1_bb.lines.bot[0]
        h1_atr = self.h1_atr[0]

        if not (self.is_valid(h1_mid) and self.is_valid(h1_atr)):
            return None

        if direction == 'up':
            if method == 'rsi':
                return None
            elif method == 'mid':
                return h1_mid
            elif method == 'mid_atr':
                return h1_mid + self.params.tp_atr_offset * h1_atr
            elif method == 'band':
                return h1_top if self.is_valid(h1_top) else None
        else:
            if method == 'rsi':
                return None
            elif method == 'mid':
                return h1_mid
            elif method == 'mid_atr':
                return h1_mid - self.params.tp_atr_offset * h1_atr
            elif method == 'band':
                return h1_bot if self.is_valid(h1_bot) else None
        return None

    # ========== 仓位计算 ==========

    def calc_size(self, sl_distance):
        """基于风险的动态仓位计算：赢后加仓，亏后减仓"""
        total = self.broker.getvalue()
        # 动态风险比例
        risk_pct = self.params.risk_per_trade
        if self.params.risk_after_win and self.params.risk_after_loss:
            if self.trade_count > 0:
                if self.consec_losses == 0:
                    risk_pct = self.params.risk_after_win  # 上次赢
                else:
                    risk_pct = self.params.risk_after_loss  # 上次亏
        risk = total * risk_pct
        if sl_distance <= 0:
            return 0
        return risk / sl_distance

    # ========== 持仓管理 ==========

    def _manage_position(self, pos, cur):
        """持仓管理：止损 + 止盈 + 移动止损"""
        is_long = pos.size > 0

        # 更新最大盈利跟踪
        if self.entry_price and self.is_valid(cur):
            if is_long:
                profit = cur - self.entry_price
            else:
                profit = self.entry_price - cur
            self.highest_profit = max(self.highest_profit, profit)

        # 移动止损
        if self.params.use_trailing_stop and self.entry_price and self.is_valid(cur):
            m15_atr = self.m15_atr[0]
            if self.is_valid(m15_atr) and m15_atr > 0:
                activate_dist = self.params.trail_activate * m15_atr
                trail_dist = self.params.trail_atr_mult * m15_atr

                if self.highest_profit >= activate_dist:
                    if is_long:
                        trail_sl = cur - trail_dist
                        if trail_sl > self.stop_loss:
                            self.stop_loss = trail_sl
                    else:
                        trail_sl = cur + trail_dist
                        if trail_sl < self.stop_loss:
                            self.stop_loss = trail_sl

        # 保本止损
        if self.params.use_breakeven_stop and self.entry_price and self.take_profit:
            if is_long:
                tp_dist = self.take_profit - self.entry_price
                if tp_dist > 0 and cur >= self.entry_price + tp_dist * self.params.breakeven_activate:
                    if self.stop_loss < self.entry_price:
                        self.stop_loss = self.entry_price
                        self.dlog(f'BE SL→{self.stop_loss:.2f}')
            else:
                tp_dist = self.entry_price - self.take_profit
                if tp_dist > 0 and cur <= self.entry_price - tp_dist * self.params.breakeven_activate:
                    if self.stop_loss > self.entry_price:
                        self.stop_loss = self.entry_price
                        self.dlog(f'BE SL→{self.stop_loss:.2f}')

        # 阶梯追踪：保本后继续上移SL
        if self.params.use_stepped_trail and self.entry_price and self.take_profit:
            # Step 1
            step_pct = self.params.trail_step1_pct
            step_sl = self.params.trail_step1_sl
            if step_pct > 0 and step_sl > 0:
                if is_long:
                    tp_dist = self.take_profit - self.entry_price
                    if tp_dist > 0 and cur >= self.entry_price + tp_dist * step_pct:
                        new_sl = self.entry_price + tp_dist * step_sl
                        if new_sl > self.stop_loss:
                            self.stop_loss = new_sl
                            self.dlog(f'STEP1 SL→{self.stop_loss:.2f}')
                else:
                    tp_dist = self.entry_price - self.take_profit
                    if tp_dist > 0 and cur <= self.entry_price - tp_dist * step_pct:
                        new_sl = self.entry_price - tp_dist * step_sl
                        if new_sl < self.stop_loss:
                            self.stop_loss = new_sl
                            self.dlog(f'STEP1 SL→{self.stop_loss:.2f}')
            # Step 2
            step2_pct = self.params.trail_step2_pct
            step2_sl = self.params.trail_step2_sl
            if step2_pct > 0 and step2_sl > 0:
                if is_long:
                    tp_dist = self.take_profit - self.entry_price
                    if tp_dist > 0 and cur >= self.entry_price + tp_dist * step2_pct:
                        new_sl = self.entry_price + tp_dist * step2_sl
                        if new_sl > self.stop_loss:
                            self.stop_loss = new_sl
                            self.dlog(f'STEP2 SL→{self.stop_loss:.2f}')
                else:
                    tp_dist = self.entry_price - self.take_profit
                    if tp_dist > 0 and cur <= self.entry_price - tp_dist * step2_pct:
                        new_sl = self.entry_price - tp_dist * step2_sl
                        if new_sl < self.stop_loss:
                            self.stop_loss = new_sl
                            self.dlog(f'STEP2 SL→{self.stop_loss:.2f}')

        # 时间止损
        if self.params.use_time_stop and self.params.max_bars > 0:
            bars_held = len(self) - self.entry_bar
            if bars_held >= self.params.max_bars:
                self.log(f'TIME_STOP {"Long" if is_long else "Short"} @ {cur:.2f} bars={bars_held}',
                        doprint=self.params.eventlog)
                self.order = self.close()
                return

        # 止损
        if is_long and self.stop_loss and cur <= self.stop_loss:
            self.log(f'STOP Long @ {cur:.2f} SL={self.stop_loss:.2f}',
                    doprint=self.params.eventlog)
            self.order = self.close()
            return
        elif not is_long and self.stop_loss and cur >= self.stop_loss:
            self.log(f'STOP Short @ {cur:.2f} SL={self.stop_loss:.2f}',
                    doprint=self.params.eventlog)
            self.order = self.close()
            return

        # 分批止盈：第一批在中轨平仓split_tp_ratio比例
        if (self.params.tp_method == 'split' and not self.partial_closed
                and self.take_profit is not None and self.entry_price is not None):
            h1_mid = self.h1_bb.lines.mid[0]
            if self.is_valid(h1_mid):
                ratio = self.params.split_tp_ratio
                if ratio > 0 and ratio < 1:
                    hit_mid = False
                    if is_long and cur >= h1_mid:
                        hit_mid = True
                    elif not is_long and cur <= h1_mid:
                        hit_mid = True
                    if hit_mid:
                        close_size = abs(pos.size) * ratio
                        if close_size > 0:
                            self.log(f'SPLIT_TP {"Long" if is_long else "Short"} '
                                    f'{ratio*100:.0f}% @ {cur:.2f} mid={h1_mid:.2f}',
                                    doprint=self.params.eventlog)
                            self.order = self.close(size=close_size)
                            self.partial_closed = True
                            # 剩余仓位的保本止损
                            self.stop_loss = self.entry_price
                            return

        # 固定止盈
        if self.take_profit is not None:
            if is_long and cur >= self.take_profit:
                self.log(f'TP Long @ {cur:.2f} TP={self.take_profit:.2f}',
                        doprint=self.params.eventlog)
                self.order = self.close()
                return
            elif not is_long and cur <= self.take_profit:
                self.log(f'TP Short @ {cur:.2f} TP={self.take_profit:.2f}',
                        doprint=self.params.eventlog)
                self.order = self.close()
                return

        # RSI动态止盈
        if self.params.tp_method == 'rsi':
            rsi = self.m15_rsi[0]
            if self.is_valid(rsi):
                if is_long and rsi > self.params.m15_rsi_short:
                    self.log(f'RSI_TP Long @ {cur:.2f} RSI={rsi:.1f}',
                            doprint=self.params.eventlog)
                    self.order = self.close()
                    return
                elif not is_long and rsi < self.params.m15_rsi_long:
                    self.log(f'RSI_TP Short @ {cur:.2f} RSI={rsi:.1f}',
                            doprint=self.params.eventlog)
                    self.order = self.close()
                    return

    # ========== 主循环 ==========

    def next(self):
        if self.order:
            return

        self._update_touch_tracking()

        # 持仓管理
        if abs(self.position.size) > 0:
            cur = self.data_15m.close[0]
            self._manage_position(self.position, cur)
            return

        if not self.ready():
            return

        # ===== 第一步：4H 震荡判断 =====
        score, is_osc = self._h4_oscillation_score()
        if not is_osc:
            return

        # ===== 第二步：1H 区间定位 =====
        zone_pos, zone_pct = self._h1_zone_position()

        # ===== 第三步：15M 入场 =====

        # --- 假突破做多 ---
        if self._check_fake_breakout_long():
            self._try_enter('up', ['FakeBreakout'], 'FakeBreakout', zone_pct)
            return

        # --- 假突破做空 ---
        if self._check_fake_breakout_short():
            self._try_enter('down', ['FakeBreakout'], 'FakeBreakout', zone_pct)
            return

        # --- 正常做多：1H接近支撑 + 15M信号 ---
        if zone_pos == 'lower':
            signals = self._m15_long_signal()
            if signals:
                self._try_enter('up', signals, '+'.join(signals), zone_pct)
                return

        # --- 正常做空：1H接近压力 + 15M信号 ---
        if zone_pos == 'upper':
            signals = self._m15_short_signal()
            if signals:
                self._try_enter('down', signals, '+'.join(signals), zone_pct)
                return

    def _try_enter(self, direction, signals, reason, zone_pct):
        """ML过滤后入场：提取特征→ML判断→决定是否入场"""
        # 提取特征
        features = self._extract_features(direction, signals, reason)

        # ML过滤
        if self.params.use_ml_filter and self._ml_filter is not None:
            passed, prob = self._ml_predict(features)
            if not passed:
                self.dlog(f'{direction.upper()} ML_SKIP prob={prob:.2f}')
                return
            self.dlog(f'{direction.upper()} ML_PASS prob={prob:.2f}')

        # 更新RR特征（在入场前先计算SL/TP）
        if direction == 'up':
            self._enter_long_with_features(reason, features, zone_pct)
        else:
            self._enter_short_with_features(reason, features, zone_pct)

    def _enter_long_with_features(self, reason, features, zone_pct):
        """做多入场（带ML特征更新）"""
        # 连亏过滤
        if self.params.use_consec_loss_filter and self.consec_losses >= self.params.max_consec_losses:
            self.dlog('LONG skipped: consec_losses')
            return
        # 1H RSI过滤
        if not self._check_h1_rsi('up'):
            self.dlog('LONG skipped: H1 RSI')
            return
        # 1H BB宽度过滤
        if not self._check_h1_bb_width():
            self.dlog('LONG skipped: H1 BB width')
            return
        # 4H趋势方向过滤
        if not self._check_h4_trend('up'):
            self.dlog('LONG skipped: H4 trend')
            return
        # 1H K线方向过滤
        if not self._check_h1_candle('up'):
            self.dlog('LONG skipped: H1 candle')
            return

        entry = self.data_15m.close[0]
        m15_bot = self.m15_bb.lines.bot[0]
        h1_bot = self.h1_bb.lines.bot[0]
        m15_atr = self.m15_atr[0]
        h1_atr = self.h1_atr[0]

        # 止损：根据sl_method选择锚点
        if self.params.sl_method == 'm15bb':
            if not self.is_valid(m15_atr):
                return
            self.stop_loss = m15_bot - self.params.sl_atr_offset * m15_atr
        else:
            if not self.is_valid(h1_atr):
                return
            self.stop_loss = h1_bot - self.params.sl_atr_offset * h1_atr
        sl_dist = entry - self.stop_loss

        if sl_dist <= 0 or not self.is_valid(sl_dist):
            return

        sz = self.calc_size(sl_dist)
        if sz <= 0:
            return

        max_sz = self.broker.getvalue() * self.params.leverage * self.params.max_leverage_ratio / entry
        sz = min(sz, max_sz)

        self.take_profit = self._calc_take_profit('up')

        tp_str = f'{self.take_profit:.2f}' if self.take_profit else 'RSI'
        tp_dist = (self.take_profit - entry) if self.take_profit and self.is_valid(self.take_profit) else 0
        rr = tp_dist / sl_dist if sl_dist > 0 and tp_dist > 0 else 0

        # R:R过滤
        if self.params.min_rr > 0 and rr < self.params.min_rr:
            self.dlog(f'LONG skipped: RR={rr:.1f} < {self.params.min_rr}')
            return

        # 保存特征（等notify_trade配对标签）
        if self.params.ml_collect_data:
            self._pending_entry_features = features.copy()

        self.entry_price = entry
        self.highest_profit = 0.0
        self.entry_bar = len(self)
        self.partial_closed = False
        self.log(f'→ LONG @ {entry:.2f} sz={sz:.4f} '
                f'SL={self.stop_loss:.2f}(dist={sl_dist:.2f}) TP={tp_str} RR={rr:.1f}:1 [{reason}]',
                doprint=self.params.eventlog)
        self.order = self.buy(size=sz)

    def _enter_short_with_features(self, reason, features, zone_pct):
        """做空入场（带ML特征更新）"""
        # 连亏过滤
        if self.params.use_consec_loss_filter and self.consec_losses >= self.params.max_consec_losses:
            self.dlog('SHORT skipped: consec_losses')
            return
        # 1H RSI过滤
        if not self._check_h1_rsi('down'):
            self.dlog('SHORT skipped: H1 RSI')
            return
        # 1H BB宽度过滤
        if not self._check_h1_bb_width():
            self.dlog('SHORT skipped: H1 BB width')
            return
        # 4H趋势方向过滤
        if not self._check_h4_trend('down'):
            self.dlog('SHORT skipped: H4 trend')
            return
        # 1H K线方向过滤
        if not self._check_h1_candle('down'):
            self.dlog('SHORT skipped: H1 candle')
            return

        entry = self.data_15m.close[0]
        m15_top = self.m15_bb.lines.top[0]
        h1_top = self.h1_bb.lines.top[0]
        m15_atr = self.m15_atr[0]
        h1_atr = self.h1_atr[0]

        if self.params.sl_method == 'm15bb':
            if not self.is_valid(m15_atr):
                return
            self.stop_loss = m15_top + self.params.sl_atr_offset * m15_atr
        else:
            if not self.is_valid(h1_atr):
                return
            self.stop_loss = h1_top + self.params.sl_atr_offset * h1_atr
        sl_dist = self.stop_loss - entry

        if sl_dist <= 0 or not self.is_valid(sl_dist):
            return

        sz = self.calc_size(sl_dist)
        if sz <= 0:
            return

        max_sz = self.broker.getvalue() * self.params.leverage * self.params.max_leverage_ratio / entry
        sz = min(sz, max_sz)

        self.take_profit = self._calc_take_profit('down')

        tp_str = f'{self.take_profit:.2f}' if self.take_profit else 'RSI'
        tp_dist = (entry - self.take_profit) if self.take_profit and self.is_valid(self.take_profit) else 0
        rr = tp_dist / sl_dist if sl_dist > 0 and tp_dist > 0 else 0

        # R:R过滤
        if self.params.min_rr > 0 and rr < self.params.min_rr:
            self.dlog(f'SHORT skipped: RR={rr:.1f} < {self.params.min_rr}')
            return

        # 保存特征
        if self.params.ml_collect_data:
            self._pending_entry_features = features.copy()

        self.entry_price = entry
        self.highest_profit = 0.0
        self.entry_bar = len(self)
        self.partial_closed = False
        self.log(f'→ SHORT @ {entry:.2f} sz={sz:.4f} '
                f'SL={self.stop_loss:.2f}(dist={sl_dist:.2f}) TP={tp_str} RR={rr:.1f}:1 [{reason}]',
                doprint=self.params.eventlog)
        self.order = self.sell(size=sz)

    def stop(self):
        if self.trade_count > 0:
            wr = self.wins / self.trade_count * 100
            self.log(f'交易: {self.trade_count} 胜率: {wr:.1f}%', doprint=True)
            self.dlog('SHORT skipped: H1 candle')
            return

        entry = self.data_15m.close[0]
        m15_top = self.m15_bb.lines.top[0]
        h1_top = self.h1_bb.lines.top[0]
        m15_atr = self.m15_atr[0]
        h1_atr = self.h1_atr[0]

        if self.params.sl_method == 'm15bb':
            if not self.is_valid(m15_atr):
                return
            self.stop_loss = m15_top + self.params.sl_atr_offset * m15_atr
        else:
            if not self.is_valid(h1_atr):
                return
            self.stop_loss = h1_top + self.params.sl_atr_offset * h1_atr
        sl_dist = self.stop_loss - entry

        if sl_dist <= 0 or not self.is_valid(sl_dist):
            return

        sz = self.calc_size(sl_dist)
        if sz <= 0:
            return

        max_sz = self.broker.getvalue() * self.params.leverage * self.params.max_leverage_ratio / entry
        sz = min(sz, max_sz)

        self.take_profit = self._calc_take_profit('down')

        tp_str = f'{self.take_profit:.2f}' if self.take_profit else 'RSI'
        tp_dist = (entry - self.take_profit) if self.take_profit and self.is_valid(self.take_profit) else 0
        rr = tp_dist / sl_dist if sl_dist > 0 and tp_dist > 0 else 0

        # R:R过滤
        if self.params.min_rr > 0 and rr < self.params.min_rr:
            self.dlog(f'SHORT skipped: RR={rr:.1f} < {self.params.min_rr}')
            return

        self.entry_price = entry
        self.highest_profit = 0.0
        self.entry_bar = len(self)
        self.partial_closed = False
        self.log(f'→ SHORT @ {entry:.2f} sz={sz:.4f} '
                f'SL={self.stop_loss:.2f}(dist={sl_dist:.2f}) TP={tp_str} RR={rr:.1f}:1 [{reason}]',
                doprint=self.params.eventlog)
        self.order = self.sell(size=sz)

    def stop(self):
        if self.trade_count > 0:
            wr = self.wins / self.trade_count * 100
            self.log(f'交易: {self.trade_count} 胜率: {wr:.1f}%', doprint=True)
