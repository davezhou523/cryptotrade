import backtrader as bt
import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta
from data import BinanceDataFetcher

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
        self.dmi = bt.indicators.DirectionalMovement(self.data, period=self.params.period)
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
        self.dmi = DMI(self.data, period=self.params.dmi_period)
        self.boll = bt.indicators.BBands(
            self.data,
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


class TrendStrategy(bt.Strategy):
    """
    使用TrendDetector的示例策略
    """
    params = (
        ('boll_period', 20),
        ('boll_dev', 2),
        ('dmi_period', 14),
        ('adx_threshold', 25),
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

        # 初始化趋势检测器
        self.trend_detector = TrendDetector(
            self.datas[0],
            boll_period=self.params.boll_period,
            boll_dev=self.params.boll_dev,
            dmi_period=self.params.dmi_period,
            adx_threshold=self.params.adx_threshold
        )

        # 跟踪订单状态
        self.order = None
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
            else:
                self.log(f'卖出执行 | 价格: {order.executed.price:.2f}')

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

        # 打印趋势判断结果
        self.log(f'趋势判断: {trend_name}', doprint=True)

        # 示例交易逻辑（可根据需要修改）
        if not self.position:
            # 没有仓位，根据趋势类型决定是否买入
            if trend_type == 1:  # 单边上涨趋势
                self.log(f'单边上涨趋势，执行买入 | 当前价格: {self.data_close[0]:.2f}')
                # 计算合适的买入手数，避免资金不足
                size = int(self.broker.getvalue() / self.data_close[0] * 0.9)  # 使用90%资金买入
                self.order = self.buy(size=size if size > 0 else 1)
        else:
            # 持有仓位，根据趋势类型决定是否卖出
            if trend_type == -1:  # 单边下跌趋势
                self.log(f'单边下跌趋势，执行卖出 | 当前价格: {self.data_close[0]:.2f}')
                self.order = self.sell(size=self.position.size)
            elif trend_type == 0:  # 震荡趋势，可考虑止盈
                if self.position.price * 1.03 <= self.data_close[0]:  # 盈利3%以上
                    self.log(f'震荡趋势，盈利3%以上，执行止盈 | 当前价格: {self.data_close[0]:.2f}')
                    self.order = self.sell(size=self.position.size)


# 示例：如何使用这个趋势判断类
def main():
    """
    示例主函数，展示如何使用TrendDetector类
    """
    # 设置时间范围（2025年1月1日至2025年12月22日）
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 22)

    # 选择要测试的数据源
    # 可以通过命令行参数选择：python trend.py ETH 或 python trend.py BTC
    # 或者直接修改下面的变量
    if len(sys.argv) > 1:
        asset = sys.argv[1].upper()
    else:
        asset = "ETH"  # 默认测试ETH数据
    
    if asset not in ["ETH", "BTC"]:
        print("请选择有效的数据源：ETH 或 BTC")
        return
    
    # 设置数据文件路径
    if asset == "ETH":
        csv_file = "./data/ETH/ethusdt_1d_20250101_20251222.csv"
    else:
        csv_file = "./data/BTC/btcusdt_1d_20250101_20251222.csv"
    
    print(f"正在测试 {asset} 的日线数据...")
    
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()

    # 设置初始资金
    initial_cash = 1000  # 可以修改这里的初始资金
    cerebro.broker.setcash(initial_cash)

    # 设置交易手续费
    cerebro.broker.setcommission(commission=0.001)

    # 加载数据 - 日线数据配置
    data = bt.feeds.GenericCSVData(
        dataname=csv_file,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,  # 我们的CSV文件没有持仓量数据，设置为-1
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Days,  # 日线数据
        compression=1,  # 日线数据的压缩比为1
        headers=True  # 跳过CSV文件的表头行
    )
    cerebro.adddata(data)

    # 添加策略
    cerebro.addstrategy(TrendStrategy, printlog=True)

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
    cerebro.plot(style='candlestick')


if __name__ == '__main__':
    main()