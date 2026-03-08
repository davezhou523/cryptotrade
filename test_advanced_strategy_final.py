import backtrader as bt
from trend.advanced_strategy import AdvancedStrategy
from data.base import get_crypto_data


def run_strategy():
    """运行高级多周期策略"""
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()

    # 设置初始资金
    initial_cash = 10000
    cerebro.broker.setcash(initial_cash)

    # 设置交易手续费和滑点
    cerebro.broker.setcommission(commission=0.001, margin=1.0, stocklike=True)
    cerebro.broker.set_slippage_perc(0.001)
    cerebro.broker.set_slippage_fixed(0.01)
    cerebro.broker.set_coc(True)
    # 加载不同时间周期的数据
    symbol = "ETH"
    start_year = 2025
    end_year = 2025

    # 按照时间周期从长到短的顺序添加数据
    # 1. 周线数据
    data_weekly = get_crypto_data(symbol, "1w", 2024, end_year)
    cerebro.adddata(data_weekly, name="weekly")

    # 2. 日线数据
    data_daily = get_crypto_data(symbol, "1d", 2024, end_year)
    cerebro.adddata(data_daily, name="daily")

    # 3. 4H数据
    data_4h = get_crypto_data(symbol, "4h", 2024, end_year)
    cerebro.adddata(data_4h, name="4h")

    # 4. 1H数据
    data_1h = get_crypto_data(symbol, "1h", start_year, end_year)
    cerebro.adddata(data_1h, name="1h")

    # 添加策略
    cerebro.addstrategy(AdvancedStrategy)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    # 运行策略
    print(f"\n初始资金: {initial_cash:.2f}")
    results = cerebro.run()
    strat = results[0]

    # 获取分析结果
    sharpe_ratio = strat.analyzers.sharpe.get_analysis()
    trade_analysis = strat.analyzers.trades.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()

    # 计算最终资金
    final_value = cerebro.broker.getvalue()
    return_pct = (final_value - initial_cash) / initial_cash

    # 打印结果
    print(f"最终资金: {final_value:.2f}")
    print(f"总收益率: {return_pct:.4f}")
    
    # 安全获取夏普比率
    sharpe_value = 0
    if sharpe_ratio is not None:
        sharpe_value = sharpe_ratio.get('sharperatio', 0)
    # 确保sharpe_value是一个数字
    if sharpe_value is None:
        sharpe_value = 0
    print(f"夏普比率: {sharpe_value:.4f}")
    
    # 安全获取交易次数
    trade_count = 0
    if trade_analysis is not None:
        trade_count = trade_analysis.get('total', {}).get('total', 0)
    print(f"交易次数: {trade_count}")
    
    # 安全获取最大回撤
    max_drawdown = 0
    if drawdown is not None:
        max_drawdown = drawdown.get('max', {}).get('drawdown', 0)
    print(f"最大回撤: {max_drawdown:.4f}%")


if __name__ == "__main__":
    run_strategy()