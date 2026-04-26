#!/usr/bin/env python3
"""
策略4测试脚本
测试 1H趋势 + 15M突破入场 + ATR风控 + RSI动量确认 策略 (优化版)
"""

from pathlib import Path
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy4 import Strategy4

ROOT = Path(__file__).resolve().parent

PARAMS = dict(
    # 日志控制
    printlog=True,
    eventlog=True,

    # 1H趋势指标参数
    h1_ema_fast=21,
    h1_ema_slow=55,
    h1_adx_period=14,
    h1_adx_threshold=25,

    # 15M入场指标参数
    m15_donchian_period=20,
    m15_rsi_period=14,
    m15_atr_period=14,
    m15_volume_ma_period=20,
    m15_ema_period=21,

    # 市场过滤参数
    atr_price_ratio_min=0.002,
    volume_ratio_threshold=1.2,
    candle_body_ratio_min=0.4,

    # 突破参数
    breakout_atr_offset=0.1,

    # RSI动量确认参数
    rsi_long_min=55,
    rsi_short_max=45,

    # 风控参数
    stop_loss_atr_multiplier=2.5,
    take_profit_1_atr=2.0,
    take_profit_2_atr=4.0,
    trailing_stop_atr=2.5,
    ema_exit_buffer_atr=0.5,
    ema_exit_confirm_bars=3,
    min_holding_bars=5,

    # 新增过滤参数
    min_trend_bars=3,
    rsi_overbought=70,
    rsi_oversold=30,
    breakout_confirm_bars=2,

    # 仓位管理参数
    risk_per_trade=0.02,
    max_position_size=0.55,
    leverage=7,
    max_leverage_ratio=0.92,
    max_drawdown_pct=0.15,
    drawdown_position_scale=0.5,

    # 风险控制
    max_consecutive_losses=5,
    max_daily_loss_pct=0.08,
)


def run_year(year: int) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(10000.0)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        data_files = [
            ("1H", f"data/ETH/binance/ethusdt_1h_{year}0101_{year}1231.csv"),
            ("15M", f"data/ETH/binance/ethusdt_15m_{year}0101_{year}1231.csv"),
        ]

        datas = []
        for timeframe, filepath in data_files:
            try:
                df = pd.read_csv(ROOT / filepath, parse_dates=["datetime"], index_col="datetime")
                if df.empty:
                    print(f"跳过空数据文件 {timeframe}: {filepath}")
                    continue

                data = bt.feeds.PandasData(
                    dataname=df,
                    datetime=None,
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

        if len(datas) < 2:
            print(f"错误: 有效数据不足，期望2个周期(1H/15M)，实际 {len(datas)} 个")
            return buffer.getvalue()

        for data in datas:
            cerebro.adddata(data)

        cerebro.addstrategy(Strategy4, **PARAMS)
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

        print("=== 开始策略4回测 ===")
        results = cerebro.run()

        if not results:
            print("回测没有产生结果")
            return buffer.getvalue()

        strat = results[0]
        trade_analysis = strat.analyzers.trades.get_analysis()
        sharpe_ratio = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()

        print("\n=== 策略4回测结果 ===")
        print(f"最终资金: {cerebro.broker.getvalue():.2f}")
        print(f"总收益率: {(cerebro.broker.getvalue() - 10000) / 10000 * 100:.2f}%")

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


def test_strategy4():
    for year in range(2020, 2026):
        output = run_year(year)
        (ROOT / f"res{year}_4").write_text(output, encoding="utf-16")
        print(f"done {year}")


if __name__ == "__main__":
    test_strategy4()
