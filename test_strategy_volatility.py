#!/usr/bin/env python3
"""
震荡策略v4 回测脚本
多周期架构：4H震荡评分 → 1H BB区间 → 15M入场执行

测试2020-2025年ETH/USDT数据
"""

from pathlib import Path
import contextlib
import io

import backtrader as bt
import pandas as pd

from trend.strategy_volatility import StrategyVolatility

ROOT = Path(__file__).resolve().parent

# ====== 策略参数配置 ======
PARAMS = dict(
    # 日志
    printlog=False,
    eventlog=False,
    debuglog=False,

    # 4H 震荡判断（评分制）
    h4_adx_period=14,
    h4_adx_threshold=20,           # ADX<20 → +1分
    h4_ema_fast=21,
    h4_ema_slow=55,
    h4_ema_closeness=0.005,        # EMA差距<0.5% → +1分
    h4_atr_period=14,
    h4_osc_score_min=2,            # 评分>=2 → 震荡

    # 1H 区间（BB）
    h1_bb_period=20,
    h1_bb_dev=2.0,

    # 15M 入场信号
    m15_bb_period=20,
    m15_bb_dev=2.5,                # 更宽的BB，信号更可靠
    m15_rsi_period=14,
    m15_rsi_long=30,               # RSI超卖
    m15_rsi_short=70,              # RSI超买
    m15_rsi_confirm_long=32,       # RSI从<30回升到>32确认做多
    m15_rsi_confirm_short=68,      # RSI从>70回落到<68确认做空

    # 15M K线形态
    use_pin_bar=True,
    use_engulfing=True,
    pin_bar_ratio=2.0,             # 影线>=2倍实体

    # 入场信号强度
    min_signals=2,                 # 至少2个15M信号同时满足
    require_bb_bounce=True,        # 必须有BB反弹确认

    # 1H区间接近度
    zone_proximity=0.2,            # 价格在1H BB 20%带宽内视为接近

    # 假突破
    fake_breakout=True,            # 启用假突破检测

    # 1H K线方向过滤
    use_h1_candle_filter=True,     # 做多须1H阳线，做空须1H阴线

    # 4H趋势方向过滤
    use_h4_trend_filter=False,     # 关闭（测试表明有害）

    # 止损
    sl_method='h1bb',              # 1H BB轨道止损
    sl_atr_offset=0.3,             # 止损距1H BB轨道0.3×1H_ATR

    # 移动止损（关闭）
    use_trailing_stop=False,
    trail_atr_mult=0,
    trail_activate=0,

    # R:R过滤（关闭）
    min_rr=0,

    # 时间止损（关闭）
    use_time_stop=False,
    max_bars=0,

    # 连亏过滤（关闭）
    use_consec_loss_filter=False,
    max_consec_losses=0,

    # 保本止损（核心改进）
    use_breakeven_stop=True,       # 启用保本止损
    breakeven_activate=0.6,        # 盈利达60%TP时移动SL到成本

    # 阶梯追踪（保本后进一步锁定利润）
    use_stepped_trail=True,        # 启用阶梯追踪
    trail_step1_pct=0.9,           # 价格达TP的90%时
    trail_step1_sl=0.65,           # SL移到TP距离的65%（锁定大部分利润）
    trail_step2_pct=0,             # 第二阶梯（关闭）
    trail_step2_sl=0,

    # 1H BB宽度过滤（关闭）
    min_h1_bb_width=0,

    # 1H RSI过滤（关闭）
    use_h1_rsi_filter=False,
    h1_rsi_period=14,
    h1_rsi_long_max=0,
    h1_rsi_short_min=0,

    # 止盈
    tp_method='band',              # 1H BB对侧轨道止盈（高R:R比）
    tp_atr_offset=0.0,
    split_tp_ratio=0,              # 分批止盈比例（0=不分批）

    # 仓位
    risk_per_trade=0.0055,         # 单笔风险0.55%（控制回撤≤15%）
    risk_after_win=0,              # 动态仓位（关闭）
    risk_after_loss=0,
    m15_atr_period=14,
    leverage=2.0,                  # 2倍杠杆（降低回撤）
    max_leverage_ratio=0.80,
    max_positions=1,

    # ML信号过滤（默认关闭，训练后启用）
    use_ml_filter=False,
    ml_model_path='',
    ml_prob_threshold=0.55,
    ml_collect_data=False,
)


def run_year(year: int, params: dict = None) -> str:
    """运行指定年份的策略回测"""
    if params is None:
        params = PARAMS

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        cerebro = bt.Cerebro()
        cerebro.broker.setcash(10000.0)
        cerebro.broker.set_shortcash(True)
        cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
        cerebro.broker.set_slippage_perc(0.001)
        cerebro.broker.set_coc(True)

        data_files = [
            ("15M", f"data/ETH/binance/ethusdt_15m_{year}0101_{year}1231.csv"),
            ("1H", f"data/ETH/binance/ethusdt_1h_{year}0101_{year}1231.csv"),
            ("4H", f"data/ETH/binance/ethusdt_4h_{year}0101_{year}1231.csv"),
        ]

        datas = []
        for timeframe, filepath in data_files:
            try:
                df = pd.read_csv(ROOT / filepath, parse_dates=["datetime"], index_col="datetime")
                if df.empty:
                    print(f"跳过空数据文件 {timeframe}: {filepath}")
                    continue
                data = bt.feeds.PandasData(
                    dataname=df, datetime=None,
                    open='open', high='high', low='low',
                    close='close', volume='volume', openinterest=-1)
                datas.append(data)
                print(f"成功加载 {timeframe} 数据: {filepath}，共 {len(df)} 行")
            except Exception as exc:
                print(f"加载数据失败 {filepath}: {exc}")

        if len(datas) < 3:
            print(f"错误: 数据不足，需要4H+1H+15M，仅加载{len(datas)}个")
            return buffer.getvalue()

        for data in datas:
            cerebro.adddata(data)

        cerebro.addstrategy(StrategyVolatility, **params)

        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")
        cerebro.addanalyzer(bt.analyzers.SharpeRatio_A, _name="sharpe",
                          timeframe=bt.TimeFrame.Days, compression=1,
                          riskfreerate=0.0, annualize=True)
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")

        print("=== 开始震荡策略v4回测 ===")
        results = cerebro.run()

        if not results:
            print("回测没有产生结果")
            return buffer.getvalue()

        strat = results[0]
        ta = strat.analyzers.trades.get_analysis()
        sharpe_ratio = strat.analyzers.sharpe.get_analysis()
        dd = strat.analyzers.drawdown.get_analysis()

        print("\n=== 震荡策略v4回测结果 ===")
        final = cerebro.broker.getvalue()
        ret = (final - 10000) / 10000 * 100
        print(f"最终资金: {final:.2f}")
        print(f"总收益率: {ret:.2f}%")

        trades = ta.get('total', {}).get('total', 0) if 'total' in ta else 0
        won = ta.get('won', {}).get('total', 0) if 'won' in ta else 0
        wr = won / trades * 100 if trades > 0 else 0
        print(f"交易次数: {trades}")
        if trades > 0:
            print(f"胜率: {wr:.2f}%")

        sharpe_val = sharpe_ratio.get("sharperatio")
        print(f"夏普比率: {sharpe_val:.2f}" if sharpe_val is not None else "夏普比率: 无足够数据计算")

        if "max" in dd:
            print(f"最大回撤: {dd['max']['drawdown']:.2f}%")

    return buffer.getvalue()


def test_volatility_strategy():
    """运行2020-2025年回测"""
    print("震荡策略v4 回测 (2020-2025)")
    print("架构：4H震荡评分 → 1H BB区间 → 15M入场 + 保本止损")
    print("=" * 55)

    for year in range(2020, 2026):
        output = run_year(year)
        (ROOT / f"res{year}_volatility").write_text(output, encoding="utf-16")
        lines = output.strip().split('\n')
        for line in lines:
            if any(k in line for k in ['总收益率', '交易次数', '胜率', '夏普比率', '最大回撤']):
                print(f"  {line.strip()}")

    print("=" * 55)
    print("全部年份回测完成！结果已保存到 res{年份}_volatility 文件")


if __name__ == "__main__":
    test_volatility_strategy()
