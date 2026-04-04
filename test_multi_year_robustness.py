#!/usr/bin/env python3
"""
多年份稳健性回测（2017~2025）
逐年输出，并在参数网格中快速筛选“跨年份更稳”的参数区间。
"""

import itertools
import statistics
from pathlib import Path

import backtrader as bt
import pandas as pd

from trend.strategy3 import Strategy3


START_CASH = 5000.0
YEARS = list(range(2017, 2026))


# 基础参数（与你当前调参思路一致）
BASE_PARAMS = {
    "leverage": 5.0,
    "max_leverage_ratio": 0.85,
    "max_position_size": 0.25,
    "min_holding_bars": 5,
    "ema_exit_confirm_bars": 3,
    "volatility_scaling": True,
    "dynamic_risk_adjustment": True,
    "printlog": False,
    "eventlog": False,
}


# 快速网格：可按需要扩/缩
PARAM_GRID = {
    "risk_per_trade": [0.011, 0.0115, 0.012],
    "ema_exit_buffer_atr": [0.26, 0.28, 0.30],
    "require_both_entry_signals": [False, True],
}


def _data_paths(year: int):
    y = f"{year}0101_{year}1231"
    return {
        "4H": Path(f"data/ETH/ethusdt_4h_{y}.csv"),
        "1H": Path(f"data/ETH/ethusdt_1h_{y}.csv"),
        "15M": Path(f"data/ETH/ethusdt_15m_{y}.csv"),
    }


def _load_datafeeds(year: int):
    paths = _data_paths(year)
    feeds = []

    for tf in ["4H", "1H", "15M"]:
        p = paths[tf]
        if not p.exists():
            return None

        df = pd.read_csv(p, parse_dates=["datetime"], index_col="datetime")
        feed = bt.feeds.PandasData(
            dataname=df,
            datetime=None,
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
        )
        feeds.append(feed)

    return feeds


def run_one_year(year: int, params: dict):
    feeds = _load_datafeeds(year)
    if not feeds:
        return None

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(START_CASH)
    cerebro.broker.set_shortcash(True)
    cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
    cerebro.broker.set_slippage_perc(0.001)
    cerebro.broker.set_coc(True)

    for f in feeds:
        cerebro.adddata(f)

    merged_params = dict(BASE_PARAMS)
    merged_params.update(params)
    cerebro.addstrategy(Strategy3, **merged_params)

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

    try:
        results = cerebro.run()
        if not results:
            return None

        strat = results[0]
        ta = strat.analyzers.trades.get_analysis()
        sa = strat.analyzers.sharpe.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()

        total_trades = ta.get("total", {}).get("total", 0)
        won = ta.get("won", {}).get("total", 0)
        win_rate = (won / total_trades * 100) if total_trades else 0.0

        final_value = cerebro.broker.getvalue()
        return_pct = (final_value - START_CASH) / START_CASH * 100
        sharpe = sa.get("sharperatio")
        max_dd = dd.get("max", {}).get("drawdown", 0.0)

        return {
            "year": year,
            "final_value": final_value,
            "return_pct": return_pct,
            "trades": total_trades,
            "win_rate": win_rate,
            "sharpe": sharpe if sharpe is not None else 0.0,
            "max_drawdown": max_dd,
        }
    except Exception:
        return None


def _iter_param_sets(grid: dict):
    keys = list(grid.keys())
    values = [grid[k] for k in keys]
    for combo in itertools.product(*values):
        yield dict(zip(keys, combo))


def summarize_param_set(yearly_rows: list, params: dict):
    returns = [r["return_pct"] for r in yearly_rows]
    drawdowns = [r["max_drawdown"] for r in yearly_rows]
    sharpes = [r["sharpe"] for r in yearly_rows]

    positive_years = sum(1 for x in returns if x > 0)
    non_negative_years = sum(1 for x in returns if x >= 0)

    avg_ret = statistics.mean(returns)
    med_ret = statistics.median(returns)
    min_ret = min(returns)
    max_ret = max(returns)

    avg_dd = statistics.mean(drawdowns)
    max_dd = max(drawdowns)
    avg_sharpe = statistics.mean(sharpes)

    stability_score = (
        avg_ret
        - 0.60 * avg_dd
        - 0.30 * max_dd
        + 0.35 * avg_sharpe
        + 0.50 * (positive_years / len(yearly_rows))
    )

    return {
        "params": params,
        "years": len(yearly_rows),
        "positive_years": positive_years,
        "non_negative_years": non_negative_years,
        "avg_return": avg_ret,
        "median_return": med_ret,
        "min_return": min_ret,
        "max_return": max_ret,
        "avg_drawdown": avg_dd,
        "max_drawdown": max_dd,
        "avg_sharpe": avg_sharpe,
        "stability_score": stability_score,
    }


def print_yearly_result(params: dict, rows: list):
    print("\n" + "=" * 90)
    print(f"参数组合: {params}")
    print("-" * 90)
    print("年份 | 收益率% | 最大回撤% | 夏普 | 交易数 | 胜率%")
    for r in rows:
        print(
            f"{r['year']} | {r['return_pct']:>7.2f} | {r['max_drawdown']:>9.2f} | "
            f"{r['sharpe']:>4.2f} | {r['trades']:>5d} | {r['win_rate']:>6.2f}"
        )


def print_top_summary(summaries: list, top_n: int = 5):
    top = summaries[:top_n]
    print("\n" + "#" * 90)
    print(f"TOP {top_n} 跨年份稳健参数（按 stability_score 排序）")
    print("#" * 90)

    for i, s in enumerate(top, 1):
        print(
            f"[{i}] score={s['stability_score']:.3f} | avgRet={s['avg_return']:.2f}% | "
            f"avgDD={s['avg_drawdown']:.2f}% | maxDD={s['max_drawdown']:.2f}% | "
            f"avgSharpe={s['avg_sharpe']:.2f} | +Year={s['positive_years']}/{s['years']} | "
            f"params={s['params']}"
        )

    if not top:
        return

    # 给出“区间建议”
    risk_vals = [s["params"]["risk_per_trade"] for s in top]
    buffer_vals = [s["params"]["ema_exit_buffer_atr"] for s in top]
    both_vals = [s["params"]["require_both_entry_signals"] for s in top]

    print("\n建议区间（来自TOP组合）：")
    print(f"- risk_per_trade: {min(risk_vals):.4f} ~ {max(risk_vals):.4f}")
    print(f"- ema_exit_buffer_atr: {min(buffer_vals):.2f} ~ {max(buffer_vals):.2f}")
    false_ratio = sum(1 for x in both_vals if x is False) / len(both_vals) * 100
    print(
        f"- require_both_entry_signals=False 出现占比: {false_ratio:.0f}% "
        f"(越高说明放宽信号在跨年上更稳)"
    )


def main():
    all_summaries = []

    for params in _iter_param_sets(PARAM_GRID):
        yearly_rows = []

        for y in YEARS:
            r = run_one_year(y, params)
            if r is not None:
                yearly_rows.append(r)

        if not yearly_rows:
            continue

        print_yearly_result(params, yearly_rows)
        summary = summarize_param_set(yearly_rows, params)
        all_summaries.append(summary)

    if not all_summaries:
        print("未得到有效结果，请检查数据文件是否完整。")
        return

    all_summaries.sort(key=lambda x: x["stability_score"], reverse=True)
    print_top_summary(all_summaries, top_n=5)


if __name__ == "__main__":
    main()
