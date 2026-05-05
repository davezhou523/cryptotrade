#!/usr/bin/env python3
"""
Strategy3 vs Strategy5 对比回测脚本
同时运行两个策略，生成对比结果文件
"""

from pathlib import Path
from datetime import datetime

from test_strategy3 import testMultiSymbol as run_s3, INITIAL_CASH as CASH3
from test_strategy5 import testMultiSymbol as run_s5, INITIAL_CASH as CASH5

ROOT = Path(__file__).resolve().parent

SYMBOLS = ["BTC", "BNB", "SOL", "XRP", "ETH"]


def build_comparison(s3_results: list, s5_results: list) -> str:
    """生成 Strategy3 vs Strategy5 对比报告"""

    # 按币种+年份索引
    s3_map = {}
    for r in s3_results:
        key = (r["coin"], r["year"])
        s3_map[key] = r

    s5_map = {}
    for r in s5_results:
        key = (r["coin"], r["year"])
        s5_map[key] = r

    lines = []
    lines.append("=" * 130)
    lines.append("Strategy3 vs Strategy5 对比回测报告")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"回测区间: 2020-2025 | 初始资金: {CASH3} USDT")
    lines.append(f"达标标准: 夏普率 > 1.2, 最大回撤 < 15%")
    lines.append("=" * 130)

    # ── 逐年逐币种详细对比 ──
    for coin in SYMBOLS:
        lines.append("")
        lines.append(f"{'─' * 130}")
        lines.append(f"  {coin}USDT 逐年对比")
        lines.append(f"{'─' * 130}")

        header = (
            f"{'年份':<6} "
            f"│ {'S3收益':>8} {'S5收益':>8} {'Δ收益':>8} "
            f"│ {'S3交易':>6} {'S5交易':>6} {'Δ交易':>6} "
            f"│ {'S3胜率':>7} {'S5胜率':>7} "
            f"│ {'S3夏普':>7} {'S5夏普':>7} "
            f"│ {'S3回撤':>7} {'S5回撤':>7}"
        )
        lines.append(header)
        lines.append("-" * 130)

        coin_s3_returns = []
        coin_s5_returns = []
        coin_s3_trades = 0
        coin_s5_trades = 0
        coin_s3_won = 0
        coin_s5_won = 0
        coin_s3_sharpes = []
        coin_s5_sharpes = []
        coin_s3_dds = []
        coin_s5_dds = []

        for year in range(2020, 2026):
            key = (coin, year)
            s3 = s3_map.get(key)
            s5 = s5_map.get(key)

            if s3 is None and s5 is None:
                continue

            s3_ret = s3["totalReturn"] if s3 else None
            s5_ret = s5["totalReturn"] if s5 else None
            s3_trades = s3["totalTrades"] if s3 else 0
            s5_trades = s5["totalTrades"] if s5 else 0
            s3_wr = s3["winRate"] if s3 else 0
            s5_wr = s5["winRate"] if s5 else 0
            s3_sharpe = s3["sharpeRatio"] if s3 else None
            s5_sharpe = s5["sharpeRatio"] if s5 else None
            s3_dd = s3["maxDrawdown"] if s3 else 0
            s5_dd = s5["maxDrawdown"] if s5 else 0

            # 计算增量
            delta_ret = f"{s5_ret - s3_ret:+.2f}%" if (s3_ret is not None and s5_ret is not None) else "N/A"
            delta_trades = f"{s5_trades - s3_trades:+d}" if (s3 and s5) else "N/A"

            s3_ret_s = f"{s3_ret:.2f}%" if s3_ret is not None else "N/A"
            s5_ret_s = f"{s5_ret:.2f}%" if s5_ret is not None else "N/A"
            s3_sharpe_s = f"{s3_sharpe:.2f}" if s3_sharpe is not None else "N/A"
            s5_sharpe_s = f"{s5_sharpe:.2f}" if s5_sharpe is not None else "N/A"

            lines.append(
                f"{year:<6} "
                f"│ {s3_ret_s:>8} {s5_ret_s:>8} {delta_ret:>8} "
                f"│ {s3_trades:>6} {s5_trades:>6} {delta_trades:>6} "
                f"│ {s3_wr:>6.1f}% {s5_wr:>6.1f}% "
                f"│ {s3_sharpe_s:>7} {s5_sharpe_s:>7} "
                f"│ {s3_dd:>6.2f}% {s5_dd:>6.2f}%"
            )

            if s3_ret is not None:
                coin_s3_returns.append(s3_ret)
            if s5_ret is not None:
                coin_s5_returns.append(s5_ret)
            if s3:
                coin_s3_trades += s3_trades
                coin_s3_won += s3["wonTrades"]
                if s3_sharpe is not None:
                    coin_s3_sharpes.append(s3_sharpe)
                coin_s3_dds.append(s3_dd)
            if s5:
                coin_s5_trades += s5_trades
                coin_s5_won += s5["wonTrades"]
                if s5_sharpe is not None:
                    coin_s5_sharpes.append(s5_sharpe)
                coin_s5_dds.append(s5_dd)

        # 币种汇总
        years = len(coin_s3_returns) or len(coin_s5_returns) or 1
        s3_avg_ret = sum(coin_s3_returns) / len(coin_s3_returns) if coin_s3_returns else 0
        s5_avg_ret = sum(coin_s5_returns) / len(coin_s5_returns) if coin_s5_returns else 0
        s3_wr_total = coin_s3_won / coin_s3_trades * 100 if coin_s3_trades > 0 else 0
        s5_wr_total = coin_s5_won / coin_s5_trades * 100 if coin_s5_trades > 0 else 0
        s3_avg_sharpe = sum(coin_s3_sharpes) / len(coin_s3_sharpes) if coin_s3_sharpes else 0
        s5_avg_sharpe = sum(coin_s5_sharpes) / len(coin_s5_sharpes) if coin_s5_sharpes else 0
        s3_avg_dd = sum(coin_s3_dds) / len(coin_s3_dds) if coin_s3_dds else 0
        s5_avg_dd = sum(coin_s5_dds) / len(coin_s5_dds) if coin_s5_dds else 0

        lines.append("-" * 130)
        lines.append(
            f"{'均值':<6} "
            f"│ {s3_avg_ret:>7.2f}% {s5_avg_ret:>7.2f}% {s5_avg_ret - s3_avg_ret:>+7.2f}% "
            f"│ {coin_s3_trades:>6} {coin_s5_trades:>6} {coin_s5_trades - coin_s3_trades:>+6} "
            f"│ {s3_wr_total:>6.1f}% {s5_wr_total:>6.1f}% "
            f"│ {s3_avg_sharpe:>7.2f} {s5_avg_sharpe:>7.2f} "
            f"│ {s3_avg_dd:>6.2f}% {s5_avg_dd:>6.2f}%"
        )

    # ── 跨币种综合对比 ──
    lines.append("")
    lines.append("=" * 130)
    lines.append("跨币种综合对比")
    lines.append("=" * 130)

    all_s3 = {"returns": [], "trades": 0, "won": 0, "sharpes": [], "dds": []}
    all_s5 = {"returns": [], "trades": 0, "won": 0, "sharpes": [], "dds": []}

    for r in s3_results:
        all_s3["returns"].append(r["totalReturn"])
        all_s3["trades"] += r["totalTrades"]
        all_s3["won"] += r["wonTrades"]
        if r["sharpeRatio"] is not None:
            all_s3["sharpes"].append(r["sharpeRatio"])
        all_s3["dds"].append(r["maxDrawdown"])

    for r in s5_results:
        all_s5["returns"].append(r["totalReturn"])
        all_s5["trades"] += r["totalTrades"]
        all_s5["won"] += r["wonTrades"]
        if r["sharpeRatio"] is not None:
            all_s5["sharpes"].append(r["sharpeRatio"])
        all_s5["dds"].append(r["maxDrawdown"])

    n_s3 = len(all_s3["returns"]) or 1
    n_s5 = len(all_s5["returns"]) or 1

    lines.append(f"{'指标':<16} {'Strategy3':>12} {'Strategy5':>12} {'差异':>12}")
    lines.append("-" * 55)
    lines.append(f"{'平均年收益率':<16} {sum(all_s3['returns'])/n_s3:>11.2f}% {sum(all_s5['returns'])/n_s5:>11.2f}% {sum(all_s5['returns'])/n_s5 - sum(all_s3['returns'])/n_s3:>+11.2f}%")
    lines.append(f"{'总交易次数':<16} {all_s3['trades']:>12} {all_s5['trades']:>12} {all_s5['trades'] - all_s3['trades']:>+12}")
    s3_wr = all_s3["won"] / all_s3["trades"] * 100 if all_s3["trades"] > 0 else 0
    s5_wr = all_s5["won"] / all_s5["trades"] * 100 if all_s5["trades"] > 0 else 0
    lines.append(f"{'综合胜率':<16} {s3_wr:>11.1f}% {s5_wr:>11.1f}% {s5_wr - s3_wr:>+11.1f}%")
    s3_avg_sh = sum(all_s3["sharpes"]) / len(all_s3["sharpes"]) if all_s3["sharpes"] else 0
    s5_avg_sh = sum(all_s5["sharpes"]) / len(all_s5["sharpes"]) if all_s5["sharpes"] else 0
    lines.append(f"{'平均夏普比率':<16} {s3_avg_sh:>12.2f} {s5_avg_sh:>12.2f} {s5_avg_sh - s3_avg_sh:>+12.2f}")
    s3_avg_dd = sum(all_s3["dds"]) / len(all_s3["dds"]) if all_s3["dds"] else 0
    s5_avg_dd = sum(all_s5["dds"]) / len(all_s5["dds"]) if all_s5["dds"] else 0
    lines.append(f"{'平均最大回撤':<16} {s3_avg_dd:>11.2f}% {s5_avg_dd:>11.2f}% {s5_avg_dd - s3_avg_dd:>+11.2f}%")

    # 达标率统计
    s3_pass = sum(1 for r in s3_results
                  if r["sharpeRatio"] is not None and r["sharpeRatio"] > 1.2 and r["maxDrawdown"] < 15.0)
    s5_pass = sum(1 for r in s5_results
                  if r["sharpeRatio"] is not None and r["sharpeRatio"] > 1.2 and r["maxDrawdown"] < 15.0)
    s3_rate = s3_pass / len(s3_results) * 100 if s3_results else 0
    s5_rate = s5_pass / len(s5_results) * 100 if s5_results else 0
    lines.append(f"{'达标率':<16} {s3_rate:>11.1f}% {s5_rate:>11.1f}% {s5_rate - s3_rate:>+11.1f}%")
    lines.append(f"{'达标(夏普>1.2+回撤<15%)':<16} {s3_pass:>6}/{len(s3_results):<5} {s5_pass:>6}/{len(s5_results):<5}")

    # ── 结论 ──
    lines.append("")
    lines.append("=" * 130)
    lines.append("结论")
    lines.append("=" * 130)
    if s5_avg_sh > s3_avg_sh and s5_avg_dd < s3_avg_dd:
        lines.append("Strategy5 在夏普比率和回撤控制上均优于 Strategy3 ✓")
    elif s5_avg_sh > s3_avg_sh:
        lines.append("Strategy5 夏普比率更优，但回撤控制需关注")
    elif s5_avg_dd < s3_avg_dd:
        lines.append("Strategy5 回撤控制更优，但夏普比率需关注")
    else:
        lines.append("Strategy5 与 Strategy3 各有优劣，需结合具体场景选择")

    trade_diff = all_s5["trades"] - all_s3["trades"]
    lines.append(f"交易频率：Strategy5 比 Strategy3 多 {trade_diff} 笔交易 ({trade_diff/all_s3['trades']*100:+.1f}%)" if all_s3["trades"] > 0 else "交易频率：无数据")
    lines.append(f"达标率：Strategy5 {s5_rate:.1f}% vs Strategy3 {s3_rate:.1f}%")

    return "\n".join(lines)


def main():
    print("=" * 80)
    print("Strategy3 vs Strategy5 对比回测")
    print("=" * 80)

    # 运行 Strategy3
    print("\n>>> 运行 Strategy3 回测...")
    s3_results = run_s3()
    print(f"\nStrategy3 完成，共 {len(s3_results)} 条结果")

    # 运行 Strategy5
    print("\n>>> 运行 Strategy5 回测...")
    s5_results = run_s5()
    print(f"\nStrategy5 完成，共 {len(s5_results)} 条结果")

    # 生成对比报告
    print("\n>>> 生成对比报告...")
    report = build_comparison(s3_results, s5_results)

    # 保存报告
    report_path = ROOT / "compare_s3_vs_s5"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n对比报告已保存到: {report_path}")

    # 同时输出到控制台
    print("\n" + report)


if __name__ == "__main__":
    main()
