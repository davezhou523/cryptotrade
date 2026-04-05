#!/usr/bin/env python3
"""
优化策略测试脚本
测试优化后的仓位管理和5倍杠杆功能
"""

from pathlib import Path
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy3 import Strategy3

# 项目根目录
ROOT = Path(__file__).resolve().parent

# 策略参数配置
PARAMS = dict(
    # 日志控制
    printlog=True,                  # 打印普通日志（每笔交易等）
    eventlog=True,                  # 打印重要事件日志（入场、出场、风控触发等）

    # 周期参数 - 各时间周期的指标参数
    h4_ema_fast=21,                # 4小时图快速EMA周期
    h4_ema_slow=55,                # 4小时图慢速EMA周期
    h1_ema_fast=21,                # 1小时图快速EMA周期
    h1_ema_slow=55,                # 1小时图慢速EMA周期
    h1_rsi_period=14,              # 1小时图RSI周期
    m15_ema_period=21,             # 15分钟图EMA周期（用于出场判断）
    m15_atr_period=14,             # 15分钟图ATR周期（用于止损和仓位计算）
    m15_rsi_period=14,             # 15分钟图RSI周期（用于入场信号）

    # 风控与仓位 - 风险管理和仓位大小计算
    risk_per_trade=0.03,           # 单笔风险，占总资金的3.0%（原1.6%）
    max_position_size=0.55,        # 最大仓位规模（占总资金比例）
    deep_pullback_scale=0.9,       # 深回调轻仓系数，价格接近EMA55时仓位打9折（原6折）
    pullback_deep_band=0.003,      # 贴近EMA55判定带（0.3%），价格与EMA55距离小于此值视为深回调
    stop_loss_atr_multiplier=1.5,  # 止损距离=1.5×ATR（原2.0）
    min_holding_bars=5,            # 最小持仓K线数，避免刚入场就被EMA噪音洗出（原4）
    ema_exit_confirm_bars=2,       # EMA破位连续确认K线数，需连续2根K线确认破位
    ema_exit_buffer_atr=0.30,      # EMA破位缓冲带（ATR倍数），提供一定容错空间（原0.2）

    # 杠杆约束 - 保证金交易参数
    leverage=7.0,                  # 杠杆倍数，7倍杠杆（原5倍）
    max_leverage_ratio=0.92,       # 最大杠杆使用率，不超过保证金的92%（原90%）

    # 风险限制 - 全局风险控制
    max_positions=1,               # 最大同时持仓数，只允许单笔交易
    max_consecutive_losses=3,      # 最大连续亏损次数，达到后暂停交易
    max_daily_loss_pct=0.07,       # 最大日亏损比例（7%），达到后当日停止交易（原5%）
    max_drawdown_pct=0.15,         # 最大回撤比例（15%），达到后仓位规模减半（原10%）
    drawdown_position_scale=0.5,   # 回撤仓位缩放系数，回撤达到阈值时仓位打5折

    # 过滤 - 信号过滤条件
    require_both_entry_signals=False, # 是否需要同时满足结构突破和RSI信号
    h1_rsi_long_low=42,            # 1小时图多头RSI下限，RSI>42才考虑做多
    h1_rsi_long_high=60,           # 1小时图多头RSI上限，RSI<60才考虑做多
    h1_rsi_short_low=40,           # 1小时图空头RSI下限，RSI>40才考虑做空
    h1_rsi_short_high=58,          # 1小时图空头RSI上限，RSI<58才考虑做空
    m15_breakout_lookback=6,       # 15分钟图突破结构回顾期（K线数）
    m15_rsi_bias_long=52,          # 15分钟图多头RSI偏置，RSI>=52视为偏多
    m15_rsi_bias_short=48,         # 15分钟图空头RSI偏置，RSI<=48视为偏空

    # 兼容测试脚本参数
    volatility_scaling=True,       # 波动率缩放，根据市场波动调整仓位
    dynamic_risk_adjustment=True,  # 动态风险调整，根据回撤调整仓位规模
)


def run_year(year: int) -> str:
    """
    运行指定年份的策略回测
    
    参数:
        year (int): 要回测的年份（例如2020）
        
    返回:
        str: 回测输出的文本内容，包含资金曲线、交易统计等结果
        
    功能说明:
        1. 创建Cerebro回测引擎并配置初始资金、佣金、滑点等
        2. 加载三个时间周期（4H、1H、15M）的ETH/USDT数据
        3. 添加Strategy3策略和性能分析器（交易分析、夏普比率、回撤）
        4. 运行回测并收集结果
        5. 输出关键性能指标：最终资金、总收益率、交易次数、胜率、夏普比率、最大回撤
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        # 创建回测引擎
        cerebro = bt.Cerebro()
        # 设置初始资金为10000 USDT（原5000）
        cerebro.broker.setcash(10000.0)
        # 允许做空
        cerebro.broker.set_shortcash(True)
        # 设置交易佣金：0.1%，保证金20%，非股票模式（期货/杠杆交易）
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        # 设置滑点：0.1%
        cerebro.broker.set_slippage_perc(0.001)
        # 启用收盘价交易（Close-Of-Candle），在K线收盘时执行订单
        cerebro.broker.set_coc(True)

        # 多周期数据文件配置：4小时、1小时、15分钟K线数据
        data_files = [
            ("4H", f"data/ETH/binance/ethusdt_4h_{year}0101_{year}1231.csv"),
            ("1H", f"data/ETH/binance/ethusdt_1h_{year}0101_{year}1231.csv"),
            ("15M", f"data/ETH/binance/ethusdt_15m_{year}0101_{year}1231.csv"),
        ]

        # 存储加载的数据对象
        datas = []
        # 遍历所有时间周期，加载CSV数据文件
        for timeframe, filepath in data_files:
            try:
                # 读取CSV文件，解析日期时间列并设为索引
                df = pd.read_csv(ROOT / filepath, parse_dates=["datetime"], index_col="datetime")
                if df.empty:
                    print(f"跳过空数据文件 {timeframe}: {filepath}")
                    continue

                # 将DataFrame转换为Backtrader可用的数据对象
                data = bt.feeds.PandasData(
                    dataname=df,
                    datetime=None,  # 因为已经设置了索引
                    open='open',
                    high='high',
                    low='low',
                    close='close',
                    volume='volume',
                    openinterest=-1
                )
                datas.append(data)
                print(f"成功加载 {timeframe} 数据: {filepath}，共 {len(df)} 行")
            except Exception as exc:
                print(f"加载数据失败 {filepath}: {exc}")

        # 检查是否成功加载了三个时间周期的数据
        if len(datas) < 3:
            print(f"错误: 有效数据不足，期望3个周期(4H/1H/15M)，实际 {len(datas)} 个")
            return buffer.getvalue()

        # 将所有加载的数据添加到回测引擎
        for data in datas:
            cerebro.adddata(data)

        # 添加策略实例，传入参数配置
        cerebro.addstrategy(Strategy3, **PARAMS)
        # 添加交易分析器，统计交易次数、胜率等
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        # 添加夏普比率分析器，评估风险调整后收益
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio_A,
            _name="sharpe",
            timeframe=bt.TimeFrame.Days,
            compression=1,
            riskfreerate=0.0,
            annualize=True,
        )
        # 添加回撤分析器，计算最大回撤
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        # 执行回测
        print("=== 开始优化策略回测 ===")
        results = cerebro.run()

        # 检查回测是否产生结果
        if not results:
            print("回测没有产生结果")
            return buffer.getvalue()

        # 提取策略实例和分析器结果
        strat = results[0]
        trade_analysis = strat.analyzers.trades.get_analysis()
        sharpe_ratio = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()

        # 输出回测结果摘要
        print("\n=== 优化策略回测结果 ===")
        print(f"最终资金: {cerebro.broker.getvalue():.2f}")
        print(f"总收益率: {(cerebro.broker.getvalue() - 5000) / 5000 * 100:.2f}%")

        if "total" in trade_analysis:
            print(f"交易次数: {trade_analysis['total']['total']}")
            if "won" in trade_analysis:
                win_rate = trade_analysis["won"]["total"] / trade_analysis["total"]["total"] * 100
                print(f"胜率: {win_rate:.2f}%")

        sharpe_val = sharpe_ratio.get("sharperatio")
        if sharpe_val is not None:
            print(f"夏普比率: {sharpe_val:.2f}")
        else:
            print("夏普比率: 无足够数据计算")

        if "max" in drawdown:
            print(f"最大回撤: {drawdown['max']['drawdown']:.2f}%")

    return buffer.getvalue()


def test_optimized_strategy():
    """
    主测试函数：运行2020-2025年的策略回测
    
    功能说明:
        1. 遍历2020到2025年（不包含2026）
        2. 对每一年调用run_year函数进行回测
        3. 将回测输出保存到res{year}_2文件中（UTF-16编码）
        4. 打印进度信息
        
    输出文件:
        res2020_2, res2021_2, ..., res2025_2
    """
    # 遍历2020-2025年，逐年回测
    for year in range(2020, 2026):
        # 运行该年份的回测
        output = run_year(year)
        # 将回测结果保存到文件（UTF-16编码）
        (ROOT / f"res{year}_3").write_text(output, encoding="utf-16")
        # 打印进度
        print(f"done {year}")


# 脚本入口：当直接运行此文件时执行主测试函数
if __name__ == "__main__":
    test_optimized_strategy()
