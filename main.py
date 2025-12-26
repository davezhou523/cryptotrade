import backtrader as bt
import sys
from datetime import datetime
from config import STRATEGY_PARAMS

from trend.stochasticRSI import StochasticRSI
from trend.tradingStrategy import TradingStrategy
from trend.trend import TrendDetector

# Binance API配置
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"

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
    time_period = 240
    # 设置初始资金
    initial_cash = 1000  # 可以修改这里的初始资金
    cerebro.broker.setcash(initial_cash)

    # 设置交易手续费和杠杆（杠杆为1，即100%保证金）
    cerebro.broker.setcommission(commission=0.001, margin=1.0)
    # 或设置百分比滑点（基于价格的百分比）
    cerebro.broker.set_slippage_perc(0.001)  # 1‰的滑点
    # 加载1小时级别数据（用于判断买卖点）
    # print("加载1小时级别数据...")
    # data_1h = bt.feeds.GenericCSVData(
    #     dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'btc'}usdt_1h_20250101_20251222.csv",
    #     datetime=0,
    #     open=1,
    #     high=2,
    #     low=3,
    #     close=4,
    #     volume=5,
    #     openinterest=-1,
    #     dtformat='%Y-%m-%d %H:%M:%S',
    #     timeframe=bt.TimeFrame.Minutes,
    #     compression=60,
    #     headers=True
    # )
    # cerebro.adddata(data_1h)  # 1小时数据作为主要数据（datas[0]）

    # 加载4小时级别数据（用于判断买卖点）
    print("加载4小时级别数据...")
    data_4h = bt.feeds.GenericCSVData(
        dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'btc'}usdt_4h_20250101_20251222.csv",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Minutes,
        compression=time_period,  # 4小时 = 240分钟
        headers=True
    )
    cerebro.adddata(data_4h)  # 4小时数据作为主要数据（datas[0]）

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
    # cerebro.addstrategy(TradingStrategy, time_period='4h')  # 例如使用4小时周期
    # 优化后的参数测试（减少到约400种组合）
    # 第一阶段：只测试核心参数
    cerebro.optstrategy(
        TradingStrategy,
        time_period=['4h'],
        rsi_period=range(12, 20),  # 重点测试RSI周期
        stoch_period=14,  # 固定为常用值
        fast_ma_period=12,  # 固定
        slow_ma_period=50,  # 固定
        stop_loss_multiplier=3,  # 固定
        take_profit_multiplier=4  # 固定
    )

    # 添加分析器
    # 修改夏普比率分析器配置，添加timeframe参数
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Minutes, compression=time_period, _name='sharpe')

    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 打印初始资金
    print(f'初始资金: {cerebro.broker.getvalue():.2f}')

    # 运行回测 - 禁用多进程，避免序列化错误
    results = cerebro.run(maxcpus=1)  # 使用单进程运行参数优化

    # 获取分析结果 - 处理参数优化的结果格式（列表的列表）
    print("\n参数优化结果：")
    print("=" * 60)
    
    best_sharpe = -float('inf')
    best_params = None
    best_result = None
    
    # 遍历所有参数组合的结果
    for i, result_list in enumerate(results):
        # 每个参数组合对应一个结果列表
        strat = result_list[0]  # 每个参数组合只有一个策略实例
        
        # 获取当前参数组合
        params = strat.params
        
        try:
            # 获取分析结果
            sharpe_ratio = strat.analyzers.sharpe.get_analysis()
            drawdown = strat.analyzers.drawdown.get_analysis()
            trade_analysis = strat.analyzers.trades.get_analysis()
            
            # 获取最终资金
            final_value = cerebro.broker.getvalue()
            total_return = (final_value / initial_cash - 1) * 100
            
            # 提取夏普比率值
            if isinstance(sharpe_ratio, dict) and 'sharperatio' in sharpe_ratio:
                sr_value = sharpe_ratio.get('sharperatio', 0)
            else:
                sr_value = 0
            
            # 打印当前参数组合的结果
            print(f"\n参数组合 {i+1}:")
            print(f"  RSI周期: {params.rsi_period}")
            print(f"  最终资金: {final_value:.2f}")
            print(f"  总收益率: {total_return:.2f}%")
            
            if sr_value != 0:
                print(f"  夏普比率: {sr_value:.2f}")
            else:
                print(f"  夏普比率: N/A")
            
            if hasattr(drawdown, 'max') and hasattr(drawdown.max, 'drawdown'):
                print(f"  最大回撤: {drawdown.max.drawdown:.2f}%")
            else:
                print(f"  最大回撤: 0.00%")
            
            # 更新最佳参数
            if sr_value > best_sharpe:
                best_sharpe = sr_value
                best_params = params
                best_result = result_list
        
        except Exception as e:
            print(f"\n参数组合 {i+1} 分析失败: {str(e)}")
    
    # 打印最佳参数组合
    if best_params is not None:
        print("\n" + "=" * 60)
        print("最佳参数组合:")
        print(f"  RSI周期: {best_params.rsi_period}")
        print(f"  夏普比率: {best_sharpe:.2f}")
        print("=" * 60)

    # 绘制图表
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    # 在main.py中添加滑点设置
    main()