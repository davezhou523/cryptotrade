import backtrader as bt
import numpy as np
from trend.stochasticRSI import StochasticRSI


class MultiPeriodStrategy(bt.Strategy):
    """
    多周期交易策略：4H趋势判断 + 1H回调确认 + 15M入场触发
    基于趋势跟随和回调入场原则
    """

    params = (
        # 基础参数
        ('printlog', False),
        ('eventlog', True),
        
        # 4H周期参数
        ('h4_ema_fast', 21),   # 4H EMA21
        ('h4_ema_slow', 55),   # 4H EMA55
        ('h4_atr_period', 14), # 4H ATR周期
        ('h4_atr_ma_period', 20), # ATR移动平均周期
        
        # 1H周期参数
        ('h1_ema21', 21),      # 1H EMA21
        ('h1_ema55', 55),      # 1H EMA55
        ('h1_rsi_period', 14), # 1H RSI周期
        
        # 15M周期参数
        ('m15_atr_period', 14), # 15M ATR周期
        ('m15_rsi_period', 14), # 15M RSI周期
        ('m15_stoch_rsi_period', 14), # 15M Stoch RSI周期
        
        # 交易参数 - 优化版
        ('risk_per_trade', 0.015),  # 单笔风险1.5%（考虑杠杆）
        ('max_position_size', 0.30), # 最大仓位30%（为动态调整留空间）
        ('stop_loss_atr_multiplier', 1.8), # 止损ATR倍数优化
        ('atr_low_threshold', 0.7), # ATR低波动阈值优化
        ('atr_high_threshold', 1.3), # ATR高波动阈值优化
        
        # 杠杆参数
        ('leverage', 5.0),     # 5倍杠杆
        ('max_leverage_ratio', 0.8), # 最大杠杆使用率80%
        
        # 仓位管理优化参数
        ('min_position_size', 0.005), # 最小仓位0.5%
        ('position_size_growth', 1.1), # 仓位增长系数
        ('volatility_scaling', True), # 波动性仓位调整
        
        # 风险控制参数优化
        ('max_consecutive_losses', 2), # 当天最大连续亏损次数
        ('max_daily_loss_pct', 0.03), # 最大日亏损3%
        ('max_drawdown_pct', 0.08),   # 回撤分段阈值1：8%
        ('drawdown_tier2_pct', 0.12),  # 回撤分段阈值2：12%
        ('drawdown_tier3_pct', 0.16),  # 回撤分段阈值3：16%
        ('drawdown_scale_tier1', 0.7), # 8%~12% 仓位缩放
        ('drawdown_scale_tier2', 0.5), # 12%~16% 仓位缩放
        ('drawdown_scale_tier3', 0.3), # >=16% 仓位缩放
        ('drawdown_log_interval_bars', 96), # 回撤降仓日志限频（按15M bar，约1天）

        ('max_positions', 2),         # 最大同时持仓数优化

        
        # 动态参数
        ('dynamic_risk_adjustment', True), # 动态风险调整
        ('volatility_factor', 0.5),   # 波动性调整因子
        
        # 退出优化参数
        ('momentum_weak_threshold', 90), # StochRSI动能转弱阈值（提高阈值，减少过早退出）
        ('momentum_weak_confirm_bars', 3), # 动能转弱确认K线数（增加确认，减少噪音退出）
        ('min_holding_bars', 4),       # 最小持仓K线数（4根15M=1小时）
        ('trend_end_min_holding_bars', 8), # 趋势反转退出前最小持仓K线数
        ('trend_end_confirm_bars', 2), # 趋势反转确认K线数
        ('high_volatility_block_ratio', 2.4), # 超高波动过滤阈值（放宽）
        ('high_volatility_confirm_bars', 2), # 超高波动确认K线数（减少误杀）
        ('require_both_entry_signals', False), # 入场默认满足RSI或结构，提升触发率


    )

    def __init__(self):
        # 多周期数据
        self.data_4h = self.datas[0]
        self.data_1h = self.datas[1]
        self.data_15m = self.datas[2]
        
        # 交易状态
        self.order = None
        self.current_position = None
        self.entry_price = None
        self.entry_time = None
        self.entry_direction = None
        self.stop_loss = None
        self.take_profit = None
        self.stop_moved_to_cost = False  # 止损是否已移至成本
        self.partial_take_profit_done = False  # 2R是否已执行半仓止盈
        
        # 持仓状态追踪
        self.bars_since_entry = 0       # 入场后K线计数
        self.momentum_weak_count = 0    # 动能转弱确认计数
        self.trend_reversal_count = 0   # 趋势反转确认计数
        self.high_volatility_count = 0  # 超高波动确认计数

        
        # 风险控制
        self.consecutive_losses = 0
        self.daily_consecutive_losses = 0  # 当天连续亏损
        self.last_trade_date = None  # 上次平仓日期
        self.daily_loss = 0.0
        self.current_day = self.data_15m.datetime.date(0)
        self.daily_start_value = self.broker.getvalue()
        self.max_portfolio_value = self.broker.getvalue()
        self.active_positions = 0
        self.trade_count = 0
        self.win_count = 0
        self.drawdown_position_scale = 1.0
        self.drawdown_reduction_active = False
        self.last_drawdown_log_bar = -10**9


        
        # 4H指标
        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema55 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_slow)
        self.h4_atr = bt.indicators.ATR(self.data_4h, period=self.params.h4_atr_period)
        self.h4_atr_ma = bt.indicators.SMA(self.h4_atr, period=self.params.h4_atr_ma_period)
        
        # 1H指标
        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema21)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema55)
        self.h1_rsi = bt.indicators.RSI(self.data_1h.close, period=self.params.h1_rsi_period)
        
        # 15M指标
        self.m15_atr = bt.indicators.ATR(self.data_15m, period=self.params.m15_atr_period)
        self.m15_atr_ma = bt.indicators.SMA(self.m15_atr, period=20)  # 15M ATR移动平均
        self.m15_rsi = bt.indicators.RSI(self.data_15m.close, period=self.params.m15_rsi_period)
        self.m15_stoch_rsi = StochasticRSI(self.data_15m, period=self.params.m15_stoch_rsi_period)
        
        # 高低点跟踪
        self.h1_last_low = None
        self.h1_last_high = None
        self.m15_last_low = None
        self.m15_last_high = None
        
        # 日志初始化
        self.log('=== 多周期交易策略初始化完成 ===', force=True)
        self.log(f'风险控制: 单笔风险{self.params.risk_per_trade*100}%, 最大仓位{self.params.max_position_size*100}%', force=True)

    # 在D:\study\cryptotrade\trend\multi_period_strategy.py文件中修改log方法
    def log(self, txt, dt=None, force=False):
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_15m.datetime.datetime(0)
        log_string = f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}'
        
        # 确保使用正确的编码输出
        try:
            print(log_string)
        except UnicodeEncodeError:
            # 如果出现编码错误，替换无法编码的字符
            log_string = log_string.encode('gbk', 'replace').decode('gbk')
            print(log_string)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status == order.Completed:
            pos_size = self.getposition(self.data_15m).size
            self.active_positions = 1 if abs(pos_size) > 1e-8 else 0

            if self.current_position is None:
                # 入场成交（开仓）
                self.entry_direction = 'long' if order.isbuy() else 'short'
                self.current_position = self.entry_direction
                self.entry_price = order.executed.price
                self.entry_time = bt.num2date(order.executed.dt)
                self.bars_since_entry = 0
                self.momentum_weak_count = 0
                self.trend_reversal_count = 0
                self.stop_moved_to_cost = False
                self.partial_take_profit_done = False


                self.log(f'{"做多" if self.entry_direction == "long" else "做空"}入场: 价格{order.executed.price:.2f} 仓位{order.executed.size:.4f} 止损{self.stop_loss:.2f} 止盈{self.take_profit[1]:.2f}')
            else:
                # 平仓成交：区分半仓/全平
                if abs(pos_size) > 1e-8:
                    self.log(f'部分平仓成交: 价格{order.executed.price:.2f} 数量{order.executed.size:.4f} 剩余持仓{pos_size:.4f}')
                else:
                    trade_type = '做多平仓' if self.entry_direction == 'long' else '做空平仓'
                    self.log(f'{trade_type}: 平仓价格{order.executed.price:.2f} 数量{abs(order.executed.size):.4f}')

                    self.current_position = None
                    self.entry_price = None
                    self.entry_time = None
                    self.entry_direction = None
                    self.stop_loss = None
                    self.take_profit = None
                    self.bars_since_entry = 0
                    self.momentum_weak_count = 0
                    self.trend_reversal_count = 0
                    self.stop_moved_to_cost = False
                    self.partial_take_profit_done = False



        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/被拒绝', force=True)

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        trade_date = bt.num2date(trade.dtclose).date() if trade.dtclose else self.data_15m.datetime.date(0)
        if self.last_trade_date is not None and trade_date != self.last_trade_date:
            self.daily_consecutive_losses = 0

        self.trade_count += 1
        pnl = trade.pnlcomm
        pnl_pct = (pnl / trade.value * 100) if trade.value else 0

        if pnl > 0:
            self.win_count += 1
            self.consecutive_losses = 0
            self.daily_consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.daily_consecutive_losses += 1

        self.last_trade_date = trade_date
        win_rate = self.win_count / self.trade_count * 100 if self.trade_count > 0 else 0
        self.log(
            f'交易关闭: 净盈亏{pnl:.2f}({pnl_pct:.2f}%) '
            f'累计{self.trade_count}笔 胜率{win_rate:.2f}% 当日连亏{self.daily_consecutive_losses}',
            force=True
        )

    def get_trend_direction(self):

        """4H趋势方向判断"""
        if len(self.data_4h) < max(self.params.h4_ema_slow, 5):
            return None
        
        if self.h4_ema21[0] > self.h4_ema55[0]:
            return 'bullish'
        elif self.h4_ema21[0] < self.h4_ema55[0]:
            return 'bearish'
        else:
            return 'sideways'

    def atr_volatility_check(self):
        """4H ATR波动性检查"""
        if len(self.data_4h) < self.params.h4_atr_ma_period:
            return False

        current_atr = self.h4_atr[0]
        atr_avg = self.h4_atr_ma[0]
        if current_atr < atr_avg * self.params.atr_low_threshold:
            self.log(f'低波动过滤: ATR{current_atr:.4f} < {atr_avg * self.params.atr_low_threshold:.4f}')
            return False
        return True

    def check_pullback_condition(self, trend_direction):
        """1H回调条件检查"""
        if len(self.data_1h) < max(self.params.h1_ema55, 5):
            return False
        
        current_price = self.data_1h.close[0]
        
        if trend_direction == 'bullish':
            # 多头回调：价格回踩EMA21，RSI在40-50区间
            return (
                current_price <= self.h1_ema21[0] * 1.005 and 
                current_price >= self.h1_ema55[0] and
                self.h1_rsi[0] >= 40 and self.h1_rsi[0] <= 50 and
                self.h1_rsi[0] > self.h1_rsi[-1]  # RSI上拐
            )
        elif trend_direction == 'bearish':
            # 空头回调：价格反弹EMA21，RSI在50-60区间
            return (
                current_price >= self.h1_ema21[0] * 0.995 and 
                current_price <= self.h1_ema55[0] and
                self.h1_rsi[0] >= 50 and self.h1_rsi[0] <= 60 and
                self.h1_rsi[0] < self.h1_rsi[-1]  # RSI下拐
            )
        
        return False

    def check_entry_signal(self, trend_direction):
        """15M入场信号检查"""
        if len(self.data_15m) < 5:
            return False
        
        if trend_direction == 'bullish':
            rsi_condition = self.m15_rsi[0] > 50 and self.m15_rsi[-1] <= 50
            structure_condition = self.m15_last_high is not None and self.data_15m.close[0] > self.m15_last_high
            
            if self.params.require_both_entry_signals:
                return rsi_condition and structure_condition
            return rsi_condition or structure_condition
            
        elif trend_direction == 'bearish':
            rsi_condition = self.m15_rsi[0] < 50 and self.m15_rsi[-1] >= 50
            structure_condition = self.m15_last_low is not None and self.data_15m.close[0] < self.m15_last_low
            
            if self.params.require_both_entry_signals:
                return rsi_condition and structure_condition
            return rsi_condition or structure_condition
        
        return False

    def update_high_low_levels(self):
        """更新高低点水平（结构位不包含当前K线）"""
        # 更新1H高低点（仅用于观察）
        if len(self.data_1h) >= 20:
            self.h1_last_low = min(self.data_1h.low.get(size=20))
            self.h1_last_high = max(self.data_1h.high.get(size=20))
        
        # 更新15M结构高低点（使用前10根已完成K线）
        if len(self.data_15m) >= 11:
            recent_lows = list(self.data_15m.low.get(size=11))
            recent_highs = list(self.data_15m.high.get(size=11))
            self.m15_last_low = min(recent_lows[:-1])
            self.m15_last_high = max(recent_highs[:-1])


    def risk_management_check(self):
        """风险控制检查 - 优化版（支持杠杆）"""
        current_value = self.broker.getvalue()
        
        # 杠杆风险检查
        total_position_value = 0
        for data in self.datas:
            pos = self.getposition(data)
            if pos.size != 0:
                total_position_value += abs(pos.size) * data.close[0]
        
        leverage_ratio = total_position_value / current_value if current_value > 0 else 0
        max_allowed_leverage = self.params.leverage * self.params.max_leverage_ratio
        
        if leverage_ratio > max_allowed_leverage:
            self.log(f'❌ 杠杆超限: 当前{leverage_ratio:.1f}x > 最大{max_allowed_leverage:.1f}x', force=True)
            return False
        
        # 当天连续亏损检查
        if self.daily_consecutive_losses >= self.params.max_consecutive_losses:
            return False
        
        # 日亏损检查
        if hasattr(self, 'daily_start_value'):
            daily_loss = (self.daily_start_value - current_value) / self.daily_start_value
            if daily_loss >= self.params.max_daily_loss_pct:
                self.log(f'❌ 日亏损{daily_loss*100:.1f}%，暂停交易', force=True)
                return False
        
        # 最大回撤检查：不硬停机，改为分段降仓交易
        if current_value > self.max_portfolio_value:
            self.max_portfolio_value = current_value

        drawdown_pct = (self.max_portfolio_value - current_value) / self.max_portfolio_value

        if drawdown_pct >= self.params.drawdown_tier3_pct:
            self.drawdown_position_scale = self.params.drawdown_scale_tier3
        elif drawdown_pct >= self.params.drawdown_tier2_pct:
            self.drawdown_position_scale = self.params.drawdown_scale_tier2
        elif drawdown_pct >= self.params.max_drawdown_pct:
            self.drawdown_position_scale = self.params.drawdown_scale_tier1
        else:
            self.drawdown_position_scale = 1.0

        drawdown_active = self.drawdown_position_scale < 1.0
        current_bar = len(self.data_15m)
        if drawdown_active:
            if (not self.drawdown_reduction_active) or (current_bar - self.last_drawdown_log_bar >= self.params.drawdown_log_interval_bars):
                self.log(
                    f'⚠️ 最大回撤{drawdown_pct*100:.1f}% 触发分段降仓，开仓仓位x{self.drawdown_position_scale:.2f}',
                    force=True
                )
                self.last_drawdown_log_bar = current_bar
            self.drawdown_reduction_active = True
        else:
            if self.drawdown_reduction_active:
                self.log('✅ 回撤恢复到阈值内，仓位恢复正常', force=True)
            self.drawdown_reduction_active = False


        
        # 同时持仓数检查（按真实持仓）
        position_count = 1 if abs(self.getposition(self.data_15m).size) > 1e-8 else 0
        if position_count >= self.params.max_positions:
            self.log(f'❌ 同时持仓{position_count}单，已达上限', force=True)
            return False

        
        # 波动性风险检查（放宽阈值 + 连续确认，减少误杀）
        if self.params.volatility_scaling:
            current_atr = self.m15_atr[0]
            atr_avg = self.m15_atr_ma[0] if len(self.m15_atr_ma) > 0 else current_atr
            atr_ratio = current_atr / atr_avg if atr_avg > 0 else 1.0

            if atr_ratio > self.params.high_volatility_block_ratio:
                self.high_volatility_count += 1
                if self.high_volatility_count >= self.params.high_volatility_confirm_bars:
                    self.log(
                        f'⚠️ 高波动风险: ATR比率{atr_ratio:.2f} 连续{self.high_volatility_count}根 > {self.params.high_volatility_block_ratio:.2f}',
                        force=True
                    )
                    return False
            else:
                self.high_volatility_count = 0

        
        #self.log(f'✅ 风险检查通过: 杠杆{leverage_ratio:.1f}x, 持仓{self.active_positions}单')
        return True

    def calculate_position_size(self):
        """计算仓位大小：风险仓位 + 杠杆上限 + 现金仓位上限"""
        current_price = self.data_15m.close[0]
        equity = self.broker.getvalue()

        if current_price <= 0 or equity <= 0:
            return 0

        stop_distance = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if stop_distance <= 0:
            return 0

        # 风险仓位（核心）
        risk_amount = equity * self.params.risk_per_trade
        risk_size = risk_amount / stop_distance

        # 波动性调整
        volatility_factor = 1.0
        if self.params.volatility_scaling:
            atr_ratio = self.m15_atr[0] / self.m15_atr_ma[0] if self.m15_atr_ma[0] > 0 else 1.0
            volatility_factor = max(0.5, min(2.0, 1.0 + (atr_ratio - 1.0) * self.params.volatility_factor))

        adjusted_size = risk_size * volatility_factor

        # 动态风险调整
        if self.params.dynamic_risk_adjustment:
            if self.consecutive_losses > 0:
                adjusted_size *= 0.8 ** self.consecutive_losses
            elif self.win_count > 0 and self.trade_count > 0:
                win_rate = self.win_count / self.trade_count
                if win_rate > 0.6:
                    adjusted_size *= min(1.0 + (win_rate - 0.6) * 0.5, 1.2)

        # 最大回撤触发后的降仓（由risk_management_check更新）
        adjusted_size *= self.drawdown_position_scale

        # 名义仓位上限（杠杆约束）
        leverage_notional_limit = equity * self.params.leverage * self.params.max_leverage_ratio
        leverage_size_cap = leverage_notional_limit / current_price

        # 杠杆联动仓位上限：避免长期固定30%封顶（随回撤缩放）
        linked_notional_limit = equity * self.params.max_position_size * self.params.leverage * self.params.max_leverage_ratio
        linked_notional_limit *= self.drawdown_position_scale
        linked_size_cap = linked_notional_limit / current_price


        min_size = equity * self.params.min_position_size / current_price
        final_size = max(min_size, min(adjusted_size, leverage_size_cap, linked_size_cap))

        notional_pct = final_size * current_price / equity * 100
        self.log(
            f'仓位计算: 风险仓位{risk_size:.6f} 波动{volatility_factor:.3f} 回撤缩放x{self.drawdown_position_scale:.2f} '
            f'杠杆上限{leverage_size_cap:.6f} 联动上限{linked_size_cap:.6f} '
            f'最终{final_size:.6f} 占比{notional_pct:.2f}%'
        )

        return final_size


    def set_stop_loss_take_profit(self, direction, entry_price):
        """设置止损止盈"""
        atr_value = self.m15_atr[0]
        
        if direction == 'long':
            self.stop_loss = entry_price - atr_value * self.params.stop_loss_atr_multiplier
            # 止盈目标：1R和2R
            self.take_profit = [
                entry_price + atr_value * self.params.stop_loss_atr_multiplier,  # 1R
                entry_price + atr_value * self.params.stop_loss_atr_multiplier * 2  # 2R
            ]
        else:
            self.stop_loss = entry_price + atr_value * self.params.stop_loss_atr_multiplier
            self.take_profit = [
                entry_price - atr_value * self.params.stop_loss_atr_multiplier,  # 1R
                entry_price - atr_value * self.params.stop_loss_atr_multiplier * 2  # 2R
            ]

    def check_exit_conditions(self):
        """检查退出条件"""
        position_size = self.getposition(self.data_15m).size
        if self.current_position is None or abs(position_size) <= 1e-8:
            return None

        self.bars_since_entry += 1
        current_price = self.data_15m.close[0]
        min_holding = self.params.min_holding_bars

        if self.entry_direction == 'long':
            if current_price <= self.stop_loss:
                self.log(f'止损触发: {self.entry_direction} 入场{self.entry_price:.2f} 止损{self.stop_loss:.2f} 亏损{self.entry_price - current_price:.2f}')
                return 'stop_loss'

            if current_price >= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log(f'1R止盈: {self.entry_direction} 止损移至成本{self.stop_loss:.2f}')

            if (current_price >= self.take_profit[1]) and (not self.partial_take_profit_done):
                self.partial_take_profit_done = True
                self.log(f'2R触发半仓止盈: {self.entry_direction} 盈利{current_price - self.entry_price:.2f}')
                return 'take_profit_partial'

            if self.data_4h.close[0] < self.h4_ema21[0]:
                self.trend_reversal_count += 1
                if self.bars_since_entry >= self.params.trend_end_min_holding_bars and self.trend_reversal_count >= self.params.trend_end_confirm_bars:
                    self.log(
                        f'趋势结束: {self.entry_direction} 4H收盘{self.data_4h.close[0]:.2f} < EMA21{self.h4_ema21[0]:.2f} '
                        f'确认{self.trend_reversal_count}根'
                    )
                    return 'trend_end'
            else:
                self.trend_reversal_count = 0


            if self.bars_since_entry >= min_holding:
                k_now = self.m15_stoch_rsi.percK[0]
                k_prev = self.m15_stoch_rsi.percK[-1]
                if k_now > self.params.momentum_weak_threshold and k_now < k_prev:
                    self.momentum_weak_count += 1
                    if self.momentum_weak_count >= self.params.momentum_weak_confirm_bars:
                        self.log(f'动能转弱: {self.entry_direction} StochRSI{k_now:.2f}回落 确认{self.momentum_weak_count}根')
                        return 'momentum_weak'
                else:
                    self.momentum_weak_count = 0

        else:
            if current_price >= self.stop_loss:
                self.log(f'止损触发: {self.entry_direction} 入场{self.entry_price:.2f} 止损{self.stop_loss:.2f} 亏损{current_price - self.entry_price:.2f}')
                return 'stop_loss'

            if current_price <= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log(f'1R止盈: {self.entry_direction} 止损移至成本{self.stop_loss:.2f}')

            if (current_price <= self.take_profit[1]) and (not self.partial_take_profit_done):
                self.partial_take_profit_done = True
                self.log(f'2R触发半仓止盈: {self.entry_direction} 盈利{self.entry_price - current_price:.2f}')
                return 'take_profit_partial'

            if self.data_4h.close[0] > self.h4_ema21[0]:
                self.trend_reversal_count += 1
                if self.bars_since_entry >= self.params.trend_end_min_holding_bars and self.trend_reversal_count >= self.params.trend_end_confirm_bars:
                    self.log(
                        f'趋势结束: {self.entry_direction} 4H收盘{self.data_4h.close[0]:.2f} > EMA21{self.h4_ema21[0]:.2f} '
                        f'确认{self.trend_reversal_count}根'
                    )
                    return 'trend_end'
            else:
                self.trend_reversal_count = 0


            low_threshold = 100 - self.params.momentum_weak_threshold
            if self.bars_since_entry >= min_holding:
                k_now = self.m15_stoch_rsi.percK[0]
                k_prev = self.m15_stoch_rsi.percK[-1]
                if k_now < low_threshold and k_now > k_prev:
                    self.momentum_weak_count += 1
                    if self.momentum_weak_count >= self.params.momentum_weak_confirm_bars:
                        self.log(f'动能转弱: {self.entry_direction} StochRSI{k_now:.2f}反弹 确认{self.momentum_weak_count}根')
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

        self.update_high_low_levels()

        if self.order:
            return

        # 先管理已有仓位，避免风控拦截导致无法止损/止盈
        exit_reason = self.check_exit_conditions()
        if exit_reason:
            self.log(f'触发退出: {exit_reason}')
            if exit_reason == 'take_profit_partial':
                pos_size = self.getposition(self.data_15m).size
                half_size = abs(pos_size) / 2
                if half_size > 0:
                    if pos_size > 0:
                        self.order = self.sell(data=self.data_15m, size=half_size)
                    else:
                        self.order = self.buy(data=self.data_15m, size=half_size)
                else:
                    self.order = self.close(data=self.data_15m)
            else:
                self.order = self.close(data=self.data_15m)
            return

        if self.current_position:
            return

        # 仅限制新开仓
        if not self.risk_management_check():
            return

        trend_direction = self.get_trend_direction()
        if trend_direction is None or trend_direction == 'sideways':
            return

        if not self.atr_volatility_check():
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
        """策略结束时的统计"""
        if self.trade_count > 0:
            win_rate = self.win_count / self.trade_count * 100
            self.log(f'策略结束统计: 交易次数{self.trade_count}, 胜率{win_rate:.1f}%', force=True)