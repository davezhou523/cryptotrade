import backtrader as bt
import sys
from datetime import datetime

# Binance API配置
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"


class DMI(bt.Indicator):
    """
    自定义DMI指标类
    Directional Movement Index (DMI) 用于判断趋势强度和方向
    """
    lines = ('plus_di', 'minus_di', 'adx')
    params = (('period', 14),)

    def __init__(self):
        # 使用Backtrader内置的DMI指标
        self.dmi = bt.indicators.DirectionalMovement(period=self.params.period)
        self.lines.plus_di = self.dmi.plusDI
        self.lines.minus_di = self.dmi.minusDI
        self.lines.adx = self.dmi.adx


class TrendDetector(bt.Indicator):
    """
    趋势判断类，使用DMI+BOLL技术指标判断三种趋势类型
    - 震荡趋势
    - 单边上涨趋势
    - 单边下跌趋势
    """
    lines = ('trend_type',)
    params = (
        # BOLL参数
        ('boll_period', 20),
        ('boll_dev', 2),

        # DMI参数
        ('dmi_period', 14),
        ('adx_threshold', 25),  # ADX阈值，用于判断趋势强度

        # 趋势类型定义
        ('sideways_trend', 0),
        ('bullish_trend', 1),
        ('bearish_trend', -1),
    )

    def __init__(self):
        # 初始化指标
        self.dmi = DMI(period=self.params.dmi_period)
        self.boll = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )

    def next(self):
        """
        计算当前趋势类型
        - 震荡趋势：ADX < adx_threshold
        - 单边上涨趋势：+DI > -DI 且 ADX >= adx_threshold
        - 单边下跌趋势：-DI > +DI 且 ADX >= adx_threshold
        """
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plus_di[0]
        minus_di_value = self.dmi.minus_di[0]

        # 判断趋势类型
        if adx_value < self.params.adx_threshold:
            # 震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend
        elif plus_di_value > minus_di_value and adx_value >= self.params.adx_threshold:
            # 单边上涨趋势
            self.lines.trend_type[0] = self.params.bullish_trend
        elif minus_di_value > plus_di_value and adx_value >= self.params.adx_threshold:
            # 单边下跌趋势
            self.lines.trend_type[0] = self.params.bearish_trend
        else:
            # 默认情况：震荡趋势
            self.lines.trend_type[0] = self.params.sideways_trend


class StochasticRSI(bt.Indicator):
    """
    自定义Stochastic RSI指标
    计算方法：先计算RSI，然后对RSI应用Stochastic指标
    """
    lines = ('percK', 'percD')
    params = (
        ('period', 14),      # RSI周期
        ('stoch_period', 14),  # Stochastic K周期
        ('dperiod', 3),        # Stochastic D周期
        ('movav', bt.indicators.SMA),  # 移动平均线类型
    )

    def __init__(self):
        # 计算RSI
        rsi = bt.indicators.RSI(period=self.params.period)
        
        # 计算RSI在指定周期内的最高价和最低价
        highest_rsi = bt.indicators.Highest(rsi, period=self.params.stoch_period)
        lowest_rsi = bt.indicators.Lowest(rsi, period=self.params.stoch_period)
        
        # 计算%K
        self.l.percK = 100.0 * (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
        
        # 计算%D - %K的移动平均线
        self.l.percD = self.params.movav(self.l.percK, period=self.params.dperiod)


class StochRSIStrategy(bt.Strategy):
    """
    结合趋势判断、Stoch RSI指标买卖信号和ATR止损止盈的策略
    """
    params = (
        # 趋势检测参数
        ('boll_period', 20),
        ('boll_dev', 2),
        ('dmi_period', 14),
        ('adx_threshold', 25),
        
        # Stoch RSI参数 - 优化后的参数
        ('rsi_period', 21),        # RSI周期从14调整为21
        ('stoch_period', 7),       # Stoch周期从14调整为7
        ('stoch_d_period', 3),
        ('oversold', 25),          # 超卖阈值从30调整为25
        ('overbought', 75),        # 超买阈值从70调整为75
        
        # ATR参数 - 优化后的参数
        ('atr_period', 14),
        ('stop_loss_multiplier', 2.0),  # 止损倍数从1.5调整为2.0
        ('take_profit_multiplier', 3.0),
        ('trailing_stop_multiplier', 2.5),  # 移动止损倍数从2.0调整为2.5
        
        # 移动平均线参数
        ('ma_period', 50),
        
        # 风险控制参数
        ('max_loss_per_trade', 0.02),  # 最大单笔亏损2%
        ('min_hold_periods', 2),       # 最小持仓时间2周期
        
        ('printlog', True),
    )

    def log(self, txt, dt=None, doprint=False):
        """日志记录函数"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def __init__(self):
        # 初始化数据引用
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_open = self.datas[0].open
        
        # 初始化趋势检测器
        self.trend_detector = TrendDetector(
            boll_period=self.params.boll_period,
            boll_dev=self.params.boll_dev,
            dmi_period=self.params.dmi_period,
            adx_threshold=self.params.adx_threshold
        )
        
        # 初始化自定义Stochastic RSI指标
        self.stoch_rsi = StochasticRSI(
            period=self.params.rsi_period,
            stoch_period=self.params.stoch_period,
            dperiod=self.params.stoch_d_period
        )
        
        # 初始化ATR指标用于止损止盈
        self.atr = bt.indicators.ATR(
            period=self.params.atr_period
        )
        
        # 初始化移动平均线指标
        self.ma = bt.indicators.SMA(self.data_close, period=self.params.ma_period)
        
        # 初始化BOLL指标用于额外过滤
        self.boll = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )
        
        # 跟踪订单状态
        self.order = None
        self.stop_loss = None
        self.take_profit = None
        self.trailing_stop = None
        self.entry_price = None
        self.entry_bar = None  # 记录建仓时的bar位置
        
        # 趋势名称映射
        self.trend_names = {
            0: '震荡趋势',
            1: '单边上涨趋势',
            -1: '单边下跌趋势'
        }

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行 | 价格: {order.executed.price:.2f}')
                # 设置ATR止损止盈和移动止损
                atr_value = self.atr[0]
                self.entry_price = order.executed.price
                self.entry_bar = len(self)  # 记录当前bar位置
                
                # 计算基于ATR的止损
                atr_stop = self.entry_price - self.params.stop_loss_multiplier * atr_value
                # 计算基于最大亏损的止损
                max_loss_stop = self.entry_price * (1 - self.params.max_loss_per_trade)
                # 取较大的止损值（更严格的止损）
                self.stop_loss = max(atr_stop, max_loss_stop)
                
                self.take_profit = self.entry_price + self.params.take_profit_multiplier * atr_value
                self.trailing_stop = self.entry_price - self.params.trailing_stop_multiplier * atr_value
                self.log(f'设置止损: {self.stop_loss:.2f}, 设置止盈: {self.take_profit:.2f}, 设置移动止损: {self.trailing_stop:.2f}')
            else:
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f}')
                # 重置止损止盈
                self.stop_loss = None
                self.take_profit = None
                self.trailing_stop = None
                self.entry_price = None
                self.entry_bar = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/被拒绝')

        self.order = None

    def next(self):
        """策略的主要逻辑"""
        if self.order:
            return

        # 获取当前趋势类型
        trend_type = int(self.trend_detector.trend_type[0])
        trend_name = self.trend_names[trend_type]
        
        # 获取Stoch RSI值
        stoch_rsi_k = self.stoch_rsi.percK[0]
        stoch_rsi_d = self.stoch_rsi.percD[0]
        
        # 获取前几个周期的Stoch RSI值用于确认信号
        if len(self) < 3:
            return  # 确保有足够的历史数据
        
        stoch_rsi_k_prev = self.stoch_rsi.percK[-1]
        stoch_rsi_d_prev = self.stoch_rsi.percD[-1]
        stoch_rsi_k_prev2 = self.stoch_rsi.percK[-2]
        stoch_rsi_d_prev2 = self.stoch_rsi.percD[-2]
        
        # 获取技术指标值
        ma_value = self.ma[0]
        atr_value = self.atr[0]
        adx_value = self.trend_detector.dmi.adx[0]
        boll_mid = self.boll.mid[0]
        boll_lower = self.boll.bot[0]  # 将lower改为bot
        
        # 打印趋势判断和指标值
        self.log(f'趋势判断: {trend_name}, Stoch RSI K: {stoch_rsi_k:.2f}, D: {stoch_rsi_d:.2f}, ATR: {atr_value:.2f}, ADX: {adx_value:.2f}', doprint=True)

        # 检查是否需要止损止盈或移动止损
        if self.position:
            # 检查最小持仓时间
            if len(self) - self.entry_bar < self.params.min_hold_periods:
                # 还在最小持仓时间内，只检查止损
                if self.data_close[0] <= self.stop_loss:
                    self.log(f'触发止损 | 价格: {self.data_close[0]:.2f}, 止损价: {self.stop_loss:.2f}')
                    self.order = self.sell(size=self.position.size)
                return
            
            # 更新移动止损（只向上移动）
            new_trailing_stop = self.data_close[0] - self.params.trailing_stop_multiplier * atr_value
            if new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop
                self.log(f'更新移动止损: {self.trailing_stop:.2f}')
            
            # 趋势反转卖出信号
            if trend_type == -1 and adx_value > self.params.adx_threshold:
                self.log(f'强下跌趋势确认，执行卖出 | 当前价格: {self.data_close[0]:.2f}')
                self.order = self.sell(size=self.position.size)
                return
            
            # Stoch RSI超买卖出信号 - 增加连续确认
            if (stoch_rsi_k > self.params.overbought and stoch_rsi_k_prev > self.params.overbought) and \
               stoch_rsi_k < stoch_rsi_k_prev:
                self.log(f'Stoch RSI连续超买且K线向下，执行卖出 | 当前价格: {self.data_close[0]:.2f}')
                self.order = self.sell(size=self.position.size)
                return
            
            # 检查止损
            if self.data_close[0] <= self.stop_loss:
                self.log(f'触发止损 | 价格: {self.data_close[0]:.2f}, 止损价: {self.stop_loss:.2f}')
                self.order = self.sell(size=self.position.size)
                return
            
            # 检查移动止损
            if self.data_close[0] <= self.trailing_stop:
                self.log(f'触发移动止损 | 价格: {self.data_close[0]:.2f}, 移动止损价: {self.trailing_stop:.2f}')
                self.order = self.sell(size=self.position.size)
                return
            
            # 检查止盈
            if self.data_close[0] >= self.take_profit:
                self.log(f'触发止盈 | 价格: {self.data_close[0]:.2f}, 止盈价: {self.take_profit:.2f}')
                self.order = self.sell(size=self.position.size)
                return

        # 无仓位时，根据趋势和Stoch RSI指标产生买入信号
        if not self.position:
            # 获取DMI指标值
            plus_di = self.trend_detector.dmi.plus_di[0]
            minus_di = self.trend_detector.dmi.minus_di[0]
            
            # 买入信号条件 - 增强过滤
            buy_condition = False
            
            # 上涨趋势中的买入信号
            if trend_type == 1:
                # 1. 趋势确认：ADX足够强，+DI > -DI
                # 2. Stoch RSI超卖：连续两个周期超卖，且K线向上突破D线
                # 3. 价格确认：价格在移动平均线上方，接近BOLL下轨或已反弹
                if (adx_value > self.params.adx_threshold * 1.2 and plus_di > minus_di * 1.1) and \
                   (stoch_rsi_k < self.params.oversold and stoch_rsi_k_prev < self.params.oversold) and \
                   (stoch_rsi_k > stoch_rsi_d and stoch_rsi_k_prev <= stoch_rsi_d_prev) and \
                   (self.data_close[0] > ma_value and self.data_close[0] >= boll_lower):
                    buy_condition = True
                    
            # 震荡趋势中的买入信号
            elif trend_type == 0:
                # 1. Stoch RSI超卖：连续两个周期超卖，且K线向上突破D线
                # 2. 价格确认：价格在移动平均线上方，接近BOLL下轨
                if (stoch_rsi_k < self.params.oversold and stoch_rsi_k_prev < self.params.oversold) and \
                   (stoch_rsi_k > stoch_rsi_d and stoch_rsi_k_prev <= stoch_rsi_d_prev) and \
                   (self.data_close[0] > ma_value and self.data_close[0] <= boll_lower * 1.01):
                    buy_condition = True
            
            if buy_condition:
                # 计算合适的买入手数，根据趋势强度调整仓位
                if trend_type == 1:  # 上涨趋势
                    position_percent = 0.3  # 使用30%资金买入
                    self.log(f'上涨趋势+Stoch RSI超卖确认，执行买入 | 当前价格: {self.data_close[0]:.2f}')
                else:  # 震荡趋势
                    position_percent = 0.15  # 使用15%资金买入
                    self.log(f'震荡趋势+Stoch RSI超卖确认，执行买入 | 当前价格: {self.data_close[0]:.2f}')
                
                # 临时计算止损价格用于头寸大小计算
                atr_value = self.atr[0]
                temp_atr_stop = self.data_close[0] - self.params.stop_loss_multiplier * atr_value
                temp_max_loss_stop = self.data_close[0] * (1 - self.params.max_loss_per_trade)
                temp_stop_loss = max(temp_atr_stop, temp_max_loss_stop)
                
                # 计算基于风险的头寸大小
                risk_amount = self.broker.getvalue() * self.params.max_loss_per_trade
                position_size = risk_amount / (self.data_close[0] - temp_stop_loss) if self.data_close[0] > temp_stop_loss else 0
                
                # 计算基于资金比例的头寸大小
                capital_amount = self.broker.getvalue() * position_percent
                capital_size = capital_amount / self.data_close[0]
                
                # 取较小的头寸大小（更保守的仓位）
                size = int(min(position_size, capital_size))
                
                if size > 0:
                    self.order = self.buy(size=size)
                else:
                    self.log(f'计算的头寸大小太小，跳过买入 | 风险头寸: {position_size:.2f}, 资金头寸: {capital_size:.2f}')


def main(timeframe='1h'):
    """
    示例主函数，展示如何使用StochRSIStrategy类
    :param timeframe: 时间周期，可选'1h'（小时线）或'15m'（15分钟线）
    """
    # 设置时间范围（2025年1月1日至2025年12月22日）
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 22)

    # 选择要测试的数据源
    # 可以通过命令行参数选择：python stoch_rsi_strategy.py ETH 1h 或 python stoch_rsi_strategy.py BTC 15m
    if len(sys.argv) > 1:
        asset = sys.argv[1].upper()
    else:
        asset = "ETH"  # 默认测试ETH数据
    
    if asset not in ["ETH", "BTC"]:
        print("请选择有效的数据源：ETH 或 BTC")
        return
    
    # 根据命令行参数设置时间周期
    if len(sys.argv) > 2 and sys.argv[2] in ['1h', '15m']:
        timeframe = sys.argv[2]
    
    # 设置数据文件路径
    if asset == "ETH":
        csv_file = f"../data/ETH/ethusdt_{timeframe}_20250101_20251222.csv"
    else:
        csv_file = f"../data/BTC/btcusdt_{timeframe}_20250101_20251222.csv"
    
    print(f"正在测试 {asset} {timeframe} 数据...")
    
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()

    # 设置初始资金
    initial_cash = 1000  # 可以修改这里的初始资金
    cerebro.broker.setcash(initial_cash)

    # 设置交易手续费和杠杆（杠杆为1，即100%保证金）
    cerebro.broker.setcommission(commission=0.001, margin=1.0)

    # 根据时间周期设置数据加载参数
    if timeframe == '1h':
        time_frame = bt.TimeFrame.Minutes
        compression = 60
    elif timeframe == '15m':
        time_frame = bt.TimeFrame.Minutes
        compression = 15
    else:
        time_frame = bt.TimeFrame.Minutes
        compression = 60

    # 加载数据
    data = bt.feeds.GenericCSVData(
        dataname=csv_file,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,  # CSV文件没有持仓量数据，设置为-1
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=time_frame,
        compression=compression,
        headers=True  # 跳过CSV文件的表头行
    )
    cerebro.adddata(data)

    # 添加策略
    cerebro.addstrategy(StochRSIStrategy, printlog=True)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 打印初始资金
    print(f'初始资金: {cerebro.broker.getvalue():.2f}')

    # 运行回测
    results = cerebro.run()

    # 获取分析结果
    strat = results[0]
    sharpe_ratio = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trade_analysis = strat.analyzers.trades.get_analysis()

    # 打印最终资金和分析结果
    final_value = cerebro.broker.getvalue()
    print(f'最终资金: {final_value:.2f}')
    # 使用实际初始资金计算收益率
    print(f'总收益率: {(final_value / initial_cash - 1) * 100:.2f}%')

    if isinstance(sharpe_ratio, dict) and 'sharperatio' in sharpe_ratio:
        print(f"夏普比率: {sharpe_ratio.get('sharperatio', 'N/A')}")
    else:
        print("夏普比率: N/A")

    if hasattr(drawdown, 'max') and hasattr(drawdown.max, 'drawdown'):
        print(f"最大回撤: {drawdown.max.drawdown:.2f}%")
    else:
        print("最大回撤: 0.00%")

    # 安全地检查交易分析数据
    try:
        if hasattr(trade_analysis, 'total') and hasattr(trade_analysis.total, 'total'):
            total_trades = trade_analysis.total.total
            if total_trades > 0:
                # 尝试获取盈利和亏损交易数
                won_trades = 0
                lost_trades = 0

                if hasattr(trade_analysis, 'won') and hasattr(trade_analysis.won, 'total'):
                    won_trades = trade_analysis.won.total

                if hasattr(trade_analysis, 'lost') and hasattr(trade_analysis.lost, 'total'):
                    lost_trades = trade_analysis.lost.total

                win_rate = won_trades / total_trades * 100 if total_trades > 0 else 0
                print(f"交易次数: {total_trades}")
                print(f"盈利次数: {won_trades}")
                print(f"亏损次数: {lost_trades}")
                print(f"胜率: {win_rate:.2f}%")
            else:
                print("交易次数: 0")
                print("没有执行任何交易")
        else:
            print("交易次数: 0")
            print("没有执行任何交易")
    except Exception as e:
        print(f"交易分析出错: {str(e)}")
        print("没有执行任何交易")

    # 绘制图表
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    main()