#!/usr/bin/env python3
"""
多币种回测脚本
支持 BTCUSDT / BNBUSDT / SOLUSDT / XRPUSDT / ETHUSDT 多币种回测
每个币种使用 4H + 1H + 15M 三个周期数据，逐年回测并汇总结果
"""

from pathlib import Path
from datetime import datetime
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy3 import Strategy3

# 项目根目录
ROOT = Path(__file__).resolve().parent

# ======================== 可配置参数 ========================

# 回测币种列表（币种简称，对应 data/{COIN}/binance/ 目录）
SYMBOLS = ["BTC", "BNB", "SOL", "XRP", "ETH"]

# 回测年份范围
START_YEAR = 2020
END_YEAR = 2025

# 每个币种的初始资金（USDT）
INITIAL_CASH = 10000.0

# 策略参数配置
PARAMS = dict(
    # 日志控制
    printlog=True,                  # 打印普通日志（每笔交易等）
    eventlog=True,                  # 打印重要事件日志（入场、出场、风控触发等）

    # 周期参数 - 各时间周期的指标参数
    h4_ema_fast=21,                 # 4小时图快速EMA周期
    h4_ema_slow=55,                 # 4小时图慢速EMA周期
    h1_ema_fast=21,                 # 1小时图快速EMA周期
    h1_ema_slow=55,                 # 1小时图慢速EMA周期
    h1_rsi_period=14,               # 1小时图RSI周期
    m15_ema_period=21,              # 15分钟图EMA周期（用于出场判断）
    m15_atr_period=14,              # 15分钟图ATR周期（用于止损和仓位计算）
    m15_rsi_period=14,              # 15分钟图RSI周期（用于入场信号）

    # 风控与仓位 - 风险管理和仓位大小计算
    risk_per_trade=0.03,            # 单笔风险，占总资金的3.0%
    max_position_size=0.55,         # 最大仓位规模（占总资金比例）
    deep_pullback_scale=0.9,        # 深回调轻仓系数，价格接近EMA55时仓位打9折
    pullback_deep_band=0.003,       # 贴近EMA55判定带（0.3%）
    stop_loss_atr_multiplier=1.5,   # 止损距离=1.5×ATR
    min_holding_bars=5,             # 最小持仓K线数
    ema_exit_confirm_bars=2,        # EMA破位连续确认K线数
    ema_exit_buffer_atr=0.30,       # EMA破位缓冲带（ATR倍数）

    # 杠杆约束 - 保证金交易参数
    leverage=7.0,                   # 杠杆倍数
    max_leverage_ratio=0.92,        # 最大杠杆使用率

    # 风险限制 - 全局风险控制
    max_positions=1,                # 最大同时持仓数
    max_consecutive_losses=3,       # 最大连续亏损次数
    max_daily_loss_pct=0.07,        # 最大日亏损比例（7%）
    max_drawdown_pct=0.15,          # 最大回撤比例（15%）
    drawdown_position_scale=0.5,    # 回撤仓位缩放系数

    # 过滤 - 信号过滤条件
    require_both_entry_signals=False,  # 是否需要同时满足结构突破和RSI信号
    h1_rsi_long_low=42,            # 1小时图多头RSI下限
    h1_rsi_long_high=60,           # 1小时图多头RSI上限
    h1_rsi_short_low=40,           # 1小时图空头RSI下限
    h1_rsi_short_high=58,          # 1小时图空头RSI上限
    m15_breakout_lookback=6,       # 15分钟图突破结构回顾期（K线数）
    m15_rsi_bias_long=52,          # 15分钟图多头RSI偏置
    m15_rsi_bias_short=48,         # 15分钟图空头RSI偏置

    # 兼容测试脚本参数
    volatility_scaling=True,        # 波动率缩放
    dynamic_risk_adjustment=True,   # 动态风险调整
)

# ==========================================================


def buildDataFilePaths(coin: str, year: int) -> list:
    """
    根据币种简称和年份构建三个周期的CSV数据文件路径

    :param coin: 币种简称，如 "BTC", "ETH"
    :param year: 年份，如 2024
    :return: [(时间周期名, 文件相对路径), ...]，如 [("4H", "data/BTC/binance/btcusdt_4h_20240101_20241231.csv"), ...]
    """
    symbolLower = f"{coin.lower()}usdt"
    yearStart = f"{year}0101"
    yearEnd = f"{year}1231"
    return [
        ("4H", f"data/{coin}/binance/{symbolLower}_4h_{yearStart}_{yearEnd}.csv"),
        ("1H", f"data/{coin}/binance/{symbolLower}_1h_{yearStart}_{yearEnd}.csv"),
        ("15M", f"data/{coin}/binance/{symbolLower}_15m_{yearStart}_{yearEnd}.csv"),
    ]


def loadMultiPeriodData(dataFilePaths: list) -> list | None:
    """
    加载多周期K线数据，返回Backtrader数据对象列表

    :param dataFilePaths: [(时间周期名, 文件相对路径), ...]
    :return: [bt.feeds.PandasData, ...] 成功返回3个数据对象，失败返回None
    """
    datas = []
    for timeframe, filepath in dataFilePaths:
        fullPath = ROOT / filepath
        try:
            # 读取CSV文件，解析日期时间列并设为索引
            df = pd.read_csv(fullPath, parse_dates=["datetime"], index_col="datetime")
            if df.empty:
                print(f"  跳过空数据文件 {timeframe}: {filepath}")
                return None

            # 将DataFrame转换为Backtrader可用的数据对象
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,       # 已经设置了索引
                open='open',
                high='high',
                low='low',
                close='close',
                volume='volume',
                openinterest=-1
            )
            datas.append(data)
            print(f"  成功加载 {timeframe} 数据: {filepath}，共 {len(df)} 行")
        except FileNotFoundError:
            print(f"  数据文件不存在 {timeframe}: {filepath}")
            return None
        except Exception as exc:
            print(f"  加载数据失败 {timeframe}: {filepath}，错误: {exc}")
            return None

    # 必须成功加载3个周期的数据
    if len(datas) < 3:
        print(f"  有效数据不足，期望3个周期(4H/1H/15M)，实际 {len(datas)} 个")
        return None

    return datas


def runBacktest(coin: str, year: int, printLog: bool = False) -> dict | None:
    """
    运行单个币种、单个年份的回测

    :param coin: 币种简称，如 "BTC"
    :param year: 回测年份
    :param printLog: 是否输出详细日志到控制台
    :return: 回测结果字典，包含资金、收益率、胜率等指标；失败返回None

    功能说明:
        1. 创建Cerebro回测引擎并配置初始资金、佣金、滑点等
        2. 加载三个时间周期（4H、1H、15M）的K线数据
        3. 添加Strategy3策略和性能分析器（交易分析、夏普比率、回撤）
        4. 运行回测并收集结果
        5. 返回关键性能指标：最终资金、总收益率、交易次数、胜率、夏普比率、最大回撤
    """
    # 构建数据文件路径
    dataFilePaths = buildDataFilePaths(coin, year)

    # 构建策略参数（控制日志输出）
    strategyParams = dict(PARAMS)
    strategyParams['printlog'] = printLog
    strategyParams['eventlog'] = printLog

    # 用于捕获回测过程中的输出
    buffer = io.StringIO()
    redirectTarget = buffer if not printLog else None

    try:
        if redirectTarget:
            ctx = contextlib.redirect_stdout(buffer)
            ctx2 = contextlib.redirect_stderr(buffer)
            ctx.__enter__()
            ctx2.__enter__()

        # 创建回测引擎
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(INITIAL_CASH)
        cerebro.broker.set_shortcash(True)
        # 设置交易佣金：0.1%，保证金20%，非股票模式（期货/杠杆交易）
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        # 启用收盘价交易（Close-Of-Candle）
        cerebro.broker.set_coc(True)

        # 加载多周期数据
        datas = loadMultiPeriodData(dataFilePaths)
        if datas is None:
            print(f"  [{coin} {year}] 数据加载失败，跳过该年份")
            return None

        # 将数据添加到回测引擎
        for data in datas:
            cerebro.adddata(data)

        # 添加策略实例
        cerebro.addstrategy(Strategy3, **strategyParams)
        # 添加交易分析器
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        # 添加夏普比率分析器
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio_A,
            _name="sharpe",
            timeframe=bt.TimeFrame.Days,
            compression=1,
            riskfreerate=0.0,
            annualize=True,
        )
        # 添加回撤分析器
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        # 执行回测
        print(f"  [{coin} {year}] 开始回测...")
        results = cerebro.run()

        if not results:
            print(f"  [{coin} {year}] 回测没有产生结果")
            return None

        # 提取分析器结果
        strat = results[0]
        tradeAnalysis = strat.analyzers.trades.get_analysis()
        sharpeResult = strat.analyzers.sharpe.get_analysis()
        drawdownResult = strat.analyzers.drawdown.get_analysis()

        # 计算核心指标
        finalValue = cerebro.broker.getvalue()
        totalReturn = (finalValue - INITIAL_CASH) / INITIAL_CASH * 100

        # 交易统计
        totalTrades = 0
        wonTrades = 0
        winRate = 0.0
        if "total" in tradeAnalysis:
            totalTrades = tradeAnalysis["total"]["total"]
            if "won" in tradeAnalysis and totalTrades > 0:
                wonTrades = tradeAnalysis["won"]["total"]
                winRate = wonTrades / totalTrades * 100

        # 夏普比率
        sharpeVal = sharpeResult.get("sharperatio")

        # 最大回撤
        maxDrawdown = 0.0
        if "max" in drawdownResult:
            maxDrawdown = drawdownResult["max"]["drawdown"]

        result = {
            "coin": coin,
            "year": year,
            "initialCash": INITIAL_CASH,
            "finalValue": finalValue,
            "totalReturn": totalReturn,
            "totalTrades": totalTrades,
            "wonTrades": wonTrades,
            "winRate": winRate,
            "sharpeRatio": sharpeVal,
            "maxDrawdown": maxDrawdown,
        }

        print(
            f"  [{coin} {year}] 回测完成: "
            f"最终资金={finalValue:.2f}  收益率={totalReturn:.2f}%  "
            f"交易={totalTrades}次  胜率={winRate:.1f}%  "
            f"夏普={'N/A' if sharpeVal is None else f'{sharpeVal:.2f}'}  "
            f"最大回撤={maxDrawdown:.2f}%"
        )

        return result

    except Exception as e:
        print(f"  [{coin} {year}] 回测异常: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        if redirectTarget:
            ctx.__exit__(None, None, None)
            ctx2.__exit__(None, None, None)


def runSingleSymbol(coin: str, startYear: int = START_YEAR, endYear: int = END_YEAR,
                    printLog: bool = False) -> list:
    """
    运行单个币种多年的回测

    :param coin: 币种简称，如 "BTC"
    :param startYear: 起始年份
    :param endYear: 结束年份
    :param printLog: 是否输出详细日志
    :return: 回测结果字典列表
    """
    print(f"\n{'=' * 60}")
    print(f"开始回测 {coin}USDT ({startYear}-{endYear})")
    print(f"{'=' * 60}")

    results = []
    for year in range(startYear, endYear + 1):
        result = runBacktest(coin, year, printLog=printLog)
        if result is not None:
            results.append(result)

    return results


def printSummaryTable(allResults: list):
    """
    打印多币种多年度的回测结果汇总表

    :param allResults: 所有回测结果字典列表

    功能说明:
        1. 按币种分组，打印每年的回测指标
        2. 计算每个币种的多年综合指标（平均收益率、综合胜率等）
        3. 打印跨币种对比汇总
    """
    if not allResults:
        print("无回测结果可汇总")
        return

    # 按币种分组
    coinResults = {}
    for r in allResults:
        coin = r["coin"]
        if coin not in coinResults:
            coinResults[coin] = []
        coinResults[coin].append(r)

    print(f"\n{'=' * 100}")
    print("多币种回测结果汇总")
    print(f"{'=' * 100}")

    # 逐年逐币种详细表
    header = (
        f"{'币种':<6} {'年份':<6} {'初始资金':>10} {'最终资金':>10} "
        f"{'收益率':>8} {'交易数':>6} {'胜率':>7} {'夏普比率':>8} {'最大回撤':>8}"
    )
    print(header)
    print("-" * 100)

    # 跨币种汇总数据
    summaryData = {}

    for coin in sorted(coinResults.keys()):
        results = coinResults[coin]
        totalReturnSum = 0.0
        totalTrades = 0
        totalWon = 0

        for r in results:
            sharpeStr = f"{r['sharpeRatio']:.2f}" if r["sharpeRatio"] is not None else "N/A"
            print(
                f"{coin:<6} {r['year']:<6} {r['initialCash']:>10.0f} {r['finalValue']:>10.2f} "
                f"{r['totalReturn']:>7.2f}% {r['totalTrades']:>6} {r['winRate']:>6.1f}% "
                f"{sharpeStr:>8} {r['maxDrawdown']:>7.2f}%"
            )
            totalReturnSum += r["totalReturn"]
            totalTrades += r["totalTrades"]
            totalWon += r["wonTrades"]

        # 计算该币种的综合指标
        yearCount = len(results)
        avgReturn = totalReturnSum / yearCount if yearCount > 0 else 0
        overallWinRate = totalWon / totalTrades * 100 if totalTrades > 0 else 0
        summaryData[coin] = {
            "avgReturn": avgReturn,
            "totalTrades": totalTrades,
            "winRate": overallWinRate,
            "yearCount": yearCount,
        }

    # 综合汇总表
    print(f"\n{'=' * 80}")
    print("跨币种对比汇总（多年平均）")
    print(f"{'=' * 80}")
    print(f"{'币种':<6} {'年数':>4} {'平均收益率':>10} {'总交易数':>8} {'综合胜率':>8}")
    print("-" * 80)

    for coin in sorted(summaryData.keys()):
        s = summaryData[coin]
        print(
            f"{coin:<6} {s['yearCount']:>4} {s['avgReturn']:>9.2f}% "
            f"{s['totalTrades']:>8} {s['winRate']:>7.1f}%"
        )


def testMultiSymbol(symbols: list = None, startYear: int = START_YEAR,
                    endYear: int = END_YEAR, printLog: bool = False):
    """
    多币种回测主函数

    :param symbols: 要回测的币种列表，默认使用 SYMBOLS 配置
    :param startYear: 起始年份
    :param endYear: 结束年份
    :param printLog: 是否输出详细日志到控制台

    功能说明:
        1. 遍历所有币种，逐一运行多年回测
        2. 逐年、逐币种输出回测结果
        3. 将每个币种的详细日志保存到文件
        4. 打印跨币种汇总对比表
    """
    if symbols is None:
        symbols = SYMBOLS

    print("=" * 80)
    print("Strategy3 多币种回测")
    print(f"币种: {', '.join(symbols)}")
    print(f"年份: {startYear} ~ {endYear}")
    print(f"初始资金: {INITIAL_CASH} USDT")
    print(f"策略参数: 杠杆={PARAMS['leverage']}x  单笔风险={PARAMS['risk_per_trade']*100}%  "
          f"止损ATR倍数={PARAMS['stop_loss_atr_multiplier']}")
    print("=" * 80)

    allResults = []

    for coin in symbols:
        # 运行单个币种的多年回测（详细日志不输出到控制台）
        coinResults = runSingleSymbol(coin, startYear, endYear, printLog=printLog)
        allResults.extend(coinResults)

        # 将每个币种的逐年详细日志保存到文件
        if coinResults:
            logLines = []
            for r in coinResults:
                logLines.append(
                    f"{r['coin']} {r['year']}: "
                    f"最终={r['finalValue']:.2f}  收益={r['totalReturn']:.2f}%  "
                    f"交易={r['totalTrades']}  胜率={r['winRate']:.1f}%  "
                    f"夏普={'N/A' if r['sharpeRatio'] is None else f'{r['sharpeRatio']:.2f}'}  "
                    f"回撤={r['maxDrawdown']:.2f}%"
                )
            logPath = ROOT / f"res_{coin.lower()}_{startYear}_{endYear}"
            logPath.write_text("\n".join(logLines), encoding="utf-8")
            print(f"  {coin} 结果已保存到 {logPath}")

    # 打印汇总表
    printSummaryTable(allResults)

    return allResults


# ======================== 兼容旧版单币种回测 ========================

def run_year(year: int, coin: str = "ETH") -> str:
    """
    运行指定年份的策略回测（兼容旧版接口）

    :param year: 要回测的年份
    :param coin: 币种简称，默认 ETH
    :return: 回测输出的文本内容
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        dataFilePaths = buildDataFilePaths(coin, year)
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(INITIAL_CASH)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        datas = loadMultiPeriodData(dataFilePaths)
        if datas is None:
            print(f"错误: 数据加载失败")
            return buffer.getvalue()

        for data in datas:
            cerebro.adddata(data)

        cerebro.addstrategy(Strategy3, **PARAMS)
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(
            bt.analyzers.SharpeRatio_A,
            _name="sharpe",
            timeframe=bt.TimeFrame.Days,
            compression=1,
            riskfreerate=0.0,
            annualize=True,
        )
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        print("=== 开始优化策略回测 ===")
        results = cerebro.run()

        if not results:
            print("回测没有产生结果")
            return buffer.getvalue()

        strat = results[0]
        tradeAnalysis = strat.analyzers.trades.get_analysis()
        sharpeRatio = strat.analyzers.sharpe.get_analysis()
        drawdownResult = strat.analyzers.drawdown.get_analysis()

        print("\n=== 优化策略回测结果 ===")
        print(f"最终资金: {cerebro.broker.getvalue():.2f}")
        print(f"总收益率: {(cerebro.broker.getvalue() - INITIAL_CASH) / INITIAL_CASH * 100:.2f}%")

        if "total" in tradeAnalysis:
            print(f"交易次数: {tradeAnalysis['total']['total']}")
            if "won" in tradeAnalysis:
                winRate = tradeAnalysis["won"]["total"] / tradeAnalysis["total"]["total"] * 100
                print(f"胜率: {winRate:.2f}%")

        sharpeVal = sharpeRatio.get("sharperatio")
        if sharpeVal is not None:
            print(f"夏普比率: {sharpeVal:.2f}")
        else:
            print("夏普比率: 无足够数据计算")

        if "max" in drawdownResult:
            print(f"最大回撤: {drawdownResult['max']['drawdown']:.2f}%")

    return buffer.getvalue()


def test_optimized_strategy():
    """
    兼容旧版单币种（ETH）回测入口
    """
    for year in range(2020, 2026):
        output = run_year(year, coin="ETH")
        (ROOT / f"res{year}_3").write_text(output, encoding="utf-16")
        print(f"done {year}")


# ======================== 脚本入口 ========================

if __name__ == "__main__":
    import sys

    # 支持命令行参数:
    #   python test_strategy3.py                    → 多币种回测（默认 BTC, BNB, SOL, XRP, ETH）
    #   python test_strategy3.py BTC ETH            → 指定币种回测
    #   python test_strategy3.py --single ETH       → 单币种兼容模式（旧版）
    #   python test_strategy3.py --log              → 开启详细日志
    if len(sys.argv) > 1:
        if "--single" in sys.argv:
            # 旧版单币种模式
            idx = sys.argv.index("--single")
            coin = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else "ETH"
            for year in range(START_YEAR, END_YEAR + 1):
                output = run_year(year, coin=coin)
                (ROOT / f"res{year}_{coin.lower()}").write_text(output, encoding="utf-16")
                print(f"done {coin} {year}")
        else:
            # 指定币种列表
            coins = [arg.upper() for arg in sys.argv[1:] if not arg.startswith("--")]
            enableLog = "--log" in sys.argv
            testMultiSymbol(symbols=coins, printLog=enableLog)
    else:
        # 默认：多币种回测
        testMultiSymbol()
