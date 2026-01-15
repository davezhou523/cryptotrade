import backtrader as bt
import sys
from datetime import datetime
from config import STRATEGY_PARAMS
from trend.test import TestStrategy
from trend.tradingStrategy import TradingStrategy
import multiprocessing
from itertools import product
from data.base import get_1h_data, get_daily_data



def run_single_strategy(params):
    """
    运行单个策略实例的函数，用于多进程调用
    """
    rsi_period, stoch_period, fast_ma_period, slow_ma_period, stop_loss_multiplier, take_profit_multiplier = params
    
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    initial_cash = 3000
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.set_shortcash(True)
    
    # 设置交易手续费和滑点
    cerebro.broker.setcommission(commission=0.001, margin=1.0, stocklike=True)
    cerebro.broker.set_slippage_perc(0.001)
    cerebro.broker.set_slippage_fixed(0.01)
    cerebro.broker.set_coc(True)
    
    # 加载数据
    data_1h = get_1h_data("ETH")
    cerebro.adddata(data_1h)
    data_daily = get_daily_data("ETH")
    cerebro.adddata(data_daily)
    
    # 添加策略
    cerebro.addstrategy(TradingStrategy,
                       rsi_period=rsi_period,
                       stoch_period=stoch_period,
                       fast_ma_period=fast_ma_period,
                       slow_ma_period=slow_ma_period,
                       stop_loss_multiplier=stop_loss_multiplier,
                       take_profit_multiplier=take_profit_multiplier
                        )
    
    # 添加分析器
    compression = 60  # 1小时
    # 修改夏普比率分析器配置
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,
                        timeframe=bt.TimeFrame.Days,  # 使用日线时间框架
                        compression=1,
                        riskfreerate=0.02,  # 设置无风险利率
                        annualize=True,  # 年化处理
                        _name='sharpe')

    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # 运行策略
    results = cerebro.run()
    strat = results[0]
    
    # 获取结果
    try:
        # 获取分析结果
        sharpe_ratio = strat.analyzers.sharpe.get_analysis()
        trade_analysis = strat.analyzers.trades.get_analysis()
        
        # 获取最终资金
        final_value = cerebro.broker.getvalue()
        return_pct = (final_value - initial_cash) / initial_cash
        
        # 提取夏普比率值
        if isinstance(sharpe_ratio, dict) and 'sharperatio' in sharpe_ratio:
            sr_value = sharpe_ratio.get('sharperatio', 0)
        else:
            sr_value = 0
        
        # 提取交易统计信息
        if isinstance(trade_analysis, dict):
            total_trades = trade_analysis.get('total', {}).get('total', 0)
        else:
            total_trades = 0
        
        return {
            'params': params,
            'final_value': final_value,
            'return_pct': return_pct,
            'sharpe_ratio': sr_value,
            'total_trades': total_trades
        }
    except Exception as e:
        return {
            'params': params,
            'error': str(e)
        }

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
    ##优化方向
    # 增加更多技术指标：考虑添加MACD、ADX、Volume等指标进行信号验证
    # 优化交易时机：研究最佳的入场和出场时机，减少无效交易
    # 增加机器学习过滤：使用简单的机器学习模型对交易信号进行过滤
    # 回测更长时间周期：使用更多历史数据进行回测，验证策略的稳定性
    # 增加市场环境判断：根据市场波动率、趋势强度等因素调整交易策略
    #
    # 定义要优化的参数范围
    # 修改参数范围
    # rsi_periods = range(7, 15, 2)  # 7-14周期，步长2
    # stoch_periods = range(5, 12, 2)  # 5-11周期，步长2
    # fast_ma_periods = range(3, 9, 2)  # 3-9周期，步长2
    # slow_ma_periods = range(10, 24, 3)  # 10-24周期，步长3
    # stop_loss_multipliers = [1.0, 1.5]  # 止损倍数
    # take_profit_multipliers = [2.0, 2.5]  # 止盈倍数

    #回测后参数:
    #参数: (11, 7, 7, 19, 1.0, 2.0)
    rsi_periods = range(11, 12, 2)  # 7-14周期，步长2
    stoch_periods = range(7, 8, 2)  # 5-11周期，步长2
    fast_ma_periods = range(7, 8, 2)  # 3-9周期，步长2
    slow_ma_periods = range(19, 20, 3)  # 10-24周期，步长3
    stop_loss_multipliers = [1.0]  # 止损倍数
    take_profit_multipliers = [2.0]  # 止盈倍数

    # 生成所有参数组合
    all_params = list(product(
        rsi_periods,
        stoch_periods,
        fast_ma_periods,
        slow_ma_periods,
        stop_loss_multipliers,
        take_profit_multipliers
    ))
    
    print(f"总共需要测试 {len(all_params)} 个参数组合")
    
    # 使用多进程运行参数优化
    num_processes = multiprocessing.cpu_count()  # 使用所有可用CPU核心
    print(f"使用 {num_processes} 个进程运行参数优化...")
    
    with multiprocessing.Pool(processes=num_processes) as pool:
        results = pool.map(run_single_strategy, all_params)
    
    # 处理结果
    print("\n参数优化结果：")
    print("=" * 60)
    
    best_return = -float('inf')
    best_result = None
    
    for result in results:
        if 'error' in result:
            print(f"参数组合 {result['params']} 运行失败: {result['error']}")
            continue
        
        print(f"\n参数组合: {result['params']}")
        print(f"  最终资金: {result['final_value']:.2f}")
        print(f"  总收益率: {result['return_pct']:.4f}")
        print(f"  夏普比率: {result['sharpe_ratio']:.4f}")
        print(f"  交易次数: {result['total_trades']}")
        
        if result['return_pct'] > best_return:
            best_return = result['return_pct']
            best_result = result
    
    print("\n最佳参数组合：")
    if best_result:
        print(f"  参数: {best_result['params']}")
        print(f"  最终资金: {best_result['final_value']:.2f}")
        print(f"  总收益率: {best_result['return_pct']:.4f}")
        print(f"  夏普比率: {best_result['sharpe_ratio']:.4f}")
        print(f"  交易次数: {best_result['total_trades']}")
    else:
        print("没有找到有效的参数组合")

if __name__ == '__main__':
    # 在main.py中添加滑点设置
    main()