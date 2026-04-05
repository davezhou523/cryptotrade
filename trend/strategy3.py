import backtrader as bt
#
# ① 4H判断趋势
#    ├── 价格> EMA21 > EMA55 → 只做多
#    ├── 价格< EMA21 < EMA55 → 只做空
#    └── EMA缠绕 → 等待（不交易）
# ② 1H判断位置（是否回调到位）
#    ├── 多头：价格回踩 EMA21/EMA55 → 进入观察区
#    ├── 空头：价格反弹 EMA21/EMA55 → 进入观察区
#    └── 未到均线 → 等待
# ③ 15M判断入场（触发信号）
#    ├── 做多：
#    │     RSI上破50 + 突破小结构 → BUY
#    │
#    ├── 做空：
#    │     RSI下破50 + 跌破小结构 → SELL
#    │
#    └── 无信号 → 继续等待
#
# ④ 风控执行
#    ├── 止损 = 2×ATR（15M）
#    ├── 单笔风险 ≤ 2%
#    └── 仓位自动计算
#
# ⑤ 持仓管理
#    ├── +1R → 保本
#    ├── +2R → 止盈一半
#    └── EMA21破位 → 全部止盈
#
# ⑥ 退出 → 回到等待
# 价格 > EMA21 > EMA55 ≠ 买点 真正的买点在这里：回调 + 小周期确认
#
# 二、EMA结构 → 操作决策总表（核心）
# 做多结构判断
# | (1小时)EMA结构              | 价格位置 | 含义   | 操作        |
# | ------------------ | ---- | ---- | --------- |
# | 价格 > EMA21 > EMA55 | 强趋势  | 上涨中  | ❌ 不追（等回调） |
# | EMA21 > 价格 > EMA55 | 回调中  | 健康回调 | ✅ 准备做多    |
# | 价格 ≈ EMA55         | 深回调  | 风险区  | ⚠️ 轻仓或放弃  |
# | 价格 < EMA55         | 结构破坏 | 可能反转 | ❌ 不做多     |
#
# 做空结构判断
# |(1小时) EMA结构              | 价格位置 | 含义   | 操作     |
# | ------------------ | ---- | ---- | ------ |
# | 价格 < EMA21 < EMA55 | 强趋势  | 下跌中  | ❌ 不追空  |
# | EMA21 < 价格 < EMA55 | 反弹中  | 健康回调 | ✅ 准备做空 |
# | 价格 ≈ EMA55         | 深反弹  | 风险区  | ⚠️ 轻仓  |
# | 价格 > EMA55         | 结构破坏 | 可能反转 | ❌ 不做空  |
#
# 三、回调 vs 反转判断（关键补充）
# | 类型   | 1小时EMA关系         | 结构   | RSI    | 结论     |
# | ---- | ------------- | ---- | ------ | ------ |
# | 多头回调 | EMA21 > EMA55 | 未破前低 | RSI≈50 | ✅ 做多   |
# | 多头反转 | EMA21走平/下拐    | 破前低  | RSI<40 | ❌ 停止做多 |
# | 空头回调 | EMA21 < EMA55 | 未破前高 | RSI≈60 | ✅ 做空   |
# | 空头反转 | EMA21上拐       | 破前高  | RSI>60 | ❌ 停止做空 |

class Strategy3(bt.Strategy):
    """策略3：4H趋势 + 1H回调 + 15M确认"""

    params = (
        # 日志控制
        ('printlog', False),                 # 是否打印普通日志（每笔交易等）
        ('eventlog', True),                  # 是否打印重要事件日志（入场、出场、风控触发等）

        # 周期参数 - 各时间周期的指标参数
        ('h4_ema_fast', 21),                # 4小时图快速EMA周期
        ('h4_ema_slow', 55),                # 4小时图慢速EMA周期
        ('h1_ema_fast', 21),                # 1小时图快速EMA周期
        ('h1_ema_slow', 55),                # 1小时图慢速EMA周期
        ('h1_rsi_period', 14),              # 1小时图RSI周期
        ('m15_ema_period', 21),             # 15分钟图EMA周期（用于出场判断）
        ('m15_atr_period', 14),             # 15分钟图ATR周期（用于止损和仓位计算）
        ('m15_rsi_period', 14),             # 15分钟图RSI周期（用于入场信号）

        # 风控与仓位 - 风险管理和仓位大小计算
        ('risk_per_trade', 0.016),          # 单笔风险 <=1.5%（可动态调整，最大2%）
        ('max_position_size', 0.3),        # 最大仓位规模（占总资金比例），小幅提升资金利用率
        ('deep_pullback_scale', 0.6),       # 深回调轻仓系数，价格接近EMA55时仓位打6折
        ('pullback_deep_band', 0.003),      # 贴近EMA55判定带（0.3%），价格与EMA55距离小于此值视为深回调
        ('stop_loss_atr_multiplier', 2.0),  # 止损距离=2×ATR
        ('min_holding_bars', 4),            # 最小持仓K线数，避免刚入场就被EMA噪音洗出
        ('ema_exit_confirm_bars', 2),       # EMA破位连续确认K线数，需连续2根K线确认破位
        ('ema_exit_buffer_atr', 0.2),       # EMA破位缓冲带（ATR倍数），提供一定容错空间

        # 杠杆约束 - 保证金交易参数
        ('leverage', 5.0),                  # 杠杆倍数，5倍杠杆
        ('max_leverage_ratio', 0.9),       # 最大杠杆使用率，不超过保证金的85%

        # 风险限制 - 全局风险控制
        ('max_positions', 1),               # 最大同时持仓数，只允许单笔交易
        ('max_consecutive_losses', 3),      # 最大连续亏损次数，达到后暂停交易
        ('max_daily_loss_pct', 0.05),       # 最大日亏损比例（5%），达到后当日停止交易
        ('max_drawdown_pct', 0.10),         # 最大回撤比例（10%），达到后仓位规模减半
        ('drawdown_position_scale', 0.5),   # 回撤仓位缩放系数，回撤达到阈值时仓位打5折

        # 过滤 - 信号过滤条件
        ('require_both_entry_signals', False), # 是否需要同时满足结构突破和RSI信号
        ('h1_rsi_long_low', 42),            # 1小时图多头RSI下限，RSI>42才考虑做多
        ('h1_rsi_long_high', 60),           # 1小时图多头RSI上限，RSI<60才考虑做多
        ('h1_rsi_short_low', 40),           # 1小时图空头RSI下限，RSI>40才考虑做空
        ('h1_rsi_short_high', 58),          # 1小时图空头RSI上限，RSI<58才考虑做空
        ('m15_breakout_lookback', 6),       # 15分钟图突破结构回顾期（K线数）
        ('m15_rsi_bias_long', 52),          # 15分钟图多头RSI偏置，RSI>=52视为偏多
        ('m15_rsi_bias_short', 48),         # 15分钟图空头RSI偏置，RSI<=48视为偏空

        # 兼容测试脚本参数
        ('volatility_scaling', True),       # 波动率缩放，根据市场波动调整仓位
        ('dynamic_risk_adjustment', True),  # 动态风险调整，根据回撤调整仓位规模
    )

    def __init__(self):
        """
        策略初始化方法
        
        功能:
            1. 设置多时间周期数据引用（4H/1H/15M）
            2. 初始化各周期技术指标（EMA、ATR、RSI）
            3. 定义订单和仓位状态变量
            4. 初始化交易统计和风险管理变量
            5. 记录初始化完成日志
        """
        # 多时间周期数据引用
        self.data_4h = self.datas[0]   # 4小时图，用于判断趋势方向
        self.data_1h = self.datas[1]   # 1小时图，用于判断回调位置
        self.data_15m = self.datas[2]  # 15分钟图，用于入场信号和仓位管理

        # 4小时图指标：EMA21和EMA55用于趋势判断
        self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_fast)
        self.h4_ema55 = bt.indicators.EMA(self.data_4h.close, period=self.params.h4_ema_slow)

        self.h1_ema21 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_fast)
        self.h1_ema55 = bt.indicators.EMA(self.data_1h.close, period=self.params.h1_ema_slow)
        self.h1_rsi = bt.indicators.RSI(self.data_1h.close, period=self.params.h1_rsi_period)

        self.m15_ema21 = bt.indicators.EMA(self.data_15m.close, period=self.params.m15_ema_period)
        self.m15_atr = bt.indicators.ATR(self.data_15m, period=self.params.m15_atr_period)
        self.m15_rsi = bt.indicators.RSI(self.data_15m.close, period=self.params.m15_rsi_period)

        # 订单和仓位状态变量
        self.order = None                    # 当前活跃订单
        self.current_position = None         # 当前持仓方向（'long'/'short'/None）
        self.entry_direction = None          # 入场方向（'long'/'short'）
        self.entry_price = None              # 入场价格
        self.entry_time = None               # 入场时间
        self.stop_loss = None                # 止损价格
        self.take_profit = None              # 止盈价格（可能包含多个止盈位）
        self.stop_moved_to_cost = False      # 止损是否已移动到成本价
        self.partial_take_profit_done = False # 是否已执行部分止盈

        # 价格结构跟踪变量
        self.m15_last_high = None           # 15分钟图最近高点（用于突破判断）
        self.m15_last_low = None            # 15分钟图最近低点（用于突破判断）
        self.h1_last_high = None            # 1小时图最近高点（用于回调判断）
        self.h1_last_low = None             # 1小时图最近低点（用于回调判断）
        self.pullback_scale = 1.0           # 回调仓位缩放系数（深回调时减小仓位）

        # 交易统计和风险管理变量
        self.trade_count = 0                # 总交易次数
        self.win_count = 0                  # 盈利交易次数
        self.consecutive_losses = 0         # 连续亏损次数
        self.daily_consecutive_losses = 0   # 当日连续亏损次数

        # 日级别和回撤管理变量
        self.current_day = self.data_15m.datetime.date(0)  # 当前交易日
        self.daily_start_value = self.broker.getvalue()    # 当日开始时的资金
        self.max_portfolio_value = self.broker.getvalue()  # 投资组合历史最高价值
        self.drawdown_position_scale = 1.0  # 回撤仓位缩放系数（回撤大时减小仓位）
        self.bars_since_entry = 0           # 自入场以来的K线数
        self.ema_break_count = 0            # EMA破位连续计数（用于出场确认）
        self.pending_entry_context = None
        self.signal_price = None            # 信号触发时的15分钟收盘价

        self.log('=== Strategy3 初始化完成 ===', force=True)

    def log(self, txt, dt=None, force=False):
        """
        日志记录方法
        
        参数:
            txt (str): 日志文本
            dt (datetime, optional): 日志时间，默认为当前15分钟K线时间
            force (bool): 强制记录（即使printlog为False，只要eventlog为True）
            
        功能:
            根据printlog和eventlog参数控制日志输出
            时间格式：YYYY-MM-DD HH:MM:SS
        """
        if not (self.params.printlog or (force and self.params.eventlog)):
            return
        dt = dt or self.data_15m.datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def build_entry_context(self, trend_direction, size):
        """
        构建入场决策上下文信息字典
        
        参数:
            trend_direction (str): 4小时图趋势方向（'bullish'/'bearish'）
            size (float): 计算出的最终仓位大小
            
        返回:
            dict: 包含入场决策所需的所有上下文信息的字典
            
        功能:
            1. 收集当前价格、ATR止损距离、账户权益等基础数据
            2. 计算基于风险的仓位大小（考虑现金限制、杠杆限制）
            3. 获取15分钟图突破结构的高低点
            4. 根据趋势方向计算结构触发、RSI触发、RSI偏置条件
            5. 计算止损和两个止盈价位（1R和2R）
            6. 返回包含所有相关指标、信号和计算结果的完整上下文字典
        """
        signal_price = self.data_15m.close[0]
        stop_distance = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        equity = self.broker.getvalue()
        risk_pct = min(self.params.risk_per_trade, 0.03)
        risk_amount = equity * risk_pct
        risk_size = risk_amount / stop_distance if stop_distance > 0 else 0
        cash_cap = (equity * self.params.max_position_size) / signal_price if signal_price > 0 else 0
        lev_cap = (equity * self.params.leverage * self.params.max_leverage_ratio) / signal_price if signal_price > 0 else 0
        base_size = min(risk_size, cash_cap, lev_cap) if signal_price > 0 else 0
        lookback = self.params.m15_breakout_lookback
        highs = list(self.data_15m.high.get(size=lookback + 1))
        lows = list(self.data_15m.low.get(size=lookback + 1))
        recent_high = max(highs[:-1])
        recent_low = min(lows[:-1])
        rsi_now = self.m15_rsi[0]
        rsi_prev = self.m15_rsi[-1]

        if trend_direction == 'bullish':
            structure_trigger = signal_price > recent_high
            rsi_trigger = rsi_now > 50 and rsi_prev <= 50
            rsi_bias_ok = rsi_now >= self.params.m15_rsi_bias_long
            stop_loss = signal_price - stop_distance
            take_profit_1 = signal_price + stop_distance
            take_profit_2 = signal_price + 2 * stop_distance
        else:
            structure_trigger = signal_price < recent_low
            rsi_trigger = rsi_now < 50 and rsi_prev >= 50
            rsi_bias_ok = rsi_now <= self.params.m15_rsi_bias_short
            stop_loss = signal_price + stop_distance
            take_profit_1 = signal_price - stop_distance
            take_profit_2 = signal_price - 2 * stop_distance

        return {
            'trend_direction': trend_direction,
            'signal_price': signal_price,
            'stop_distance': stop_distance,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'equity': equity,
            'risk_pct': risk_pct,
            'risk_amount': risk_amount,
            'risk_size': risk_size,
            'cash_cap': cash_cap,
            'lev_cap': lev_cap,
            'base_size': base_size,
            'final_size': size,
            'pullback_scale': self.pullback_scale,
            'drawdown_scale': self.drawdown_position_scale,
            'h4_price': self.data_4h.close[0],
            'h4_ema21': self.h4_ema21[0],
            'h4_ema55': self.h4_ema55[0],
            'h1_price': self.data_1h.close[0],
            'h1_ema21': self.h1_ema21[0],
            'h1_ema55': self.h1_ema55[0],
            'h1_rsi': self.h1_rsi[0],
            'm15_price': signal_price,
            'm15_rsi': rsi_now,
            'm15_rsi_prev': rsi_prev,
            'recent_high': recent_high,
            'recent_low': recent_low,
            'structure_trigger': structure_trigger,
            'rsi_trigger': rsi_trigger,
            'rsi_bias_ok': rsi_bias_ok,
            'entry_mode': 'AND' if self.params.require_both_entry_signals else 'OR',
            'lookback': lookback,
        }

    def log_entry_context(self, context):
        """
        记录入场上下文详细信息日志
        
        参数:
            context (dict): 由build_entry_context构建的入场决策上下文字典
            
        功能:
            1. 输出入场理由：展示4H/1H/15M三个周期的价格、EMA、RSI等关键指标
            2. 输出仓位计算：展示权益、风险比例、风险金额、各种仓位限制和缩放系数
            3. 输出目标计算：展示信号价、止损价、两个止盈价的计算结果
            
        日志级别:
            强制日志（force=True），即使printlog为False也会输出
        """
        direction_text = '多头' if context['trend_direction'] == 'bullish' else '空头'
        self.log(
            f'{direction_text}入场理由: '
            f'4H价格{context["h4_price"]:.2f}/EMA21 {context["h4_ema21"]:.2f}/EMA55 {context["h4_ema55"]:.2f}; '
            f'1H价格{context["h1_price"]:.2f}/EMA21 {context["h1_ema21"]:.2f}/EMA55 {context["h1_ema55"]:.2f}/RSI {context["h1_rsi"]:.2f}; '
            f'15M价格{context["m15_price"]:.2f}/最近高{context["recent_high"]:.2f}/最近低{context["recent_low"]:.2f}/'
            f'RSI前值{context["m15_rsi_prev"]:.2f}/当前{context["m15_rsi"]:.2f}; '
            f'结构触发={context["structure_trigger"]} RSI穿越={context["rsi_trigger"]} RSI偏置={context["rsi_bias_ok"]} '
            f'组合模式={context["entry_mode"]}',
            force=True
        )
        self.log(
            f'{direction_text}仓位计算公式:',
            force=True
        )
        self.log(
            f'  权益 = {context["equity"]:.2f}',
            force=True
        )
        self.log(
            f'  风险比例 = min(params.risk_per_trade, 0.03) = {context["risk_pct"]*100:.2f}%',
            force=True
        )
        self.log(
            f'  风险金额 = 权益 × 风险比例 = {context["equity"]:.2f} × {context["risk_pct"]:.4f} = {context["risk_amount"]:.2f}',
            force=True
        )
        self.log(
            f'  ATR止损距离 = m15_atr × params.stop_loss_atr_multiplier = {context["stop_distance"]/self.params.stop_loss_atr_multiplier:.2f} × {self.params.stop_loss_atr_multiplier} = {context["stop_distance"]:.2f}',
            force=True
        )
        self.log(
            f'  风险仓位 = 风险金额 ÷ ATR止损距离 = {context["risk_amount"]:.2f} ÷ {context["stop_distance"]:.2f} = {context["risk_size"]:.4f}',
            force=True
        )
        self.log(
            f'  现金上限 = (权益 × params.max_position_size) ÷ 信号价 = ({context["equity"]:.2f} × {self.params.max_position_size}) ÷ {context["signal_price"]:.2f} = {context["cash_cap"]:.4f}',
            force=True
        )
        self.log(
            f'  杠杆上限 = (权益 × params.leverage × params.max_leverage_ratio) ÷ 信号价 = ({context["equity"]:.2f} × {self.params.leverage} × {self.params.max_leverage_ratio}) ÷ {context["signal_price"]:.2f} = {context["lev_cap"]:.4f}',
            force=True
        )
        self.log(
            f'  基础仓位 = min(风险仓位, 现金上限, 杠杆上限) = min({context["risk_size"]:.4f}, {context["cash_cap"]:.4f}, {context["lev_cap"]:.4f}) = {context["base_size"]:.4f}',
            force=True
        )
        self.log(
            f'  回撤缩放 = {context["drawdown_scale"]:.2f}',
            force=True
        )
        self.log(
            f'  回调缩放 = {context["pullback_scale"]:.2f}',
            force=True
        )
        self.log(
            f'  最终仓位 = 基础仓位 × 回撤缩放 × 回调缩放 = {context["base_size"]:.4f} × {context["drawdown_scale"]:.2f} × {context["pullback_scale"]:.2f} = {context["final_size"]:.4f}',
            force=True
        )
        operator = '-' if context['trend_direction'] == 'bullish' else '+'
        self.log(
            f'{direction_text}目标计算公式:',
            force=True
        )
        self.log(
            f'  信号价 = 15分钟收盘价 = {context["signal_price"]:.2f}',
            force=True
        )
        if context['trend_direction'] == 'bullish':
            self.log(
                f'  止损 = 信号价 - ATR止损距离 = {context["signal_price"]:.2f} - {context["stop_distance"]:.2f} = {context["stop_loss"]:.2f}',
                force=True
            )
            self.log(
                f'  止盈1 = 信号价 + ATR止损距离 = {context["signal_price"]:.2f} + {context["stop_distance"]:.2f} = {context["take_profit_1"]:.2f}',
                force=True
            )
            self.log(
                f'  止盈2 = 信号价 + 2 × ATR止损距离 = {context["signal_price"]:.2f} + 2 × {context["stop_distance"]:.2f} = {context["take_profit_2"]:.2f}',
                force=True
            )
        else:
            self.log(
                f'  止损 = 信号价 + ATR止损距离 = {context["signal_price"]:.2f} + {context["stop_distance"]:.2f} = {context["stop_loss"]:.2f}',
                force=True
            )
            self.log(
                f'  止盈1 = 信号价 - ATR止损距离 = {context["signal_price"]:.2f} - {context["stop_distance"]:.2f} = {context["take_profit_1"]:.2f}',
                force=True
            )
            self.log(
                f'  止盈2 = 信号价 - 2 × ATR止损距离 = {context["signal_price"]:.2f} - 2 × {context["stop_distance"]:.2f} = {context["take_profit_2"]:.2f}',
                force=True
            )

    def notify_order(self, order):
        """
        订单状态通知回调函数
        
        参数:
            order (backtrader.order.Order): 订单对象
            
        功能:
            1. 处理订单完成（入场或出场）时的状态更新
            2. 更新仓位状态变量（入场价格、方向、时间等）
            3. 记录入场和出场日志
            4. 处理订单取消/拒单/保证金不足情况
        """
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
                    self.log(
                        f'价格差异: 信号价{self.signal_price:.2f} 成交价{order.executed.price:.2f} 差异{diff:.2f}'
                    )
                self.log(
                    f'{"做多" if self.entry_direction == "long" else "做空"}入场: '
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

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒单', force=True)

        self.order = None

    def notify_trade(self, trade):
        """
        交易关闭通知回调函数
        
        参数:
            trade (backtrader.trade.Trade): 交易对象
            
        功能:
            1. 更新交易统计数据（总交易次数、盈利次数）
            2. 跟踪连续亏损次数（全局和当日）
            3. 计算并记录胜率
            4. 记录交易关闭日志
        """
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
        # 计算点数：净利润除以仓位大小（每单位价格变化）
        if hasattr(trade, 'size') and trade.size != 0:
            price_diff = pnl / abs(trade.size)
        else:
            price_diff = 0
        self.log(f'交易关闭: 净盈亏{pnl:.2f} 点数{price_diff:.2f} 累计{self.trade_count} 胜率{win_rate:.2f}%', force=True)

    def update_levels(self):
        """
        更新价格结构水平（高点和低点）
        
        功能:
            1. 15分钟图: 获取最近11根K线的最高点和最低点（排除当前K线）
               - 用于15分钟级别突破判断
            2. 1小时图: 获取最近21根K线的最高点和最低点（排除当前K线）
               - 用于1小时级别回调判断
        """
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
        """
        判断4小时图趋势方向
        
        返回:
            str or None: 
                - 'bullish' (多头趋势): 价格 > EMA21 > EMA55
                - 'bearish' (空头趋势): 价格 < EMA21 < EMA55
                - 'sideways' (震荡趋势): 其他情况
                - None: 数据不足（EMA55未计算完成）
                
        逻辑:
            基于价格与EMA21、EMA55的相对位置判断趋势强度
        """
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
        检查1小时图回调条件
        
        参数:
            trend_direction (str): 4小时图趋势方向（'bullish'/'bearish'/'sideways'）
            
        返回:
            bool: 是否满足回调入场条件
            
        功能:
            1. 检查价格是否处于EMA21和EMA55构成的"回调区间"
            2. 根据趋势方向，检查RSI是否处于合适范围
            3. 判断是否为"深回调"（价格非常接近EMA55），并设置仓位缩放系数
            4. 避免追涨杀跌：在强趋势区（价格超出EMA区间）等待回调
        """
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
        """
        检查15分钟图入场信号
        
        参数:
            trend_direction (str): 4小时图趋势方向（'bullish'/'bearish'/'sideways'）
            
        返回:
            bool: 是否满足入场信号
            
        功能:
            1. 结构突破: 价格突破最近N根K线的高低点
            2. RSI信号: RSI穿越50中线或达到偏置阈值
            3. 信号组合: 根据require_both_entry_signals参数决定是否需要同时满足
               - 若为True: 需要结构突破+RSI信号
               - 若为False: 结构突破或RSI信号任一即可
        """
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
        """
        更新回撤仓位缩放系数
        
        功能:
            1. 跟踪投资组合历史最高价值（max_portfolio_value）
            2. 计算当前回撤比例（drawdown）
            3. 如果回撤超过最大允许回撤（max_drawdown_pct），则仓位规模减半
               - 通过drawdown_position_scale参数控制
        """
        equity = self.broker.getvalue()
        if equity > self.max_portfolio_value:
            self.max_portfolio_value = equity
        drawdown = (self.max_portfolio_value - equity) / self.max_portfolio_value if self.max_portfolio_value > 0 else 0
        self.drawdown_position_scale = self.params.drawdown_position_scale if drawdown >= self.params.max_drawdown_pct else 1.0

    def risk_management_check(self):
        """
        风险管理和交易限制检查
        
        返回:
            bool: 是否允许开新仓（True=允许，False=禁止）
            
        功能:
            1. 连续亏损限制：达到max_consecutive_losses后暂停交易
            2. 日亏损限制：当日亏损超过max_daily_loss_pct后停止当日交易
            3. 最大回撤限制：已在update_drawdown_scale中处理
        """
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
        """
        计算仓位大小（基于风险的仓位管理）
        
        返回:
            float: 合约数量（基于15分钟图价格）
            
        计算步骤:
            1. 基于ATR计算止损距离（stop_distance = ATR × stop_loss_atr_multiplier）
            2. 计算风险金额（risk_amount = 资金 × 风险比例）
            3. 基于风险的仓位大小（risk_size = 风险金额 ÷ 止损距离）
            4. 应用多个限制：
               - 现金限制（max_position_size）
               - 杠杆限制（leverage × max_leverage_ratio）
            5. 应用缩放系数：
               - 回撤缩放（drawdown_position_scale）
               - 回调缩放（pullback_scale）
        """
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
        size *= self.drawdown_position_scale
        size *= self.pullback_scale

        return max(0, size)

    def set_stop_loss_take_profit(self, direction, entry_price):
        """
        设置止损和止盈价格
        
        参数:
            direction (str): 交易方向 ('long'/'short')
            entry_price (float): 入场价格
            
        功能:
            1. 基于ATR计算止损距离（r = ATR × stop_loss_atr_multiplier）
            2. 设置止损位：
               - 多头：入场价 - r
               - 空头：入场价 + r
            3. 设置两个止盈位：
               - 第一止盈：入场价 ± r（1倍ATR）
               - 第二止盈：入场价 ± 2r（2倍ATR）
        """
        r = self.m15_atr[0] * self.params.stop_loss_atr_multiplier
        if direction == 'long':
            self.stop_loss = entry_price - r
            self.take_profit = [entry_price + r, entry_price + 3 * r]
        else:
            self.stop_loss = entry_price + r
            self.take_profit = [entry_price - r, entry_price - 3 * r]

    def check_exit_conditions(self):
        """
        检查出场条件（止损、止盈、EMA破位）
        
        返回:
            tuple or None: (出场原因, 破位数值) 或 None
                出场原因可能的值：
                - 'stop_loss': 止损触发
                - 'take_profit_partial': 部分止盈触发（第二止盈位）
                - 'ema_break_exit': EMA破位出场
                破位数值：仅当EMA破位出场时有值，表示价格破位的点数
                None: 无出场信号
        
        功能:
            1. 止损检查：价格触及止损位
            2. 移动止损到成本：当价格达到第一止盈位（1R）时，将止损移到入场价
            3. 部分止盈：当价格达到第二止盈位（2R）时，平仓一半
            4. EMA破位出场：价格跌破/突破EMA21（带缓冲带），需连续确认
        """
        pos_size = self.getposition(self.data_15m).size
        if self.current_position is None or abs(pos_size) <= 1e-8:
            return None

        price = self.data_15m.close[0]
        ema = self.m15_ema21[0]
        atr = self.m15_atr[0]
        ema_buffer = atr * self.params.ema_exit_buffer_atr if atr > 0 else 0

        if self.entry_direction == 'long':
            if price <= self.stop_loss:
                return ('stop_loss', None)

            if price >= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做多 +1R，止损移到成本')

            if price >= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return ('take_profit_partial', None)

            if self.bars_since_entry >= self.params.min_holding_bars and price < (ema - ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    # 计算破位点数：EMA缓冲带下界 - 当前价格
                    break_amount = (ema - ema_buffer) - price
                    self.log(f'多头EMA破位计算: EMA({ema:.2f}) - 缓冲带({ema_buffer:.2f}) = {ema - ema_buffer:.2f} - 价格({price:.2f}) = 破位{break_amount:.2f}点', force=True)
                    return ('ema_break_exit', break_amount)
            else:
                self.ema_break_count = 0

        else:
            if price >= self.stop_loss:
                return ('stop_loss', None)

            if price <= self.take_profit[0] and not self.stop_moved_to_cost:
                self.stop_loss = self.entry_price
                self.stop_moved_to_cost = True
                self.log('做空 +1R，止损移到成本')

            if price <= self.take_profit[1] and not self.partial_take_profit_done:
                self.partial_take_profit_done = True
                return ('take_profit_partial', None)

            if self.bars_since_entry >= self.params.min_holding_bars and price > (ema + ema_buffer):
                self.ema_break_count += 1
                if self.ema_break_count >= self.params.ema_exit_confirm_bars:
                    # 计算破位点数：当前价格 - EMA缓冲带上界
                    break_amount = price - (ema + ema_buffer)
                    self.log(f'空头EMA破位计算: 价格({price:.2f}) - (EMA({ema:.2f}) + 缓冲带({ema_buffer:.2f})) = {price:.2f} - {ema + ema_buffer:.2f} = 破位{break_amount:.2f}点', force=True)
                    return ('ema_break_exit', break_amount)
            else:
                self.ema_break_count = 0

        return None

    def next(self):
        """
        主策略逻辑（每根K线调用）
        
        执行流程:
            1. 日期检查与重置: 如果是新的一天，重置日统计
            2. 更新价格水平: 调用update_levels
            3. 订单检查: 如果有未完成订单，等待
            4. 持仓管理: 
               - 如果有持仓，增加bars_since_entry计数
               - 检查出场条件（止损、止盈、EMA破位）
               - 如果有出场信号，执行平仓（部分或全部）
            5. 风险检查: 调用risk_management_check，不通过则返回
            6. 趋势判断: 获取4小时图趋势方向，震荡市场不交易
            7. 回调条件: 检查1小时图是否处于健康回调区间
            8. 入场信号: 检查15分钟图入场信号（突破+RSI）
            9. 仓位计算: 基于风险计算仓位大小
            10. 执行入场: 根据趋势方向开多或开空，设置止损止盈
        """
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
            # 处理返回结果：可能是元组 (reason, break_amount) 或字符串（旧格式）
            if isinstance(exit_result, tuple):
                reason = exit_result[0]
                break_amount = exit_result[1]
            else:
                # 向后兼容：旧格式返回字符串
                reason = exit_result
                break_amount = None
            
            reason_map = {
                'stop_loss': '止损触发',
                'take_profit_partial': '部分止盈触发',
                'ema_break_exit': 'EMA破位出场'
            }
            reason_text = reason_map.get(reason, reason)
            
            # 如果有破位数值，添加到日志
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
        else:
            self.signal_price = self.data_15m.close[0]
            self.order = self.sell(data=self.data_15m, size=size)
            self.set_stop_loss_take_profit('short', self.data_15m.close[0])
            context = self.build_entry_context(trend_direction, size)
            self.log_entry_context(context)
            self.log('空头入场信号确认', force=True)

    def stop(self):
        """
        策略结束回调函数
        
        功能:
            在回测结束时调用，输出最终交易统计结果（交易次数、胜率）
        """
        if self.trade_count > 0:
            win_rate = self.win_count / self.trade_count * 100
            self.log(f'策略结束统计: 交易次数{self.trade_count}, 胜率{win_rate:.1f}%', force=True)
