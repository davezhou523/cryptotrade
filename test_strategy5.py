#!/usr/bin/env python3
"""
Strategy5 v4 回测脚本 — S3基底 + 趋势交叉入场
核心：收益/胜率/夏普必须优秀前提下提高交易次数
"""

from pathlib import Path
from datetime import datetime
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy5 import Strategy5

# 项目根目录
ROOT = Path(__file__).resolve().parent

# ======================== 可配置参数 ========================

SYMBOLS = ["BTC", "BNB", "SOL", "XRP", "ETH"]

START_YEAR = 2020
END_YEAR = 2025

INITIAL_CASH = 10000.0

# 策略5 v4参数 — S3基底 + 交叉入场
PARAMS = dict(
    # 日志控制
    printlog=True,
    eventlog=True,

    # 周期参数（同S3）
    h4_ema_fast=21,
    h4_ema_slow=55,
    h4_adx_period=14,
    h4_adx_strong_threshold=30,
    h4_adx_min_threshold=22,
    h1_ema_fast=21,
    h1_ema_slow=55,
    h1_rsi_period=14,
    h1_macd_fast=12,
    h1_macd_slow=26,
    h1_macd_signal=9,
    h1_atr_period=14,
    m15_ema_period=21,
    m15_atr_period=14,
    m15_rsi_period=14,
    m15_volume_ma_period=15,
    m15_breakout_lookback=6,           # 同S3（v3用5，改回6）

    # 风控与仓位（同S3）
    risk_per_trade=0.03,
    max_position_size=0.55,            # 同S3（v3用0.60）
    strong_trend_boost=1.0,
    deep_pullback_scale=0.9,
    pullback_deep_band=0.003,
    stop_loss_atr_multiplier=1.5,      # 同S3（v3用1.2→1.5）
    min_holding_bars=5,                # 同S3（v3用3）
    ema_exit_confirm_bars=2,
    ema_exit_buffer_atr=0.30,          # 同S3（v3用0.25）

    # 追踪止盈参数（兼容，不使用渐进追踪）
    tp1_r_multiplier=1.0,
    tp2_r_multiplier=3.0,
    tp3_r_multiplier=3.5,
    tp4_r_multiplier=5.0,
    trailing_stop_atr_multiplier=2.5,
    trailing_tighten1_multiplier=1.5,
    trailing_tighten2_multiplier=1.0,

    # 动量模式参数（兼容，不使用）
    momentum_atr_distance=3.0,
    momentum_position_scale=0.80,
    momentum_adx_threshold=20,

    # 趋势交叉模式参数（唯一新增）
    crossover_atr_distance=0.5,        # 交叉模式：EMA21附近0.5×ATR内
    crossover_position_scale=0.9,      # 交叉模式仓位缩放（仅轻微缩放）
    crossover_adx_threshold=25,        # 交叉模式ADX阈值（比v3更严格）

    # 震荡市模式参数（兼容，不使用）
    sideways_enabled=False,
    sideways_ema_distance=0.02,
    sideways_position_scale=0.50,
    sideways_stop_atr_multiplier=1.0,
    sideways_adx_threshold=20,
    sideways_rsi_long_low=42,
    sideways_rsi_long_high=62,
    sideways_rsi_short_low=38,
    sideways_rsi_short_high=58,
    sideways_volume_threshold=1.10,
    sideways_trailing_atr_multiplier=1.0,

    # 杠杆约束（同S3）
    leverage=7.0,
    max_leverage_ratio=0.92,

    # 风险限制（同S3）
    max_positions=1,
    max_consecutive_losses=3,
    max_daily_loss_pct=0.07,
    max_drawdown_pct=0.15,             # 同S3（v3用0.10）
    drawdown_position_scale=0.5,       # 同S3（v3用0.4）
    hard_drawdown_limit=0.13,

    # 入场过滤（同S3）
    h1_rsi_long_low=42,               # 同S3（v3用38）
    h1_rsi_long_high=60,              # 同S3（v3用64）
    h1_rsi_short_low=40,              # 同S3（v3用36）
    h1_rsi_short_high=58,             # 同S3（v3用62）
    m15_rsi_bias_long=52,             # 同S3（v3用49）
    m15_rsi_bias_short=48,            # 同S3（v3用51）
    volume_ratio_threshold=1.0,
    momentum_volume_threshold=1.10,

    # 兼容参数
    volatility_scaling=True,
    dynamic_risk_adjustment=True,
)

# ======================== 币种级别参数覆盖 ========================

SYMBOL_PARAMS_OVERRIDE = {
    "XRP": dict(
        risk_per_trade=0.02,
        stop_loss_atr_multiplier=2.0,
        ema_exit_buffer_atr=0.4,
        leverage=5.0,
        crossover_position_scale=0.85,     # XRP交叉模式更保守
        crossover_adx_threshold=28,         # XRP交叉ADX更严格
    ),
}


def getSymbolParams(coin: str) -> dict:
    params = dict(PARAMS)
    if coin in SYMBOL_PARAMS_OVERRIDE:
        params.update(SYMBOL_PARAMS_OVERRIDE[coin])
    return params


# ==========================================================


def buildDataFilePaths(coin: str, year: int) -> list:
    symbolLower = f"{coin.lower()}usdt"
    yearStart = f"{year}0101"
    yearEnd = f"{year}1231"
    return [
        ("4H", f"data/{coin}/binance/{symbolLower}_4h_{yearStart}_{yearEnd}.csv"),
        ("1H", f"data/{coin}/binance/{symbolLower}_1h_{yearStart}_{yearEnd}.csv"),
        ("15M", f"data/{coin}/binance/{symbolLower}_15m_{yearStart}_{yearEnd}.csv"),
    ]


def loadMultiPeriodData(dataFilePaths: list) -> list | None:
    datas = []
    for timeframe, filepath in dataFilePaths:
        fullPath = ROOT / filepath
        try:
            df = pd.read_csv(fullPath, parse_dates=["datetime"], index_col="datetime")
            if df.empty:
                print(f"  跳过空数据文件 {timeframe}: {filepath}")
                return None
            data = bt.feeds.PandasData(
                dataname=df,
                datetime=None,
                open='open', high='high', low='low', close='close',
                volume='volume', openinterest=-1
            )
            datas.append(data)
            print(f"  成功加载 {timeframe} 数据: {filepath}，共 {len(df)} 行")
        except FileNotFoundError:
            print(f"  数据文件不存在 {timeframe}: {filepath}")
            return None
        except Exception as exc:
            print(f"  加载数据失败 {timeframe}: {filepath}，错误: {exc}")
            return None

    if len(datas) < 3:
        print(f"  有效数据不足，期望3个周期(4H/1H/15M)，实际 {len(datas)} 个")
        return None
    return datas


def runBacktest(coin: str, year: int, printLog: bool = False) -> dict | None:
    dataFilePaths = buildDataFilePaths(coin, year)
    strategyParams = getSymbolParams(coin)
    strategyParams['printlog'] = printLog
    strategyParams['eventlog'] = printLog

    buffer = io.StringIO()
    redirectTarget = buffer if not printLog else None

    try:
        if redirectTarget:
            ctx = contextlib.redirect_stdout(buffer)
            ctx2 = contextlib.redirect_stderr(buffer)
            ctx.__enter__()
            ctx2.__enter__()

        cerebro = bt.Cerebro()
        cerebro.broker.setcash(INITIAL_CASH)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        datas = loadMultiPeriodData(dataFilePaths)
        if datas is None:
            print(f"  [{coin} {year}] 数据加载失败，跳过该年份")
            return None

        for data in datas:
            cerebro.adddata(data)

        cerebro.addstrategy(Strategy5, **strategyParams)
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

        print(f"  [{coin} {year}] 开始回测...")
        results = cerebro.run()

        if not results:
            print(f"  [{coin} {year}] 回测没有产生结果")
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
        maxDrawdown = 0.0
        if "max" in drawdownResult:
            maxDrawdown = drawdownResult["max"]["drawdown"]

        result = {
            "coin": coin, "year": year,
            "initialCash": INITIAL_CASH, "finalValue": finalValue,
            "totalReturn": totalReturn, "totalTrades": totalTrades,
            "wonTrades": wonTrades, "winRate": winRate,
            "sharpeRatio": sharpeVal, "maxDrawdown": maxDrawdown,
        }

        # 标记是否达标
        sharpe_ok = sharpeVal is not None and sharpeVal > 1.2
        dd_ok = maxDrawdown < 15.0
        status = "✓" if (sharpe_ok and dd_ok) else "✗"

        print(
            f"  [{coin} {year}] 回测完成{status}: "
            f"最终={finalValue:.2f}  收益={totalReturn:.2f}%  "
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
    print(f"\n{'=' * 60}")
    print(f"Strategy5 v4 (S3+交叉) 回测 {coin}USDT ({startYear}-{endYear})")
    print(f"{'=' * 60}")

    results = []
    for year in range(startYear, endYear + 1):
        result = runBacktest(coin, year, printLog=printLog)
        if result is not None:
            results.append(result)
    return results


def printSummaryTable(allResults: list):
    if not allResults:
        print("无回测结果可汇总")
        return

    coinResults = {}
    for r in allResults:
        coin = r["coin"]
        if coin not in coinResults:
            coinResults[coin] = []
        coinResults[coin].append(r)

    print(f"\n{'=' * 110}")
    print("Strategy5 v4 (S3+交叉) — 多币种回测结果汇总")
    print(f"{'=' * 110}")

    header = (
        f"{'币种':<6} {'年份':<6} {'最终资金':>10} "
        f"{'收益率':>8} {'交易数':>6} {'胜率':>7} {'夏普比率':>8} {'最大回撤':>8} {'达标':>4}"
    )
    print(header)
    print("-" * 110)

    summaryData = {}

    for coin in sorted(coinResults.keys()):
        results = coinResults[coin]
        totalReturnSum = 0.0
        totalTrades = 0
        totalWon = 0
        passCount = 0

        for r in results:
            sharpeStr = f"{r['sharpeRatio']:.2f}" if r["sharpeRatio"] is not None else "N/A"
            sharpe_ok = r["sharpeRatio"] is not None and r["sharpeRatio"] > 1.2
            dd_ok = r["maxDrawdown"] < 15.0
            status = "✓" if (sharpe_ok and dd_ok) else "✗"
            if sharpe_ok and dd_ok:
                passCount += 1

            print(
                f"{coin:<6} {r['year']:<6} {r['finalValue']:>10.2f} "
                f"{r['totalReturn']:>7.2f}% {r['totalTrades']:>6} {r['winRate']:>6.1f}% "
                f"{sharpeStr:>8} {r['maxDrawdown']:>7.2f}% {status:>4}"
            )
            totalReturnSum += r["totalReturn"]
            totalTrades += r["totalTrades"]
            totalWon += r["wonTrades"]

        yearCount = len(results)
        avgReturn = totalReturnSum / yearCount if yearCount > 0 else 0
        overallWinRate = totalWon / totalTrades * 100 if totalTrades > 0 else 0
        passRate = passCount / yearCount * 100 if yearCount > 0 else 0
        summaryData[coin] = {
            "avgReturn": avgReturn,
            "totalTrades": totalTrades,
            "winRate": overallWinRate,
            "yearCount": yearCount,
            "passRate": passRate,
        }

    print(f"\n{'=' * 90}")
    print("跨币种对比汇总（多年平均）")
    print(f"{'=' * 90}")
    print(f"{'币种':<6} {'年数':>4} {'平均收益率':>10} {'总交易数':>8} {'综合胜率':>8} {'达标率':>8}")
    print("-" * 90)

    for coin in sorted(summaryData.keys()):
        s = summaryData[coin]
        print(
            f"{coin:<6} {s['yearCount']:>4} {s['avgReturn']:>9.2f}% "
            f"{s['totalTrades']:>8} {s['winRate']:>7.1f}% {s['passRate']:>7.1f}%"
        )


def testMultiSymbol(symbols: list = None, startYear: int = START_YEAR,
                    endYear: int = END_YEAR, printLog: bool = False):
    if symbols is None:
        symbols = SYMBOLS

    print("=" * 80)
    print("Strategy5 v4 (S3+交叉) 多币种回测")
    print(f"目标: 夏普率 > 1.2, 最大回撤 < 15%")
    print(f"币种: {', '.join(symbols)}")
    print(f"年份: {startYear} ~ {endYear}")
    print(f"初始资金: {INITIAL_CASH} USDT")
    print(f"核心改动: S3基底 + 趋势交叉入场(ADX≥25+MACD确认)")
    print(f"策略参数: 杠杆={PARAMS['leverage']}x  单笔风险={PARAMS['risk_per_trade']*100}%  "
          f"止损ATR={PARAMS['stop_loss_atr_multiplier']}x  交叉仓位={PARAMS['crossover_position_scale']}x")
    print("=" * 80)

    allResults = []

    for coin in symbols:
        coinResults = runSingleSymbol(coin, startYear, endYear, printLog=printLog)
        allResults.extend(coinResults)

        if coinResults:
            logLines = []
            for r in coinResults:
                sharpe_ok = r['sharpeRatio'] is not None and r['sharpeRatio'] > 1.2
                dd_ok = r['maxDrawdown'] < 15.0
                status = "PASS" if (sharpe_ok and dd_ok) else "FAIL"
                logLines.append(
                    f"{r['coin']} {r['year']} [{status}]: "
                    f"最终={r['finalValue']:.2f}  收益={r['totalReturn']:.2f}%  "
                    f"交易={r['totalTrades']}  胜率={r['winRate']:.1f}%  "
                    f"夏普={'N/A' if r['sharpeRatio'] is None else f'{r['sharpeRatio']:.2f}'}  "
                    f"回撤={r['maxDrawdown']:.2f}%"
                )
            logPath = ROOT / f"res5_{coin.lower()}_{startYear}_{endYear}"
            logPath.write_text("\n".join(logLines), encoding="utf-8")
            print(f"  {coin} 结果已保存到 {logPath}")

    printSummaryTable(allResults)
    return allResults


# ======================== 脚本入口 ========================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        coins = [arg.upper() for arg in sys.argv[1:] if not arg.startswith("--")]
        enableLog = "--log" in sys.argv
        if coins:
            testMultiSymbol(symbols=coins, printLog=enableLog)
        else:
            testMultiSymbol(printLog=enableLog)
    else:
        testMultiSymbol()
