import backtrader as bt
import pandas as pd
from trend.dmi import DMI

class AdvancedStrategy(bt.Strategy):
    """
    高级交易策略
    规则：
    1. 日线趋势判断：
       - 上涨趋势：ADX > 25, DI+ > DI-, Boll Width > 10%, price > MA50
       - 下跌趋势：ADX > 25, DI- > DI+, price < MA50
       - 震荡行情：ADX < 20, Boll Width < 6%
    
    2. 趋势行情 → 压缩突破策略：
       入场：
       - 周线趋势：MA20 > MA60
       - 日线Boll收窄：Boll width < 0.08
       - 4H入场：收盘价重新站上Boll中轨
       出场：
       - 止盈：日线Boll中轨
       - 止损：2倍ATR
    
    3. 震荡行情 → 布林回调策略：
       入场：
       - 周线趋势：MA20 > MA60
       - 价格在日线Boll下轨附近
       - 1H入场：收盘价重新站上Boll中轨
       出场：
       - 止盈：日线Boll中轨
       - 止损：2倍ATR
    """
    params = (
        # 周线MA参数
        ('weekly_ma20', 20),
        ('weekly_ma60', 60),
        # 日线参数
        ('daily_ma50', 50),
        ('daily_boll_period', 20),
        ('daily_boll_dev', 2.0),
        ('dmi_period', 14),
        ('adx_threshold', 25),
        ('adx_oscillate_threshold', 20),
        ('boll_width_trend_threshold', 0.10),
        ('boll_width_oscillate_threshold', 0.06),
        ('boll_compression_threshold', 0.06),  # 波动压缩阈值改为6%
        # 4H参数
        ('boll_4h_period', 20),
        ('boll_4h_dev', 2.0),
        ('donchian_period', 20),  # 突破触发周期
        # 1H参数
        ('boll_1h_period', 20),
        ('boll_1h_dev', 2.0),
        # 成交量参数
        ('volume_ma_period', 20),  # 成交量MA周期
        # 止损止盈参数
        ('stop_loss_multiplier', 2.0),
        ('atr_period', 14),
        ('risk_per_trade', 0.02),  # 每笔交易风险2%
        ('atr_risk_threshold', 0.08),  # ATR风险阈值4%
        ('rr_ratio', 2.0),  # 风险回报比2:1
    )

    def __init__(self):
        # 初始化数据引用
        # 按照添加顺序：datas[0] = 周线, datas[1] = 日线, datas[2] = 4H, datas[3] = 1H
        self.log(f'datas[0] 类型: {type(self.datas[0])}')
        self.log(f'datas[0] 内容: {self.datas[0]}')
        
        # 尝试获取datas[0]的属性
        # if hasattr(self.datas[0], '__dict__'):
        #     for key, value in list(self.datas[0].__dict__.items())[:10]:  # 只显示前10个属性
        #         if not key.startswith('__'):
        #             self.log(f'datas[0].{key}: {value}')
        
        self.data_weekly = self.datas[0]
        self.data_daily = self.datas[1]
        self.data_4h = self.datas[2]
        self.data_1h = self.datas[3]

        self.data_weekly_close = self.data_weekly.close
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
                self.params.daily_ma50,
                self.params.daily_boll_period,
                self.params.dmi_period,
                self.params.boll_4h_period,
                self.params.boll_1h_period,
                self.params.atr_period,
                self.params.donchian_period,
                self.params.volume_ma_period
            )
            # 检查周线数据长度
            # 尝试多种可能的属性名称来获取数据长度
            weekly_length = 0
            # 尝试 _dataname 属性
            if hasattr(self.data_weekly, '_dataname') and self.data_weekly._dataname is not None:
                try:
                    weekly_length = len(self.data_weekly._dataname)
                    # self.log(f'通过 _dataname 获取周线数据长度: {weekly_length}')
                    # self.log(f'周线数据: {self.data_weekly._dataname}')
                except Exception as e:
                    self.log(f'访问 _dataname 出错: {str(e)}')

            # 其他时间周期数据长度
            daily_length = len(self.data_daily._dataname) if hasattr(self.data_daily, '_dataname') and self.data_daily._dataname is not None else 0
            h4_length = len(self.data_4h._dataname) if hasattr(self.data_4h, '_dataname') and self.data_4h._dataname is not None else 0
            h1_length = len(self.data_1h._dataname) if hasattr(self.data_1h, '_dataname') and self.data_1h._dataname is not None else 0

            # 打印数据长度信息
            self.log(f'数据长度: weekly={weekly_length}, daily={daily_length}, 4h={h4_length}, 1h={h1_length}')

            # 周线数据检查
            if weekly_length < 20:
                self.log(f'周线数据不足: {weekly_length} < 20')
                return False

            # 其他时间周期的数据长度检查
            if daily_length < self.min_period or h4_length < self.min_period or h1_length < self.min_period:
                self.log(
                    f'数据长度不足: daily={daily_length}, 4h={h4_length}, 1h={h1_length}, min_period={self.min_period},要求最少{self.min_period}个周期')
                return False

            # 周线MA - 使用可用的最大周期
            weekly_ma20_period = min(self.params.weekly_ma20, weekly_length)
            weekly_ma60_period = min(self.params.weekly_ma60, weekly_length)
            
            self.weekly_ma20 = bt.indicators.SMA(self.data_weekly.close, period=weekly_ma20_period)
            self.weekly_ma60 = bt.indicators.SMA(self.data_weekly.close, period=weekly_ma60_period)
            
            # 日线指标
            self.daily_ma50 = bt.indicators.SMA(self.data_daily.close, period=self.params.daily_ma50)
            self.daily_boll = bt.indicators.BBands(
                self.data_daily,
                period=self.params.daily_boll_period,
                devfactor=self.params.daily_boll_dev
            )
            # 计算Boll Width
            self.daily_boll_width = (self.daily_boll.top - self.daily_boll.bot) / self.daily_boll.mid
            # DMI指标
            self.dmi = DMI(self.data_daily, period=self.params.dmi_period)
            
            # 4H指标
            self.h4_boll = bt.indicators.BBands(
                self.data_4h,
                period=self.params.boll_4h_period,
                devfactor=self.params.boll_4h_dev
            )
            # 4H Donchian通道（突破触发）
            self.h4_donchian = bt.indicators.Highest(self.data_4h.high, period=self.params.donchian_period)
            # 4H成交量MA
            self.h4_volume_ma = bt.indicators.SMA(self.data_4h.volume, period=self.params.volume_ma_period)
            
            # 1H指标
            self.h1_boll = bt.indicators.BBands(
                self.data_1h,
                period=self.params.boll_1h_period,
                devfactor=self.params.boll_1h_dev
            )
            
            # ATR
            self.atr = bt.indicators.ATR(
                self.data_daily,
                period=self.params.atr_period
            )
            
            # 存储所有指标
            self.indicators = {
                'weekly_ma20': self.weekly_ma20,
                'weekly_ma60': self.weekly_ma60,
                'daily_ma50': self.daily_ma50,
                'daily_boll': self.daily_boll,
                'daily_boll_width': self.daily_boll_width,
                'dmi': self.dmi,
                'h4_boll': self.h4_boll,
                'h4_donchian': self.h4_donchian,
                'h4_volume_ma': self.h4_volume_ma,
                'h1_boll': self.h1_boll,
                'atr': self.atr
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
                # 设置止损和止盈
                self.stop_loss = self.entry_price - self.params.stop_loss_multiplier * self.atr[0]
                self.take_profit = self.daily_boll.mid[0]
                self.log(f'设置止损: {self.stop_loss:.2f} | 止盈: {self.take_profit:.2f}')
            else:
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f} | 数量: {abs(order.executed.size):.4f}')
                self.entry_price = None
                self.stop_loss = None
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
        if len(self.dmi.adx) < self.params.dmi_period:
            return 0

        # 计算Boll Width
        boll_width = self.daily_boll_width[0]
        
        # 上涨趋势
        if (self.dmi.adx[0] > self.params.adx_threshold and
            self.dmi.plus_di[0] > self.dmi.minus_di[0] and
            boll_width > self.params.boll_width_trend_threshold and
            self.data_daily_close[0] > self.daily_ma50[0]):
            return 1
        # 下跌趋势
        elif (self.dmi.adx[0] > self.params.adx_threshold and
              self.dmi.minus_di[0] > self.dmi.plus_di[0] and
              self.data_daily_close[0] < self.daily_ma50[0]):
            return -1
        # 震荡行情
        elif (self.dmi.adx[0] < self.params.adx_oscillate_threshold and
              boll_width < self.params.boll_width_oscillate_threshold):
            return 0
        else:
            return 0
    
    def calculate_position_size(self, entry_price):
        """计算仓位大小"""
        # 计算每笔交易的风险金额
        risk_amount = self.broker.getvalue() * self.params.risk_per_trade
        # 计算止损距离
        stop_loss_distance = self.atr[0] * self.params.stop_loss_multiplier
        # 计算仓位大小
        size = risk_amount / stop_loss_distance
        return size
    
    def check_risk_filter(self):
        """风险过滤"""
        # 检查ATR是否超过阈值
        atr_percent = self.atr[0] / self.data_daily_close[0]
        if atr_percent > self.params.atr_risk_threshold:
            # self.log(f'风险过滤：ATR {atr_percent:.4f} > 阈值 {self.params.atr_risk_threshold}')
            return False
        return True

    def next(self):
        """主策略逻辑"""
        if self.order:
            return

        # 检查数据长度
        try:

            # 检查指标是否存在
            required_indicators = ['weekly_ma20', 'weekly_ma60', 'daily_ma50', 'daily_boll', 
                                  'daily_boll_width', 'dmi', 'h4_boll', 'h4_donchian', 
                                  'h4_volume_ma', 'h1_boll', 'atr']
            for indicator_name in required_indicators:
                if not hasattr(self, indicator_name):
                    self.log(f'指标 {indicator_name} 未初始化')
                    return
            
            # 检查指标是否已经计算完成
            if not self.indicators_ready:
                try:
                    # 检查所有指标是否有足够的数据
                    if (len(self.weekly_ma20) > self.params.weekly_ma20 and
                        len(self.weekly_ma60) > self.params.weekly_ma60 and
                        len(self.dmi.adx) > self.params.dmi_period and
                        len(self.daily_boll.mid) > self.params.daily_boll_period and
                        len(self.h4_boll.mid) > self.params.boll_4h_period and
                        len(self.h1_boll.mid) > self.params.boll_1h_period and
                        len(self.atr) > self.params.atr_period):
                        # 检查指标值是否有效
                        if (not pd.isna(self.weekly_ma20[0]) and
                            not pd.isna(self.weekly_ma60[0]) and
                            not pd.isna(self.dmi.adx[0]) and
                            not pd.isna(self.daily_boll.mid[0]) and
                            not pd.isna(self.h4_boll.mid[0]) and
                            not pd.isna(self.h1_boll.mid[0]) and
                            not pd.isna(self.atr[0])):
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
                    len(self.weekly_ma20) < 1 or len(self.weekly_ma60) < 1 or
                    len(self.daily_ma50) < self.params.daily_ma50 or
                    len(self.h4_boll.top) < self.params.boll_4h_period or
                    len(self.h1_boll.top) < self.params.boll_1h_period or
                    len(self.atr) < self.params.atr_period):
                    return
            except Exception as e:
                self.log(f'指标数据检查错误: {str(e)}')
                return

            # 判断周线趋势
            try:
                # 周线趋势判断 - 添加安全检查
                if len(self.weekly_ma20) < 1 or len(self.weekly_ma60) < 1:
                    return
                weekly_trend = self.weekly_ma20[0] > self.weekly_ma60[0]
                if not weekly_trend:
                    # self.log('周线趋势下跌，等待趋势回升')
                    return

                # 判断日线趋势
                self.trend_type = self.determine_trend()
                
                # 风险过滤
                if not self.check_risk_filter():
                    return
                
                # 检查是否有仓位
                if not self.position:
                    # 趋势行情 → 压缩突破策略
                    if self.trend_type == 1:
                        # 日线Boll收窄（波动压缩识别）
                        if self.daily_boll_width[0] < self.params.boll_compression_threshold:
                            # 4H突破触发
                            if self.data_4h_close[0] > self.h4_donchian[0]:
                                # 入场确认：成交量大于MA20
                                if self.data_4h.volume[0] > self.h4_volume_ma[0]:
                                    self.log(f'趋势行情压缩突破策略入场 | 价格: {self.data_4h_close[0]:.2f} | 突破: {self.h4_donchian[0]:.2f}')
                                    # 计算仓位大小（风险控制）
                                    size = self.calculate_position_size(self.data_4h_close[0])
                                    self.order = self.buy(size=size)
                    
                    # 震荡行情 → 布林回调策略
                    elif self.trend_type == 0:
                        # 4H回调触发：触碰下轨
                        if self.data_4h_close[0] <= self.h4_boll.bot[0] * 1.005:  # 允许5%的误差
                            # 入场确认：成交量大于MA20
                            if self.data_4h.volume[0] > self.h4_volume_ma[0]:
                                self.log(f'震荡行情布林回调策略入场 | 价格: {self.data_4h_close[0]:.2f} | 下轨: {self.h4_boll.bot[0]:.2f}')
                                # 计算仓位大小（风险控制）
                                size = self.calculate_position_size(self.data_4h_close[0])
                                self.order = self.buy(size=size)
                else:
                    # 出场条件
                    # 移动止盈：止盈随ATR移动
                    current_take_profit = max(self.take_profit, self.entry_price + (self.atr[0] * 0.5))
                    
                    # 止损
                    if self.stop_loss is not None and self.data_daily_close[0] <= self.stop_loss:
                        self.log(f'触发止损 | 价格: {self.data_daily_close[0]:.2f} | 止损价: {self.stop_loss:.2f}')
                        self.order = self.close()
                    # 止盈：日线中轨 或 风险回报比2:1
                    elif (abs(self.data_daily_close[0] - self.daily_boll.mid[0]) / self.daily_boll.mid[0] < 0.005 or
                          self.data_daily_close[0] >= current_take_profit):
                        self.log(f'触发止盈 | 价格: {self.data_daily_close[0]:.2f} | 中轨: {self.daily_boll.mid[0]:.2f} | 目标: {current_take_profit:.2f}')
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