import backtrader as bt
import sys
from datetime import datetime
import csv
from config import STRATEGY_PARAMS

from trend.stochasticRSI import StochasticRSI
from trend.tradingStrategy import TradingStrategy
from trend.trend import TrendDetector

# Binance API配置
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"

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
    cerebro.addstrategy(TradingStrategy)

    # 添加分析器
    # 修改夏普比率分析器配置，添加timeframe参数
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Minutes, compression=60, _name='sharpe')

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
        sr_value = sharpe_ratio.get('sharperatio', 'N/A')
        # 检查是否为有效数值，保留2位小数
        if sr_value != 'N/A' and sr_value is not None:
            print(f"夏普比率: {sr_value:.2f}")
        else:
            print("夏普比率: N/A")
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