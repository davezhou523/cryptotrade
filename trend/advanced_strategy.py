import backtrader as bt
import pandas as pd
from trend.dmi import DMI

class AdvancedStrategy(bt.Strategy):
    """

    """
    params = (
        # 日线EMA参数
        ('daily_ema21', 21),
        ('daily_ema55', 55),
        ('daily_ema122', 122),
        ('daily_boll_period', 20),
        ('daily_boll_dev', 2.0),
        ('dmi_period', 14),
        ('adx_threshold', 18),
        ('adx_oscillate_threshold', 20),
        ('boll_width_trend_threshold', 0.10),
        ('boll_width_oscillate_threshold', 0.06),
        ('boll_compression_threshold', 0.06),  # 波动压缩阈值改为6%
        # 4H参数
        ('boll_4h_period', 20),
        ('boll_4h_dev', 2.0),
        ('donchian_period', 18),  # 突破触发周期
        # 1H参数
        ('boll_1h_period', 20),
        ('boll_1h_dev', 2.0),
        # 成交量参数
        ('volume_ma_period', 20),  # 成交量MA周期
        # 止损止盈参数
        ('stop_loss_multiplier', 2.0),
        ('atr_period', 14),
        ('risk_per_trade', 0.02),  # 每笔交易风险2%
        ('atr_risk_threshold', 0.01),  # ATR风险阈值4%
        ('rr_ratio', 2.0),  # 风险回报比2:1
    )

    def __init__(self):
        # 初始化数据引用
        self.data_daily = self.datas[0]
        self.data_4h = self.datas[1]
        self.data_1h = self.datas[2]
        
        # 打印数据引用信息
        self.log(f'数据引用初始化:')
        self.log(f'  data_daily: {self.data_daily}, name: {getattr(self.data_daily, "_name", "unknown")}')
        self.log(f'  data_4h: {self.data_4h}, name: {getattr(self.data_4h, "_name", "unknown")}')
        self.log(f'  data_1h: {self.data_1h}, name: {getattr(self.data_1h, "_name", "unknown")}')
        
        # 打印datas列表信息
        self.log(f'datas列表长度: {len(self.datas)}')
        for i, data in enumerate(self.datas):
            self.log(f'  datas[{i}]: {data}, name: {getattr(data, "_name", "unknown")}')

        self.data_daily_close = self.data_daily.close
        self.data_daily_high = self.data_daily.high
        self.data_daily_low = self.data_daily.low
        self.data_4h_close = self.data_4h.close
        self.data_1h_close = self.data_1h.close
        
        # 跟踪订单状态
        self.order = None
        self.stop_loss = None
        self.take_profit = None
        self.entry_price = None
        self.trend_type = 0  # 0: 震荡, 1: 上涨, -1: 下跌
        
        # 初始化指标状态
        self.indicators_ready = False
        self.indicators = {}
        
        # 延迟初始化指标，避免数据长度不足的问题
        self._initialize_indicators()
    
    def _initialize_indicators(self):
        """延迟初始化指标"""
        try:
            # 计算最小周期（排除周线MA60，因为周线数据可能不足）
            self.min_period = max(
                self.params.daily_boll_period,
                self.params.dmi_period,
                self.params.boll_4h_period,
                self.params.boll_1h_period,
                self.params.atr_period,
                self.params.donchian_period,
                self.params.volume_ma_period
            )


            # 其他时间周期数据长度
            daily_length = len(self.data_daily._dataname) if hasattr(self.data_daily, '_dataname') and self.data_daily._dataname is not None else 0
            h4_length = len(self.data_4h._dataname) if hasattr(self.data_4h, '_dataname') and self.data_4h._dataname is not None else 0
            h1_length = len(self.data_1h._dataname) if hasattr(self.data_1h, '_dataname') and self.data_1h._dataname is not None else 0

            # 打印数据长度信息
            self.log(f'数据长度: daily={daily_length}, 4h={h4_length}, 1h={h1_length}')

            # 打印指标参数设置
            self.log('\n=== 指标参数设置 ===')
            self.log(f'日线EMA21周期: {self.params.daily_ema21},日线EMA55周期: {self.params.daily_ema55},日线EMA122周期: {self.params.daily_ema122}')
            self.log(f'日线布林带周期: {self.params.daily_boll_period}, 标准差: {self.params.daily_boll_dev}')
            self.log(f'DMI周期: {self.params.dmi_period}')
            self.log(f'4H布林带周期: {self.params.boll_4h_period}, 标准差: {self.params.boll_4h_dev}')
            self.log(f'4H Donchian通道周期: {self.params.donchian_period}')
            self.log(f'4H EMA21周期: 21')
            self.log(f'1H布林带周期: {self.params.boll_1h_period}, 标准差: {self.params.boll_1h_dev}')
            self.log(f'ATR周期: {self.params.atr_period},成交量MA周期: {self.params.volume_ma_period}')

            # 其他时间周期的数据长度检查
            if daily_length < self.min_period or h4_length < self.min_period or h1_length < self.min_period:
                self.log(
                    f'数据长度不足: daily={daily_length}, 4h={h4_length}, 1h={h1_length}, min_period={self.min_period},要求最少{self.min_period}个周期')
                return False

            # 添加 EMA 指标
            self.log('\n=== 初始化指标 ===')
            self.log('初始化日线EMA指标...')
            self.daily_ema21 = bt.indicators.EMA(self.data_daily.close, period=self.params.daily_ema21)
            self.daily_ema55 = bt.indicators.EMA(self.data_daily.close, period=self.params.daily_ema55)
            self.daily_ema122 = bt.indicators.EMA(self.data_daily.close, period=self.params.daily_ema122)
            
            self.log('初始化日线布林带指标...')
            self.daily_boll = bt.indicators.BBands(
                self.data_daily,
                period=self.params.daily_boll_period,
                devfactor=self.params.daily_boll_dev
            )
            # 计算Boll Width
            self.daily_boll_width = (self.daily_boll.top - self.daily_boll.bot) / self.daily_boll.mid
            
            self.log('初始化DMI指标...')
            self.dmi = DMI(self.data_daily, period=self.params.dmi_period)
            
            # 4H指标
            self.log('初始化4H指标...')
            self.h4_boll = bt.indicators.BBands(
                self.data_4h,
                period=self.params.boll_4h_period,
                devfactor=self.params.boll_4h_dev
            )
            # 4H Donchian通道（突破入场）
            self.h4_donchian_high = bt.indicators.Highest(self.data_4h.high, period=self.params.donchian_period)
            # 4H Donchian Low（跌破入场）
            self.h4_donchian_low = bt.indicators.Lowest(self.data_4h.low, period=self.params.donchian_period)
            # 4H EMA21（止盈）
            self.h4_ema21 = bt.indicators.EMA(self.data_4h.close, period=21)
            # 4H ADX（趋势强度）
            self.h4_dmi = DMI(self.data_4h, period=self.params.dmi_period)
            # 4H ATR（波动率判断）
            self.log(f'初始化4H ATR指标 (周期: {self.params.atr_period})...')
            self.h4_atr = bt.indicators.ATR(self.data_4h, period=self.params.atr_period)
            # 4H成交量MA
            self.h4_volume_ma = bt.indicators.SMA(self.data_4h.volume, period=self.params.volume_ma_period)

            
            # 1H指标
            self.log('初始化1H指标...')
            self.h1_boll = bt.indicators.BBands(
                self.data_1h,
                period=self.params.boll_1h_period,
                devfactor=self.params.boll_1h_dev
            )
            
            # 日线ATR（用于风险控制）
            self.log(f'初始化日线ATR指标 (周期: {self.params.atr_period})...')
            self.daily_atr = bt.indicators.ATR(
                self.data_daily,
                period=self.params.atr_period
            )
            
            # 存储所有指标
            self.indicators = {
                'daily_ema21': self.daily_ema21,
                'daily_ema55': self.daily_ema55,
                'daily_ema122': self.daily_ema122,
                'daily_boll': self.daily_boll,
                'daily_boll_width': self.daily_boll_width,
                'dmi': self.dmi,
                'h4_boll': self.h4_boll,
                'h4_donchian_high': self.h4_donchian_high,
                'h4_donchian_low': self.h4_donchian_low,
                'h4_ema21': self.h4_ema21,
                'h4_dmi': self.h4_dmi,
                'h4_atr': self.h4_atr,
                'h4_volume_ma': self.h4_volume_ma,
                'h1_boll': self.h1_boll,
                'daily_atr': self.daily_atr
            }
            
            self.indicators_ready = True
            self.log('所有指标计算完成，策略开始运行')
            return True
            
        except Exception as e:
            self.log(f'指标初始化错误: {str(e)}')
            import traceback
            traceback.print_exc()
            return False

    def log(self, txt, dt=None):
        """日志记录函数"""
        dt = dt or self.datas[0].datetime.datetime(0)
        print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                self.entry_price = order.executed.price
                # 设置止损（4H ATR × 2）
                self.stop_loss = self.entry_price - self.params.stop_loss_multiplier * self.h4_atr[0]
                self.log(f'设置止损: {self.stop_loss:.2f}')
            elif order.issell():
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f}')
                self.entry_price = order.executed.price
                # 设置止损（4H ATR × 2）
                self.stop_loss = self.entry_price + self.params.stop_loss_multiplier * self.h4_atr[0]
                self.log(f'设置止损: {self.stop_loss:.2f}')
            else:
                self.log(f'平仓执行 | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f}')
                self.entry_price = None
                self.stop_loss = None
                self.take_profit = None
                self.take_profit = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单被取消/保证金不足/被拒绝')

        self.order = None

    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return

        self.log(f'交易完成 | 毛利润: {trade.pnl:.2f} | 净利润: {trade.pnlcomm:.2f}')

    def determine_trend(self):
        """判断日线趋势"""
        if len(self.daily_ema21) < 1 or len(self.daily_ema55) < 1 or len(self.daily_ema122) < 1:
            self.log('未足够ema数据判断趋势')
            return
        if len(self.dmi.adx) < self.params.dmi_period:
            self.log('未足够adx数据判断趋势')
            return None
        daily_trend = (self.daily_ema21[0] > self.daily_ema55[0] and
                       self.daily_ema55[0] > self.daily_ema122[0])
        short_trend = (
                self.daily_ema21[0] < self.daily_ema55[0] and
                self.daily_ema55[0] < self.daily_ema122[0]
        )

        # 计算Boll Width
        boll_width = self.daily_boll_width[0]
        
        # 上涨趋势
        if (self.dmi.adx[0] > self.params.adx_threshold and
            self.dmi.plus_di[0] > self.dmi.minus_di[0] and
            daily_trend):
            return 1
        # 下跌趋势
        elif (self.dmi.adx[0] > self.params.adx_threshold and
              self.dmi.minus_di[0] > self.dmi.plus_di[0] and
              short_trend):
            return -1
        # 震荡行情
        elif (self.dmi.adx[0] < self.params.adx_oscillate_threshold and
              boll_width < self.params.boll_width_oscillate_threshold):
            return 0
        else:
            return None
    
    def calculate_position_size(self, entry_price):
        """计算仓位大小"""
        # 计算每笔交易的风险金额
        risk_amount = self.broker.getvalue() * self.params.risk_per_trade
        # 计算止损距离（使用4H ATR）
        stop_loss_distance = self.h4_atr[0] * self.params.stop_loss_multiplier
        # 计算仓位大小
        size = risk_amount / stop_loss_distance
        return size
    
    def check_risk_filter(self):
        """风险过滤"""
        # 检查4H ATR是否超过阈值
        atr_percent = self.h4_atr[0] / self.data_4h_close[0]
        if atr_percent > self.params.atr_risk_threshold:
            self.log(f'风险过滤：ATR {atr_percent:.4f} > 阈值 {self.params.atr_risk_threshold}')
            return False
        return True


    # 在策略的next方法中添加详细的指标数值日志
    def next(self):
        """主策略逻辑"""
        if self.order:
            return

        # 直接使用 data_4h 的数据，而不是依赖 self.data
        # 这样无论当前处理的是哪个数据源，策略逻辑都会基于 4H 数据执行

        # 检查数据长度
        try:
            # 获取当前4H时间
            current_time = self.data_4h.datetime.datetime(0)

            # 检查指标是否存在
            required_indicators = ['daily_ema21', 'daily_ema55', 'daily_ema122', 'daily_boll',
                                   'daily_boll_width', 'dmi', 'h4_boll', 'h4_donchian_high',
                                   'h4_donchian_low', 'h4_ema21', 'h4_dmi', 'h4_atr',
                                   'h4_volume_ma', 'h1_boll', 'daily_atr']
            for indicator_name in required_indicators:
                if not hasattr(self, indicator_name):
                    self.log(f'指标 {indicator_name} 未初始化')
                    return

            # 检查指标是否已经计算完成
            if not self.indicators_ready:
                try:
                    # 检查所有指标是否有足够的数据
                    if (len(self.dmi.adx) > self.params.dmi_period and
                            len(self.daily_boll.mid) > self.params.daily_boll_period and
                            len(self.h4_boll.mid) > self.params.boll_4h_period and
                            len(self.h1_boll.mid) > self.params.boll_1h_period and
                            len(self.h4_atr) > self.params.atr_period):
                        # 检查指标值是否有效
                        if (not pd.isna(self.daily_ema21[0]) and
                                not pd.isna(self.daily_ema55[0]) and
                                not pd.isna(self.daily_ema122[0]) and
                                not pd.isna(self.dmi.adx[0]) and
                                not pd.isna(self.daily_boll.mid[0]) and
                                not pd.isna(self.h4_boll.mid[0]) and
                                not pd.isna(self.h1_boll.mid[0]) and
                                not pd.isna(self.h4_atr[0])):
                            self.indicators_ready = True
                            self.log('所有指标计算完成，策略开始运行')
                except Exception as e:
                    self.log(f'指标检查错误: {str(e)}')
                    import traceback
                    traceback.print_exc()
                    return

            if not self.indicators_ready:
                self.log('指标计算中，等待更多数据')
                return

            # 检查指标数据是否足够
            try:
                # 检查所有关键指标是否有足够的数据
                if (len(self.dmi.adx) < self.params.dmi_period or
                        len(self.daily_boll.top) < self.params.daily_boll_period or
                        len(self.daily_ema21) < self.params.daily_ema21 or
                        len(self.daily_ema55) < self.params.daily_ema55 or
                        len(self.daily_ema122) < 122 or
                        len(self.h4_boll.top) < self.params.boll_4h_period or
                        len(self.h4_donchian_high) < self.params.donchian_period or
                        len(self.h4_donchian_low) < self.params.donchian_period or
                        len(self.h4_ema21) < 21 or
                        len(self.h4_dmi.adx) < self.params.dmi_period or
                        len(self.h4_atr) < self.params.atr_period or
                        len(self.h1_boll.top) < self.params.boll_1h_period or
                        len(self.daily_atr) < self.params.atr_period):
                    self.log('指标数据不足，等待更多数据')
                    return
            except Exception as e:
                self.log(f'指标数据检查错误: {str(e)}')
                return

            try:
                # 获取当前4H收盘价
                current_4h_close = self.data_4h.close[0]
                current_h4_atr = self.h4_atr[0]

                # 打印当前数据信息用于调试
                if current_time.hour % 8 == 0:  # 每8小时打印一次
                    self.log(
                        f'调试信息: 当前时间={current_time}, 4H收盘价={current_4h_close:.2f}, 4H ATR={current_h4_atr:.2f}')

                    # 打印详细的指标数值
                    self.log('\n=== 指标数值 ===')
                    self.log(f'日线EMA21: {self.daily_ema21[0]:.2f}')
                    self.log(f'日线EMA55: {self.daily_ema55[0]:.2f}')
                    self.log(f'日线EMA122: {self.daily_ema122[0]:.2f}')
                    self.log(f'日线ADX: {self.dmi.adx[0]:.2f}，日线DI+: {self.dmi.plus_di[0]:.2f},日线DI-: {self.dmi.minus_di[0]:.2f}')

                    self.log(f'4H ATR: {self.h4_atr[0]:.2f} (Binance标准: 14周期)')
                    self.log(f'4H ADX: {self.h4_dmi.adx[0]:.2f},4H DI+: {self.h4_dmi.plus_di[0]:.2f},4H DI-: {self.h4_dmi.minus_di[0]:.2f}')
                    self.log(f'4H EMA21: {self.h4_ema21[0]:.2f}')
                    self.log(f'4H Donchian上轨: {self.h4_donchian_high[0]:.2f}')
                    self.log(f'4H Donchian下轨: {self.h4_donchian_low[0]:.2f}')

                # 判断日线趋势
                self.trend_type = self.determine_trend()
                if self.trend_type is None:
                    self.log('未确定趋势，等待更多数据')
                    return
                else:
                    trend_str = '上涨' if self.trend_type == 1 else '下跌' if self.trend_type == -1 else '震荡'
                    self.log(f'当前趋势: {trend_str}')

                # 风险过滤
                if not self.check_risk_filter():
                    return

                # 检查价格是否大于 EMA122
                if self.data_daily.close[0] <= self.daily_ema122[0]:
                    self.log(f'价格 {self.data_daily.close[0]:.2f} 低于 EMA122 {self.daily_ema122[0]:.2f}，不入场')
                    return
                else:
                    self.log(f'价格 {self.data_daily.close[0]:.2f} 高于 EMA122 {self.daily_ema122[0]:.2f}，继续检查')

                # 波动过滤：ATR / price > 1.5%
                h4_atr_percent = current_h4_atr / current_4h_close
                if h4_atr_percent < 0.015:
                    self.log(
                        f'波动太小，ATR/价格 = {h4_atr_percent:.4f} < 0.015，不入场,h4_atr={current_h4_atr:.2f},4h_close={current_4h_close:.2f}')
                    return
                else:
                    self.log(f'波动足够，ATR/价格 = {h4_atr_percent:.4f} >= 0.015，继续检查')

                # 趋势强度：ADX > 20
                if self.h4_dmi.adx[0] <= 20:
                    self.log(f'趋势强度不足，4h ADX = {self.h4_dmi.adx[0]:.2f} <= 20，不入场')
                    return
                else:
                    self.log(f'趋势强度足够，4h ADX = {self.h4_dmi.adx[0]:.2f} > 20，继续检查')

                # 检查是否有仓位
                if not self.position:

                    if self.trend_type == 1:
                        # 4H突破入场：价格突破Donchian Channel
                        if current_4h_close > self.h4_donchian_high[0]:
                            # 入场确认：成交量大于MA20
                            if self.data_4h.volume[0] > self.h4_volume_ma[0]:
                                self.log(
                                    f'强多头趋势突破入场 | 价格: {current_4h_close:.2f} | 突破: {self.h4_donchian_high[0]:.2f} | ADX: {self.h4_dmi.adx[0]:.2f}')
                                # 计算仓位大小（风险控制）
                                size = self.calculate_position_size(current_4h_close)
                                self.order = self.buy(size=size)
                            else:
                                self.log(
                                    f'突破条件满足但成交量不足 | 成交量: {self.data_4h.volume[0]} < MA20: {self.h4_volume_ma[0]}')
                        else:
                            self.log(
                                f'未突破Donchian通道 | 当前价格: {current_4h_close:.2f} <= 通道上轨: {self.h4_donchian_high[0]:.2f}')

                    # 强空头趋势：EMA21 < EMA55 < EMA122
                    elif self.trend_type == -1:
                        # 4H跌破入场：价格跌破Donchian Low
                        if current_4h_close < self.h4_donchian_low[0]:
                            # 入场确认：成交量大于MA20
                            if self.data_4h.volume[0] > self.h4_volume_ma[0]:
                                self.log(
                                    f'强空头趋势跌破入场 | 价格: {current_4h_close:.2f} | 跌破: {self.h4_donchian_low[0]:.2f} | ADX: {self.h4_dmi.adx[0]:.2f}')
                                # 计算仓位大小（风险控制）
                                size = self.calculate_position_size(current_4h_close)
                                self.order = self.sell(size=size)
                            else:
                                self.log(
                                    f'跌破条件满足但成交量不足 | 成交量: {self.data_4h.volume[0]} < MA20: {self.h4_volume_ma[0]}')
                        else:
                            self.log(
                                f'未跌破Donchian通道 | 当前价格: {current_4h_close:.2f} >= 通道下轨: {self.h4_donchian_low[0]:.2f}')
                else:
                    # 出场条件

                    # 止损：4H ATR × 2
                    if self.stop_loss is not None and current_4h_close <= self.stop_loss:
                        self.log(f'触发止损4h | 价格: {current_4h_close:.2f} | 止损价: {self.stop_loss:.2f}')
                        self.order = self.close()
                    # 止盈：跌破4H EMA21
                    elif current_4h_close < self.h4_ema21[0]:
                        self.log(f'触发止盈 | 价格: {current_4h_close:.2f} | 4H EMA21: {self.h4_ema21[0]:.2f}')
                        self.order = self.close()
            except Exception as e:
                self.log(f'策略逻辑错误: {str(e)}')
                import traceback
                traceback.print_exc()
                return
        except Exception as e:
            self.log(f'策略执行错误: {str(e)}')
            import traceback
            traceback.print_exc()
            return