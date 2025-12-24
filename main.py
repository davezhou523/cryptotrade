import backtrader as bt
import sys
from datetime import datetime
import csv
from config import STRATEGY_PARAMS

from trend.stochasticRSI import StochasticRSI
from trend.trend import TrendDetector

# Binance API配置
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"


class StochRSIStrategy(bt.Strategy):
    """
    结合趋势判断、Stoch RSI指标买卖信号和ATR止损止盈的策略
    使用多时间周期：日线级别判断趋势，1小时级别判断买卖点
    """
    params = (
        # 趋势检测参数
        ('boll_period', STRATEGY_PARAMS['boll_period']),
        ('boll_dev', STRATEGY_PARAMS['boll_dev']),
        ('dmi_period', STRATEGY_PARAMS['dmi_period']),
        ('adx_threshold', STRATEGY_PARAMS['adx_threshold']),

        # Stoch RSI参数 - 优化参数以提高胜率
        ('rsi_period', STRATEGY_PARAMS['rsi_period']),
        ('stoch_period', STRATEGY_PARAMS['stoch_period']),  # 增加周期，减少敏感度
        ('stoch_d_period', STRATEGY_PARAMS['stoch_d_period']),  # 缩短D线周期
        ('oversold', STRATEGY_PARAMS['oversold']),  # 提高超卖阈值，减少买入信号
        ('overbought', STRATEGY_PARAMS['overbought']),  # 降低超买阈值，提前卖出

        # ATR参数
        ('atr_period', STRATEGY_PARAMS['atr_period']),

        # 优化建议
        ('stop_loss_multiplier', STRATEGY_PARAMS['stop_loss_multiplier']),  # 适当扩大止损范围，减少被震荡止损的概率
        ('take_profit_multiplier', STRATEGY_PARAMS['take_profit_multiplier']),  # 适当降低止盈目标，提高盈利交易的胜率

        ('trailing_stop_multiplier', STRATEGY_PARAMS['trailing_stop_multiplier']),

        # 移动平均线参数
        ('ma_period', STRATEGY_PARAMS['ma_period']),  # 增加MA周期，使趋势判断更稳定

        # 风险控制参数 - 优化风险控制
        ('max_loss_per_trade', STRATEGY_PARAMS['max_loss_per_trade']),  # 适当提高单笔最大亏损比例，增加盈利潜力

        ('min_hold_periods', STRATEGY_PARAMS['min_hold_periods']),  # 增加最小持仓时间到3个周期
        ('max_trades_per_day', STRATEGY_PARAMS['max_trades_per_day']),  # 减少每日最大交易次数到1次

        ('printlog', STRATEGY_PARAMS['printlog']),
    )

    def __init__(self):
        # 初始化数据引用
        # datas[0]: 1小时级别数据（用于判断买卖点）
        self.data_1h_close = self.datas[0].close
        self.data_1h_high = self.datas[0].high
        self.data_1h_low = self.datas[0].low
        self.data_1h_open = self.datas[0].open
        self.data_1h_volume = self.datas[0].volume  # 新增成交量引用
        
        # datas[1]: 日线级别数据（用于判断趋势）
        self.data_daily_close = self.datas[1].close
        self.data_daily_high = self.datas[1].high
        self.data_daily_low = self.datas[1].low

        # 初始化日线级别的趋势检测器
        self.trend_detector_daily = TrendDetector(self.datas[1])
        
        # 在1小时数据上初始化买卖点指标
        self.stoch_rsi_1h = StochasticRSI(
            period=self.params.rsi_period,
            stoch_period=self.params.stoch_period,
            dperiod=self.params.stoch_d_period
        )
        
        self.atr_1h = bt.indicators.ATR(
            period=self.params.atr_period
        )
        
        self.ma_1h = bt.indicators.EMA(self.data_1h_close, period=self.params.ma_period)
        self.boll_1h = bt.indicators.BBands(
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )
        
        self.rsi_1h = bt.indicators.RSI(period=self.params.rsi_period)
        
        # 新增：5周期成交量移动平均线
        self.volume_ma_5 = bt.indicators.EMA(self.data_1h_volume, period=5)

        # 跟踪订单状态
        self.order = None
        self.stop_loss = None
        self.take_profit = None
        self.trailing_stop = None
        self.entry_price = None
        self.entry_bar = None

        # 趋势名称映射
        self.trend_names = {
            0: '震荡趋势',
            1: '单边上涨趋势',
            -1: '单边下跌趋势'
        }

        # 跟踪交易数量
        self.trade_count = 0
        self.daily_trade_count = 0
        self.last_trade_date = None

    def log(self, txt, dt=None, doprint=False):
        """Logging function"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交或已接受，不做处理
            return

        if order.status in [order.Completed]:
            # 订单已完成
            if order.isbuy():
                # 买入订单完成
                self.log(f'买入执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                # 初始化持仓变量
                self.entry_price = order.executed.price
                self.entry_bar = len(self.datas[0]) - 1

                # 设置止损止盈
                atr_value = self.atr_1h[0]
                self.stop_loss = self.entry_price - self.params.stop_loss_multiplier * atr_value
                self.take_profit = self.entry_price + self.params.take_profit_multiplier * atr_value
                self.trailing_stop = self.entry_price - self.params.trailing_stop_multiplier * atr_value

                # 更新交易计数
                self.trade_count += 1
                current_date = self.datas[0].datetime.date(0)
                if self.last_trade_date != current_date:
                    self.daily_trade_count = 1
                    self.last_trade_date = current_date
                else:
                    self.daily_trade_count += 1

            else:
                # 卖出订单完成
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f} | 数量: {order.executed.size:.4f}')
                # 重置持仓变量
                self.entry_price = None
                self.entry_bar = None
                self.stop_loss = None
                self.take_profit = None
                self.trailing_stop = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            # 订单被取消、保证金不足或被拒绝
            self.log('订单被取消/保证金不足/被拒绝')

        # 重置订单状态
        self.order = None

    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return

        self.log(f'交易完成 | 利润: {trade.pnl:.2f} | 净利润: {trade.pnlcomm:.2f}')

    def next(self):
        """主策略逻辑，每个数据点执行一次"""
        if self.order:
            return

        # 记录当前价格（1小时级别）
        self.log(f'当前价格: {self.data_1h_close[0]:.2f}')

        # 获取1小时级别的Stoch RSI指标值
        stoch_rsi_k = self.stoch_rsi_1h.percK[0]
        stoch_rsi_d = self.stoch_rsi_1h.percD[0]
        
        # 获取前一周期的Stoch RSI值
        stoch_rsi_k_prev = self.stoch_rsi_1h.percK[-1]
        stoch_rsi_d_prev = self.stoch_rsi_1h.percD[-1]
        
        # 获取1小时级别的技术指标值
        ma_value = self.ma_1h[0]
        atr_value = self.atr_1h[0]
        
        # 获取1小时级别的BOLL指标值
        boll_mid = self.boll_1h.mid[0]
        boll_bot = self.boll_1h.bot[0]
        boll_top = self.boll_1h.top[0]
        
        # 获取1小时级别的RSI指标值
        rsi_value = self.rsi_1h[0]
        if len(self.rsi_1h) > 5:
            rsi_value_prev = self.rsi_1h[-5]
        else:
            rsi_value_prev = rsi_value
            
        # 获取成交量信息
        volume_current = self.data_1h_volume[0]
        volume_ma_5 = self.volume_ma_5[0] if len(self.volume_ma_5) > 0 else volume_current

        # 获取日线级别的趋势类型
        trend_type = self.trend_detector_daily.trend_type[0]
        adx_value = self.trend_detector_daily.dmi.adx[0]

        # 打印调试信息
        self.log(f'日线趋势: {self.trend_names.get(trend_type, "未知")} | 日线ADX: {adx_value:.2f}')
        self.log(f'1小时Stoch RSI: K={stoch_rsi_k:.2f}, D={stoch_rsi_d:.2f}')

        # 检查是否有仓位
        if self.position:
            # 确保entry_bar已初始化
            if self.entry_bar is None:
                self.entry_bar = len(self) - 1  # 假设上一个bar开的仓
            
            # 检查是否达到最小持仓时间
            if len(self.datas[0]) - self.entry_bar < self.params.min_hold_periods:
                self.log(f'未达到最小持仓时间 {self.params.min_hold_periods}，继续持有')
                return
            
            # 更新移动止损 - 根据波动率调整
            if trend_type == 1:  # 上涨趋势
                new_trailing_stop = self.data_1h_close[0] - self.params.trailing_stop_multiplier * atr_value
            elif trend_type == 0:  # 震荡趋势
                new_trailing_stop = self.data_1h_close[0] - 1.8 * atr_value  # 提高震荡趋势的止损幅度
            else:  # 下跌趋势
                new_trailing_stop = self.data_1h_close[0] - 1.2 * atr_value  # 适当提高下跌趋势的止损幅度
            
            if new_trailing_stop > self.trailing_stop:
                self.trailing_stop = new_trailing_stop
                self.log(f'移动止损更新: {self.trailing_stop:.2f}')
            
            # 卖出信号1：Stoch RSI超买且死叉（K线从上向下突破D线）
            if (stoch_rsi_k > self.params.overbought) and (stoch_rsi_k < stoch_rsi_d) and (stoch_rsi_k_prev >= stoch_rsi_d_prev):
                self.log(f'1小时Stoch RSI超买且死叉，执行卖出')
                self.order = self.sell(size=self.position.size)
            
            # 卖出信号2：价格连续两根K线跌破MA且趋势改变
            elif (self.data_1h_close[0] < self.ma_1h[0]) and (self.data_1h_close[-1] < self.ma_1h[-1]) and (trend_type != 1):
                self.log(f'1小时价格连续两根K线跌破MA且趋势改变，执行卖出')
                self.order = self.sell(size=self.position.size)
            
            # 卖出信号3：ATR突破（波动性增加时保护利润）
            elif (self.data_1h_high[0] - self.data_1h_low[0]) > atr_value * 2.5:  # 提高ATR突破阈值
                self.log(f'ATR突破，执行卖出保护利润')
                self.order = self.sell(size=self.position.size)
            
            # 止损检查
            elif self.data_1h_close[0] <= self.stop_loss:
                self.log(f'触发止损，执行卖出')
                self.order = self.sell(size=self.position.size)
            
            # 移动止损检查
            elif self.data_1h_close[0] <= self.trailing_stop:
                self.log(f'触发移动止损，执行卖出')
                self.order = self.sell(size=self.position.size)
            
            # 止盈检查
            elif self.data_1h_close[0] >= self.take_profit:
                self.log(f'触发止盈，执行卖出')
                self.order = self.sell(size=self.position.size)
        
        else:  # 没有仓位，考虑买入
            # 检查每日交易次数限制
            current_date = self.datas[0].datetime.date(0)
            if self.last_trade_date == current_date and self.daily_trade_count >= self.params.max_trades_per_day:
                self.log(f'每日交易次数已达上限 ({self.params.max_trades_per_day}次)')
                return
                
            # 买入信号条件：根据趋势类型调整
            buy_condition = False
            
            # 根据日线趋势类型调整买入条件（1小时级别）
            if trend_type == 1:  # 日线上涨趋势
                # 上涨趋势中需要明确的买入信号
                # Stoch RSI金叉且价格突破MA，同时成交量放大
                # 降低Stoch RSI阈值，增加买入机会
                if (stoch_rsi_k < 50) and (stoch_rsi_k > stoch_rsi_d) and (stoch_rsi_k_prev <= stoch_rsi_d_prev):
                    if (self.data_1h_close[0] > self.ma_1h[0]) and (self.data_1h_close[-1] <= self.ma_1h[-1]):
                        if volume_current > volume_ma_5 * 1.1:  # 适当降低成交量要求
                            buy_condition = True
            elif trend_type == 0:  # 日线震荡趋势
                # 震荡趋势中需要更明确的超卖信号
                if (stoch_rsi_k < 25) and (stoch_rsi_k > stoch_rsi_d) and (stoch_rsi_k_prev <= stoch_rsi_d_prev):
                    if (self.data_1h_close[0] <= boll_bot * 1.01) and (self.data_1h_close[0] > self.ma_1h[0]):
                        # 增加RSI底背离条件
                        if len(self.data_1h_close) > 5 and (self.data_1h_close[0] < self.data_1h_close[-5]) and (rsi_value > rsi_value_prev):
                            if volume_current > volume_ma_5 * 1.1:  # 成交量放大
                                buy_condition = True
            else:  # 日线下跌趋势
                # 下跌趋势中需要非常明确的超卖信号
                if (stoch_rsi_k < 15) and (stoch_rsi_k > stoch_rsi_d) and (stoch_rsi_k_prev <= stoch_rsi_d_prev):
                    if (self.data_1h_close[0] <= boll_bot * 1.005) and (self.data_1h_close[0] > self.ma_1h[0]):
                        if volume_current > volume_ma_5 * 1.3:  # 成交量明显放大
                            buy_condition = True
            
            if buy_condition:
                self.log(f'买入信号确认，执行买入 | 当前价格: {self.data_1h_close[0]:.2f}')
                
                # 计算买入手数 - 允许小数数量
                cash = self.broker.getcash()
                value = self.broker.getvalue()
                
                # 计算基于风险的头寸大小
                risk_amount = value * self.params.max_loss_per_trade
                if atr_value > 0:
                    # 根据市场波动率动态调整仓位
                    if atr_value > (self.atr_1h[-1] * 1.5) and len(self.atr_1h) > 1:
                        # 高波动率时降低仓位
                        position_size_risk = risk_amount / (self.params.stop_loss_multiplier * atr_value) * 0.7
                    else:
                        position_size_risk = risk_amount / (self.params.stop_loss_multiplier * atr_value)
                else:
                    position_size_risk = cash / self.data_1h_close[0]
                
                # 计算基于可用资金的头寸大小（使用更保守的比例）
                cash_size = (cash * 0.7) / self.data_1h_close[0]  # 减少可用资金比例到70%
                
                # 取较小的头寸大小
                position_size = min(position_size_risk, cash_size)
                
                # 移除最小持仓限制，允许购买小数数量
                if position_size > 0.0001:  # 设置一个非常小的最小值，避免极端情况
                    self.log(f'买入数量: {position_size:.4f}')
                    self.order = self.buy(size=position_size)
                else:
                    self.log(f'可用资金不足，无法买入')


# 在main.py中创建数据加载函数
def load_data(asset, timeframe, compression, dataname_format):
    """加载指定时间周期的历史数据"""
    print(f"加载{timeframe}级别数据...")
    return bt.feeds.GenericCSVData(
        dataname=datname_format.format(asset=asset, 
                                      symbol='eth' if asset == 'ETH' else 'btc'),
        datetime=0, open=1, high=2, low=3, close=4, volume=5, openinterest=-1,
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=timeframe, compression=compression,
        headers=True
    )



def main():
    """
    主函数，同时加载日线和1小时数据进行回测
    """
    # 设置时间范围（2025年1月1日至2025年12月22日）
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 22)

    # 选择要测试的数据源
    if len(sys.argv) > 1:
        asset = sys.argv[1].upper()
    else:
        asset = "ETH"  # 默认测试ETH数据
    
    if asset not in ["ETH", "BTC"]:
        print("请选择有效的数据源：ETH 或 BTC")
        return
    
    print(f"正在测试 {asset} 多时间周期数据...")
    
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()

    # 设置初始资金
    initial_cash = 1000  # 可以修改这里的初始资金
    cerebro.broker.setcash(initial_cash)

    # 设置交易手续费和杠杆（杠杆为1，即100%保证金）
    cerebro.broker.setcommission(commission=0.001, margin=1.0)

    # 加载1小时级别数据（用于判断买卖点）
    print("加载1小时级别数据...")
    data_1h = bt.feeds.GenericCSVData(
        dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'btc'}usdt_1h_20250101_20251222.csv",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Minutes,
        compression=60,
        headers=True
    )
    cerebro.adddata(data_1h)  # 1小时数据作为主要数据（datas[0]）

    # 加载日线级别数据（用于判断趋势）
    print("加载日线级别数据...")
    data_daily = bt.feeds.GenericCSVData(
        dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'btc'}usdt_1d_20250101_20251222.csv",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Days,
        compression=1,
        headers=True
    )
    cerebro.adddata(data_daily)  # 日线数据作为次要数据（datas[1]）

    # 添加策略
    # cerebro.addstrategy(StochRSIStrategy, printlog=True)
    cerebro.addstrategy(StochRSIStrategy)

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