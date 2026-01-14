import backtrader as bt
import sys
from datetime import datetime
from config import STRATEGY_PARAMS
from trend.test import TestStrategy

from trend.tradingStrategy import TradingStrategy

# Binance API配置
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"

def get_1h_data(asset):
    """
    获取1小时级别数据
    """
    return bt.feeds.GenericCSVData(
        dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'BTC'}usdt_1h_20250101_20251222.csv",
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

def get_daily_data(asset):
    """
    获取日线级别数据
    """
    return bt.feeds.GenericCSVData(
        dataname=f"data/{asset}/{'eth' if asset == 'ETH' else 'BTC'}usdt_1d_20250101_20251222.csv",
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,
        dtformat='%Y-%m-%d %H:%M:%S',  # 修正日期时间格式，包含时间部分
        timeframe=bt.TimeFrame.Days,
        compression=1,
        headers=True
    )
def main():
    """
    主函数，同时加载日线和1小时数据进行回测
    """
    # 设置时间范围（2025年1月1日至2025年12月22日）
    global final_value, total_return
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
    cerebro.broker.set_shortcash(True)  # 允许用现金做空
    # 设置交易手续费和杠杆（杠杆为1，即100%保证金）
    cerebro.broker.setcommission(commission=0.001, margin=1.0)
    # 或设置百分比滑点（基于价格的百分比）
    cerebro.broker.set_slippage_perc(0.001)  # 1‰的滑点
    cerebro.broker.set_slippage_fixed(0.01)  # 固定滑点
    # 关键设置：使用收盘价成交
    cerebro.broker.set_coc(True)
    # 加载1小时级别数据（用于判断买卖点）
    print("加载1小时级别数据...")
    data_1h = get_1h_data(asset)
    cerebro.adddata(data_1h)  # 1小时数据作为主要数据（datas[0]）
    # 加载日线级别数据（用于判断趋势）
    data_daily = get_daily_data(asset)
    cerebro.adddata(data_daily)  # 日线数据作为次要数据（datas[1]）
    # cerebro.addstrategy(TestStrategy)
    # results = cerebro.run(maxcpus=1)
    # return
    # 添加策略
    # cerebro.addstrategy(TradingStrategy, time_period='4h')  # 例如使用4小时周期
    # 优化后的参数测试（减少到约400种组合）
    # 第一阶段：只测试核心参数
    optimization_time_period = '1h'  # 与optstrategy中的配置一致
    # 根据时间周期设置压缩率
    if optimization_time_period == '1h':
        compression = 60
    elif optimization_time_period == '4h':
        compression = 240
    else:
        compression = 60  # 默认1小时
    # 定义要优化的参数范围
    opt_params = {
        'rsi_period': range(10, 11),
        'stoch_period': range(8,9),
        'fast_ma_period': range(5, 6, 1),
        'slow_ma_period': range(15, 16, 2),
        'stop_loss_multiplier': [1.5],
        'take_profit_multiplier': [3.0]
    }

    cerebro.optstrategy(TradingStrategy, **opt_params)

    # 添加分析器
    # 修改夏普比率分析器配置，添加timeframe参数
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, timeframe=bt.TimeFrame.Minutes, compression=compression, _name='sharpe')

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
    best_return = -float('inf')

    # 遍历所有参数组合的结果
    for i, result_list in enumerate(results):
        # 每个参数组合对应一个结果列表
        for strat in result_list:
            # 尝试通过分析器获取结果
            try:
                # 获取策略参数
                params = strat.params
                params_dict = params.__dict__

                # 使用分析器获取交易结果
                if hasattr(strat, 'analyzers') and hasattr(strat.analyzers, 'trades'):
                    trade_analysis = strat.analyzers.trades.get_analysis()
                    total_trades = trade_analysis.get('total', {}).get('total', 0)
                else:
                    total_trades = 0

                # 直接使用初始资金和cerebro.broker.getvalue()获取最终资金
                # 注意：在参数优化模式下，cerebro.broker.getvalue()可能不是最新的
                # 我们需要找到一种更可靠的方式来获取最终资金
                # 对于这个问题，我们可以改用单个策略实例来运行回测

                # 暂时使用cerebro.broker.getvalue()作为最终资金
                final_value = cerebro.broker.getvalue()
                return_pct = (final_value - initial_cash) / initial_cash

                print(f"\n参数组合 {i + 1}:")
                print(f"  参数: {params_dict}")
                print(f"  最终资金: {final_value:.2f}")
                print(f"  总收益率: {return_pct:.2f}%")
                print(f"  交易次数: {total_trades}")

                if return_pct > best_return:
                    best_return = return_pct
                    best_result = {
                        'params': params_dict,
                        'final_value': final_value,
                        'return_pct': return_pct,
                        'total_trades': total_trades
                    }

            except Exception as e:
                print(f"\n参数组合 {i + 1} 分析失败: {str(e)}")

    print("\n最佳参数组合：")
    print(best_result)

    # 遍历所有参数组合的结果
    # for i, result_list in enumerate(results):
    #     # 每个参数组合对应一个结果列表
    #     strat = result_list[0]  # 每个参数组合只有一个策略实例
    #
    #     # 获取当前参数组合
    #     params = strat.params
    #     params_str = f"RSI周期: {params.rsi_period}, 快速MA周期: {params.fast_ma_period}, 慢速MA周期: {params.slow_ma_period}"
    #     print(params_str)
    #     try:
    #         # 获取分析结果
    #         sharpe_ratio = strat.analyzers.sharpe.get_analysis()
    #         drawdown = strat.analyzers.drawdown.get_analysis()
    #         trade_analysis = strat.analyzers.trades.get_analysis()
    #
    #         # 获取最终资金
    #         final_value = cerebro.broker.getvalue()
    #         total_return = (final_value / initial_cash - 1) * 100
    #
    #         # 提取夏普比率值
    #         if isinstance(sharpe_ratio, dict) and 'sharperatio' in sharpe_ratio:
    #             sr_value = sharpe_ratio.get('sharperatio', 0)
    #         else:
    #             sr_value = 0
    #
    #         # 提取交易统计信息
    #         total_trades = 0
    #         winning_trades = 0
    #         losing_trades = 0
    #         win_rate = 0.0
    #
    #         if isinstance(trade_analysis, dict):
    #             total_trades = trade_analysis.get('total', {}).get('total', 0)
    #             winning_trades = trade_analysis.get('won', {}).get('total', 0)
    #             losing_trades = trade_analysis.get('lost', {}).get('total', 0)
    #
    #             # 计算胜率
    #             if total_trades > 0:
    #                 win_rate = (winning_trades / total_trades) * 100
    #
    #         # 打印当前参数组合的结果
    #         print(f"\n参数组合 {i+1}:")
    #         print(f"  RSI周期: {params.rsi_period}")
    #         print(f"  最终资金: {final_value:.2f}")
    #         print(f"  总收益率: {total_return:.2f}%")
    #
    #         if sr_value != 0:
    #             print(f"  夏普比率: {sr_value:.2f}")
    #         else:
    #             print(f"  夏普比率: N/A")
    #
    #         if hasattr(drawdown, 'max') and hasattr(drawdown.max, 'drawdown'):
    #             print(f"  最大回撤: {drawdown.max.drawdown:.2f}%")
    #         else:
    #             print(f"  最大回撤: 0.00%")
    #
    #         # 新增：打印交易统计信息
    #         print(f"  交易次数: {total_trades}")
    #         print(f"  盈利次数: {winning_trades}")
    #         print(f"  亏损次数: {losing_trades}")
    #         print(f"  胜率: {win_rate:.2f}%")
    #
    #         # 更新最佳参数
    #         if sr_value > best_sharpe:
    #             best_sharpe = sr_value
    #             best_params = params
    #             best_result = result_list
    #             # 保存最佳结果的交易统计信息
    #             best_final_value = final_value
    #             best_total_return = total_return
    #             best_total_trades = total_trades
    #             best_winning_trades = winning_trades
    #             best_losing_trades = losing_trades
    #             best_win_rate = win_rate
    #
    #     except Exception as e:
    #         print(f"\n参数组合 {i+1} 分析失败: {str(e)}")
    #
    # # 打印最佳参数组合
    # if best_params is not None:
    #     print("\n" + "=" * 80)
    #     print("最佳参数组合:")
    #     print(f"  最终资金: {best_final_value:.2f}")
    #     print(f"  总收益率: {best_total_return:.2f}%")
    #     print(f"  夏普比率: {best_sharpe:.2f}")
    #     if hasattr(drawdown, 'max') and hasattr(drawdown.max, 'drawdown'):
    #         print(f"  最大回撤: {drawdown.max.drawdown:.2f}%")
    #     else:
    #         print(f"  最大回撤: 0.00%")
    #     print(f"  交易次数: {best_total_trades}")
    #     print(f"  盈利次数: {best_winning_trades}")
    #     print(f"  亏损次数: {best_losing_trades}")
    #     print(f"  胜率: {best_win_rate:.2f}%")
    #     print(f"  参数配置: RSI周期={best_params.rsi_period}, 时间周期={best_params.time_period}")
    #     print("=" * 80)

    # 绘制图表
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    # 在main.py中添加滑点设置
    main()