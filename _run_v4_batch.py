from pathlib import Path
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy3 import Strategy3


ROOT = Path(__file__).resolve().parent

PARAMS = dict(
    risk_per_trade=0.015,
    leverage=5.0,
    max_leverage_ratio=0.89,
    max_position_size=0.29,
    min_holding_bars=4,
    ema_exit_confirm_bars=2,
    ema_exit_buffer_atr=0.22,
    volatility_scaling=True,
    dynamic_risk_adjustment=True,
    require_both_entry_signals=True,
    printlog=True,
    eventlog=True,
)


def run_year(year: int) -> str:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(5000.0)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        data_files = [
            ("4H", f"data/ETH/binance/ethusdt_4h_{year}0101_{year}1231.csv"),
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
                    open="open",
                    high="high",
                    low="low",
                    close="close",
                    volume="volume",
                )
                datas.append(data)
                print(f"成功加载 {timeframe} 数据: {filepath}，共 {len(df)} 行")
            except Exception as exc:
                print(f"加载数据失败 {filepath}: {exc}")

        if len(datas) < 3:
            print(f"错误: 有效数据不足，期望3个周期(4H/1H/15M)，实际 {len(datas)} 个")
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
        trade_analysis = strat.analyzers.trades.get_analysis()
        sharpe_ratio = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()

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


def main():
    for year in range(2020, 2026):
        output = run_year(year)
        (ROOT / f"res{year}_4").write_text(output, encoding="utf-16")
        print(f"done {year}")


if __name__ == "__main__":
    main()
