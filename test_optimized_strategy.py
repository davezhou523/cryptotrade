#!/usr/bin/env python3
"""
优化策略测试脚本
测试优化后的仓位管理和5倍杠杆功能
"""

import backtrader as bt
import pandas as pd
from datetime import datetime
from trend.multi_period_strategy import MultiPeriodStrategy

def test_optimized_strategy():
    """测试优化后的策略"""
    
    # 创建回测引擎
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(5000.0)
    
    # 添加多周期数据
    # 使用2025年ETH数据
    data_files = [
        ('4H', 'data/ETH/ethusdt_4h_20250101_20251231.csv'),
        ('1H', 'data/ETH/ethusdt_1h_20250101_20251231.csv'),
        ('15M', 'data/ETH/ethusdt_15m_20250101_20251231.csv')
    ]
    
    datas = []
    for timeframe, filepath in data_files:
        try:
            # 读取CSV数据
            df = pd.read_csv(filepath, parse_dates=['datetime'], index_col='datetime')
            
            # 创建数据源
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,  # 使用索引作为时间
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume'
            )
            datas.append(data)
            print(f"成功加载 {timeframe} 数据: {filepath}")
        except Exception as e:
            print(f"加载数据失败 {filepath}: {e}")
            # 如果某个周期数据不存在，使用其他周期数据
            continue
    
    if not datas:
        print("错误: 没有找到可用的数据文件")
        return
    
    # 添加数据到回测引擎
    for data in datas:
        cerebro.adddata(data)
    
    # 设置策略参数
    cerebro.addstrategy(
        MultiPeriodStrategy,
        # 优化参数
        risk_per_trade=0.015,  # 1.5%风险
        leverage=5.0,          # 5倍杠杆
        max_leverage_ratio=0.8, # 最大杠杆使用率80%
        volatility_scaling=True, # 波动性仓位调整
        dynamic_risk_adjustment=True, # 动态风险调整
        printlog=True,         # 打印详细日志
        eventlog=True         # 记录重要事件
    )
    
    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    
    # 运行回测
    print("=== 开始优化策略回测 ===")
    try:
        results = cerebro.run()
        
        if results:
            # 分析结果
            strat = results[0]
            
            # 获取分析器结果
            trade_analysis = strat.analyzers.trades.get_analysis()
            sharpe_ratio = strat.analyzers.sharpe.get_analysis()
            drawdown = strat.analyzers.drawdown.get_analysis()
            
            # 打印关键指标
            print("\n=== 优化策略回测结果 ===")
            print(f"最终资金: {cerebro.broker.getvalue():.2f}")
            print(f"总收益率: {(cerebro.broker.getvalue() - 5000) / 5000 * 100:.2f}%")
            
            if 'total' in trade_analysis:
                print(f"交易次数: {trade_analysis['total']['total']}")
                if 'won' in trade_analysis:
                    print(f"胜率: {trade_analysis['won']['total'] / trade_analysis['total']['total'] * 100:.2f}%")
            
            sharpe_val = sharpe_ratio.get('sharperatio')
            if sharpe_val is not None:
                print(f"夏普比率: {sharpe_val:.2f}")
            else:
                print("夏普比率: 无足够数据计算")
            
            if 'max' in drawdown:
                print(f"最大回撤: {drawdown['max']['drawdown']:.2f}%")
        else:
            print("回测没有产生结果")
            
    except Exception as e:
        print(f"回测过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_optimized_strategy()