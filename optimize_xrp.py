#!/usr/bin/env python3
"""
XRP 专项参数优化脚本
独立于 test_strategy3.py，不影响其他币种的默认参数

问题诊断:
    XRP 默认参数下夏普比率低，核心问题:
    - 2020/2023 胜率仅 40.5%/25%，假信号过多
    - require_both_entry_signals=False 导致结构突破或RSI任一触发即入场
    - XRP 波动大，1.5×ATR 止损太窄，频繁被扫
    - 7倍杠杆对 XRP 风险敞口过大

优化方向:
    1. 入场信号收紧 → require_both_entry_signals=True
    2. RSI 区间收窄 → 减少弱信号入场
    3. 止损加宽 → 适应 XRP 高波动
    4. 杠杆降低 → 控制风险敞口
"""

from pathlib import Path
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy3 import Strategy3

# 项目根目录
ROOT = Path(__file__).resolve().parent

# 每个币种的初始资金（USDT）
INITIAL_CASH = 10000.0

# 回测年份范围
START_YEAR = 2020
END_YEAR = 2025


# ======================== XRP 专用参数组 ========================

# 默认参数（与 test_strategy3.py 保持一致，作为基准对比）
DEFAULT_PARAMS = dict(
    printlog=False, eventlog=False,
    h4_ema_fast=21, h4_ema_slow=55,
    h1_ema_fast=21, h1_ema_slow=55, h1_rsi_period=14,
    m15_ema_period=21, m15_atr_period=14, m15_rsi_period=14,
    risk_per_trade=0.03, max_position_size=0.55,
    deep_pullback_scale=0.9, pullback_deep_band=0.003,
    stop_loss_atr_multiplier=1.5, min_holding_bars=5,
    ema_exit_confirm_bars=2, ema_exit_buffer_atr=0.30,
    leverage=7.0, max_leverage_ratio=0.92,
    max_positions=1, max_consecutive_losses=3,
    max_daily_loss_pct=0.07, max_drawdown_pct=0.15,
    drawdown_position_scale=0.5,
    require_both_entry_signals=False,
    h1_rsi_long_low=42, h1_rsi_long_high=60,
    h1_rsi_short_low=40, h1_rsi_short_high=58,
    m15_breakout_lookback=6,
    m15_rsi_bias_long=52, m15_rsi_bias_short=48,
    volatility_scaling=True, dynamic_risk_adjustment=True,
)

# XRP 优化参数组 A：入场过滤收紧 + 止损加宽
XRP_PARAMS_A = dict(DEFAULT_PARAMS,
    # 入场信号：要求结构突破+RSI同时满足，减少假信号
    require_both_entry_signals=True,
    # 1H RSI 区间收窄，只在更强动量时入场
    h1_rsi_long_low=45, h1_rsi_long_high=58,
    h1_rsi_short_low=42, h1_rsi_short_high=56,
    # 15M RSI 偏置更严格
    m15_rsi_bias_long=54, m15_rsi_bias_short=46,
    # 止损加宽，适应 XRP 高波动
    stop_loss_atr_multiplier=2.0,
    # 降低杠杆和风险
    leverage=5.0, risk_per_trade=0.02,
    # EMA 缓冲带加宽
    ema_exit_buffer_atr=0.40,
)

# XRP 优化参数组 B：仅入场过滤收紧（保守调整）
XRP_PARAMS_B = dict(DEFAULT_PARAMS,
    require_both_entry_signals=True,
    stop_loss_atr_multiplier=2.0,
    leverage=5.0,
    risk_per_trade=0.02,
)

# XRP 优化参数组 C：仅降低风险敞口（最小改动）
XRP_PARAMS_C = dict(DEFAULT_PARAMS,
    stop_loss_atr_multiplier=2.0,
    leverage=5.0,
    risk_per_trade=0.02,
    ema_exit_buffer_atr=0.40,
)

# 所有待对比的参数组
PARAM_GROUPS = {
    "默认(基准)": DEFAULT_PARAMS,
    "A-全面收紧": XRP_PARAMS_A,
    "B-仅入场过滤": XRP_PARAMS_B,
    "C-仅降风险": XRP_PARAMS_C,
}


# ======================== 回测逻辑 ========================


def buildDataFilePaths(year: int) -> list:
    """构建 XRP 三个周期的 CSV 数据文件路径"""
    yearStart = f"{year}0101"
    yearEnd = f"{year}1231"
    return [
        ("4H", f"data/XRP/binance/xrpusdt_4h_{yearStart}_{yearEnd}.csv"),
        ("1H", f"data/XRP/binance/xrpusdt_1h_{yearStart}_{yearEnd}.csv"),
        ("15M", f"data/XRP/binance/xrpusdt_15m_{yearStart}_{yearEnd}.csv"),
    ]


def loadMultiPeriodData(dataFilePaths: list) -> list | None:
    """加载多周期K线数据"""
    datas = []
    for timeframe, filepath in dataFilePaths:
        fullPath = ROOT / filepath
        try:
            df = pd.read_csv(fullPath, parse_dates=["datetime"], index_col="datetime")
            if df.empty:
                return None
            data = bt.feeds.PandasData(
                dataname=df, datetime=None,
                open='open', high='high', low='low',
                close='close', volume='volume', openinterest=-1
            )
            datas.append(data)
        except Exception:
            return None
    return datas if len(datas) >= 3 else None


def runBacktest(params: dict, year: int) -> dict | None:
    """
    运行单年 XRP 回测

    :param params: 策略参数字典
    :param year: 回测年份
    :return: 结果字典 或 None
    """
    dataFilePaths = buildDataFilePaths(year)
    strategyParams = dict(params)
    strategyParams['printlog'] = False
    strategyParams['eventlog'] = False

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(INITIAL_CASH)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        datas = loadMultiPeriodData(dataFilePaths)
        if datas is None:
            return None

        for data in datas:
            cerebro.adddata(data)

        cerebro.addstrategy(Strategy3, **strategyParams)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio_A,
            _name="sharpe", timeframe=bt.TimeFrame.Days,
            compression=1, riskfreerate=0.0, annualize=True,
        )
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        results = cerebro.run()
        if not results:
            return None

        strat = results[0]
        tradeAnalysis = strat.analyzers.trades.get_analysis()
        sharpeResult = strat.analyzers.sharpe.get_analysis()
        drawdownResult = strat.analyzers.drawdown.get_analysis()

        finalValue = cerebro.broker.getvalue()
        totalReturn = (finalValue - INITIAL_CASH) / INITIAL_CASH * 100

        totalTrades = 0
        wonTrades = 0
        winRate = 0.0
        if "total" in tradeAnalysis:
            totalTrades = tradeAnalysis["total"]["total"]
            if "won" in tradeAnalysis and totalTrades > 0:
                wonTrades = tradeAnalysis["won"]["total"]
                winRate = wonTrades / totalTrades * 100

        sharpeVal = sharpeResult.get("sharperatio")
        maxDrawdown = drawdownResult["max"]["drawdown"] if "max" in drawdownResult else 0.0

        return {
            "finalValue": finalValue,
            "totalReturn": totalReturn,
            "totalTrades": totalTrades,
            "wonTrades": wonTrades,
            "winRate": winRate,
            "sharpeRatio": sharpeVal,
            "maxDrawdown": maxDrawdown,
        }


def main():
    """
    XRP 参数对比主函数

    逐年、逐参数组运行回测，输出对比表格，找出 XRP 最优参数组
    """
    print("=" * 100)
    print("XRP 专项参数优化对比")
    print(f"回测年份: {START_YEAR}-{END_YEAR}  初始资金: {INITIAL_CASH} USDT")
    print("=" * 100)

    # 参数组名称列表
    groupNames = list(PARAM_GROUPS.keys())

    # 逐年对比
    allResults = {}  # {组名: [逐年结果]}

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"\n--- {year} 年 ---")
        print(f"{'参数组':<16} {'最终资金':>10} {'收益率':>8} {'交易数':>6} {'胜率':>7} {'夏普':>8} {'最大回撤':>8}")
        print("-" * 80)

        for groupName in groupNames:
            params = PARAM_GROUPS[groupName]
            result = runBacktest(params, year)

            if result is None:
                print(f"{groupName:<16} 数据缺失")
                continue

            # 累计结果
            if groupName not in allResults:
                allResults[groupName] = []
            allResults[groupName].append(result)

            sharpeStr = f"{result['sharpeRatio']:.2f}" if result["sharpeRatio"] is not None else "N/A"
            print(
                f"{groupName:<16} {result['finalValue']:>10.2f} {result['totalReturn']:>7.2f}% "
                f"{result['totalTrades']:>6} {result['winRate']:>6.1f}% "
                f"{sharpeStr:>8} {result['maxDrawdown']:>7.2f}%"
            )

    # 多年综合对比
    print(f"\n{'=' * 100}")
    print("XRP 多年综合对比")
    print(f"{'=' * 100}")
    print(f"{'参数组':<16} {'年数':>4} {'平均收益':>10} {'总交易':>6} {'综合胜率':>8} {'平均夏普':>8} {'最大回撤':>8}")
    print("-" * 80)

    bestGroup = None
    bestAvgSharpe = -float('inf')

    for groupName in groupNames:
        results = allResults.get(groupName, [])
        if not results:
            print(f"{groupName:<16} 无结果")
            continue

        yearCount = len(results)
        avgReturn = sum(r["totalReturn"] for r in results) / yearCount
        totalTrades = sum(r["totalTrades"] for r in results)
        totalWon = sum(r["wonTrades"] for r in results)
        overallWinRate = totalWon / totalTrades * 100 if totalTrades > 0 else 0

        # 计算有效夏普的平均值（None 排除）
        sharpeValues = [r["sharpeRatio"] for r in results if r["sharpeRatio"] is not None]
        avgSharpe = sum(sharpeValues) / len(sharpeValues) if sharpeValues else 0

        # 最大回撤取所有年份中的最大值
        maxDd = max(r["maxDrawdown"] for r in results)

        print(
            f"{groupName:<16} {yearCount:>4} {avgReturn:>9.2f}% "
            f"{totalTrades:>6} {overallWinRate:>7.1f}% "
            f"{avgSharpe:>8.2f} {maxDd:>7.2f}%"
        )

        if avgSharpe > bestAvgSharpe:
            bestAvgSharpe = avgSharpe
            bestGroup = groupName

    # 推荐结论
    if bestGroup:
        print(f"\n>>> 推荐参数组: {bestGroup}（平均夏普 {bestAvgSharpe:.2f}）")

        # 打印推荐参数与默认参数的差异
        if bestGroup != "默认(基准)":
            bestParams = PARAM_GROUPS[bestGroup]
            diffKeys = [k for k in bestParams if bestParams[k] != DEFAULT_PARAMS.get(k)]
            print(f"\n与默认参数的差异:")
            for key in diffKeys:
                defaultVal = DEFAULT_PARAMS.get(key, "N/A")
                bestVal = bestParams[key]
                print(f"  {key}: {defaultVal} → {bestVal}")

            print(f"\n将以下参数添加到 test_strategy3.py 的 SYMBOL_PARAMS_OVERRIDE['XRP'] 中即可:")
            print(f"    \"XRP\": dict(")
            for key in diffKeys:
                val = bestParams[key]
                if isinstance(val, float):
                    print(f"        {key}={val},")
                elif isinstance(val, bool):
                    print(f"        {key}={val},")
                else:
                    print(f"        {key}={val},")
            print(f"    ),")


if __name__ == "__main__":
    main()
