import argparse
import contextlib
import csv
import io
from itertools import product
from pathlib import Path

import backtrader as bt

from data.base import get_crypto_data
from trend.advanced_strategy import AdvancedStrategy


DEFAULT_SINGLE_PARAMS = {
    'printlog': True,
    'eventlog': True,
    'daily_adx_trend_threshold': 25,
    'daily_boll_compression_threshold': 0.05,
    'daily_boll_expansion_threshold': 0.10,
    'h4_volume_ratio_threshold': 1.20,
    'h4_breakout_buffer': 0.0015,
    'h4_breakout_body_ratio': 0.45,
    'h4_breakout_close_strength': 0.65,
    'h4_pullback_close_strength': 0.55,
    'h1_breakout_buffer': 0.0008,
    'h1_breakout_body_ratio': 0.35,
    'h1_breakout_close_strength': 0.60,
    'require_breakout_retest': True,
    'h1_retest_touch_buffer': 0.0015,
    'h1_retest_hold_buffer': 0.0005,
    'h1_retest_confirm_buffer': 0.0003,
    'h1_retest_body_ratio': 0.25,
    'h1_retest_close_strength': 0.55,
    'h1_retest_volume_ratio_threshold': 1.10,
    'h1_reversal_close_strength': 0.55,
    'h1_stop_atr_multiplier': 2.0,
    'signal_valid_bars': 4,
    'rr_ratio': 2.0,
    'risk_per_trade': 0.02,
    'trend_breakeven_rr': 1.0,
    'trend_trailing_activation_rr': 2.0,
    'trend_trailing_atr_multiplier': 3.0,
    'trend_ema_exit_buffer': 0.0020,
}

DEFAULT_PARAM_GRID = {
    'daily_adx_trend_threshold': [23, 25],
    'daily_boll_compression_threshold': [0.045, 0.05],
    'h4_breakout_buffer': [0.0010],
    'h4_volume_ratio_threshold': [1.25],
    'h1_retest_touch_buffer': [0.0015],
    'h1_retest_hold_buffer': [0.0005],
    'h1_retest_confirm_buffer': [0.0002, 0.0003, 0.0005],
    'h1_retest_body_ratio': [0.20, 0.25, 0.30],
    'h1_retest_volume_ratio_threshold': [1.00, 1.10, 1.20],
}


def parse_float_list(value):
    return [float(item.strip()) for item in value.split(',') if item.strip()]


def parse_int_list(value):
    return [int(item.strip()) for item in value.split(',') if item.strip()]


def extract_nested(mapping, keys, default=0):
    current = mapping or {}
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
        if current is None:
            return default
    return current


def format_metric(value, kind='float'):
    if kind == 'pct_ratio':
        return f'{value:.2%}'
    if kind == 'pct_value':
        return f'{value:.2f}%'
    if kind == 'int':
        return str(int(value))
    if kind == 'bool':
        return 'Y' if value else 'N'
    return f'{value:.4f}' if isinstance(value, float) else str(value)


def build_default_csv_path(symbol, start_year, end_year):
    filename = f'advanced_strategy_optimization_{symbol.lower()}_{start_year}_{end_year}.csv'
    return str(Path(__file__).resolve().parent / filename)


def build_result_row(rank, result):
    row = {
        'rank': rank,
        'score': result.get('score', score_result(result)),
        'symbol': result['symbol'],
        'start_year': result['start_year'],
        'end_year': result['end_year'],
        'final_value': result['final_value'],
        'return_pct': result['return_pct'],
        'sharpe_ratio': result['sharpe_ratio'],
        'trade_count': result['trade_count'],
        'win_rate': result['win_rate'],
        'max_drawdown': result['max_drawdown'],
    }
    row.update(result.get('params', {}))
    return row


def print_search_table(results, param_keys, top_n=5):
    rows = []
    display_columns = ['rank', 'score', 'return_pct', 'sharpe_ratio', 'win_rate', 'max_drawdown', 'trade_count', *param_keys]
    headers = {
        'rank': 'Rank',
        'score': 'Score',
        'return_pct': 'Return',
        'sharpe_ratio': 'Sharpe',
        'win_rate': 'WinRate',
        'max_drawdown': 'MaxDD',
        'trade_count': 'Trades',
    }
    kinds = {
        'rank': 'int',
        'score': 'float',
        'return_pct': 'pct_ratio',
        'sharpe_ratio': 'float',
        'win_rate': 'pct_ratio',
        'max_drawdown': 'pct_value',
        'trade_count': 'int',
    }

    for rank, result in enumerate(results[:top_n], start=1):
        row = build_result_row(rank, result)
        rows.append({
            column: format_metric(row.get(column, ''), kinds.get(column, 'float'))
            for column in display_columns
        })

    widths = {}
    for column in display_columns:
        header = headers.get(column, column)
        widths[column] = max(len(header), *(len(row[column]) for row in rows)) if rows else len(header)

    separator = '-+-'.join('-' * widths[column] for column in display_columns)
    header_line = ' | '.join(headers.get(column, column).ljust(widths[column]) for column in display_columns)

    print(f'\n参数搜索结果表 Top {top_n}')
    print(separator)
    print(header_line)
    print(separator)
    for row in rows:
        print(' | '.join(row[column].ljust(widths[column]) for column in display_columns))
    print(separator)


def write_results_csv(results, csv_path):
    if not results:
        return None

    destination = Path(csv_path).expanduser()
    if not destination.is_absolute():
        destination = Path(__file__).resolve().parent / destination
    destination.parent.mkdir(parents=True, exist_ok=True)

    param_keys = sorted({key for result in results for key in result.get('params', {}).keys()})
    fieldnames = [
        'rank',
        'score',
        'symbol',
        'start_year',
        'end_year',
        'final_value',
        'return_pct',
        'sharpe_ratio',
        'trade_count',
        'win_rate',
        'max_drawdown',
        *param_keys,
    ]

    with destination.open('w', newline='', encoding='utf-8-sig') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for rank, result in enumerate(results, start=1):
            writer.writerow(build_result_row(rank, result))

    return str(destination)


def build_cerebro(symbol, start_year, end_year, strategy_params=None):
    strategy_params = strategy_params or {}
    cerebro = bt.Cerebro()

    initial_cash = 5000
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.set_shortcash(True)
    cerebro.broker.setcommission(commission=0.001, margin=0.2, stocklike=False)
    cerebro.broker.set_slippage_perc(0.001)
    cerebro.broker.set_slippage_fixed(0.01)
    cerebro.broker.set_coc(True)

    trend_start_year = max(start_year - 1, 2017)

    data_daily = get_crypto_data(symbol, '1d', trend_start_year, end_year)
    cerebro.adddata(data_daily, name='daily')

    data_4h = get_crypto_data(symbol, '4h', trend_start_year, end_year)
    cerebro.adddata(data_4h, name='4h')

    data_1h = get_crypto_data(symbol, '1h', start_year, end_year)
    cerebro.adddata(data_1h, name='1h')

    cerebro.addstrategy(AdvancedStrategy, **strategy_params)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')

    return cerebro, initial_cash, trend_start_year


def run_backtest(symbol='ETH', start_year=2025, end_year=2025, strategy_params=None):
    strategy_params = strategy_params or {}
    cerebro, initial_cash, trend_start_year = build_cerebro(symbol, start_year, end_year, strategy_params)
    results = cerebro.run()
    strat = results[0]

    sharpe_ratio = strat.analyzers.sharpe.get_analysis()
    trade_analysis = strat.analyzers.trades.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()

    final_value = cerebro.broker.getvalue()
    return_pct = (final_value - initial_cash) / initial_cash
    sharpe_value = extract_nested(sharpe_ratio, ['sharperatio'], 0) or 0
    trade_count = extract_nested(trade_analysis, ['total', 'total'], 0)
    won_trades = extract_nested(trade_analysis, ['won', 'total'], 0)
    max_drawdown = extract_nested(drawdown, ['max', 'drawdown'], 0)
    win_rate = (won_trades / trade_count) if trade_count else 0

    return {
        'symbol': symbol,
        'start_year': start_year,
        'end_year': end_year,
        'trend_start_year': trend_start_year,
        'initial_cash': initial_cash,
        'final_value': final_value,
        'return_pct': return_pct,
        'sharpe_ratio': sharpe_value,
        'trade_count': trade_count,
        'won_trades': won_trades,
        'win_rate': win_rate,
        'max_drawdown': max_drawdown,
        'params': strategy_params,
    }


def score_result(result):
    trade_penalty = 0 if result['trade_count'] >= 3 else (3 - result['trade_count']) * 3
    return (
        result['return_pct'] * 100
        + result['sharpe_ratio'] * 5
        + result['win_rate'] * 10
        - result['max_drawdown'] * 0.8
        - trade_penalty
    )


def print_backtest_result(result, title='回测结果'):
    print(f'\n{title}')
    print('=' * 72)
    print(
        f"标的: {result['symbol']} | 区间: {result['start_year']}-{result['end_year']} | "
        f"趋势预热起点: {result['trend_start_year']}"
    )
    print(f"最终资金: {result['final_value']:.2f}")
    print(f"总收益率: {result['return_pct']:.4f}")
    print(f"夏普比率: {result['sharpe_ratio']:.4f}")
    print(f"交易次数: {result['trade_count']}")
    print(f"胜率: {result['win_rate']:.2%}")
    print(f"最大回撤: {result['max_drawdown']:.4f}%")
    print(f"参数: {result['params']}")


def run_backtest_for_search(symbol, start_year, end_year, strategy_params):
    if strategy_params.get('printlog'):
        return run_backtest(symbol=symbol, start_year=start_year, end_year=end_year, strategy_params=strategy_params)
    with contextlib.redirect_stdout(io.StringIO()):
        return run_backtest(symbol=symbol, start_year=start_year, end_year=end_year, strategy_params=strategy_params)


def run_parameter_search(symbol, start_year, end_year, base_params, param_grid, top_n=5, show_progress=False, show_table=False):
    grid_keys = list(param_grid.keys())
    grid_values = [param_grid[key] for key in grid_keys]
    combinations = list(product(*grid_values))
    total = len(combinations)
    results = []

    if show_progress:
        print(f'开始参数搜索，总组合数: {total}')
    for index, combo in enumerate(combinations, start=1):
        params = base_params.copy()
        params.update(dict(zip(grid_keys, combo)))
        if show_progress:
            print(f'[{index}/{total}] 测试参数: {params}')
        result = run_backtest_for_search(symbol, start_year, end_year, params)
        result['score'] = score_result(result)
        if show_progress:
            print(
                f"    -> 收益率: {result['return_pct']:.4f} | 夏普: {result['sharpe_ratio']:.4f} | "
                f"胜率: {result['win_rate']:.2%} | 回撤: {result['max_drawdown']:.4f}% | "
                f"交易数: {result['trade_count']} | 评分: {result['score']:.4f}"
            )
        results.append(result)

    results.sort(key=lambda item: item['score'], reverse=True)
    if show_table:
        print_search_table(results, grid_keys, top_n=top_n)
    return results


def calculate_robust_score(train_result, validation_result):
    consistency_penalty = (
        abs(train_result['return_pct'] - validation_result['return_pct']) * 100
        + abs(train_result['sharpe_ratio'] - validation_result['sharpe_ratio']) * 2
        + abs(train_result['win_rate'] - validation_result['win_rate']) * 10
    )
    robust_score = validation_result['score'] * 0.7 + train_result['score'] * 0.3 - consistency_penalty
    return robust_score, consistency_penalty


def run_robust_parameter_search(
    symbol,
    train_start_year,
    train_end_year,
    validation_start_year,
    validation_end_year,
    base_params,
    param_grid,
    candidate_pool_size=10,
    show_progress=False,
):
    train_results = run_parameter_search(
        symbol=symbol,
        start_year=train_start_year,
        end_year=train_end_year,
        base_params=base_params,
        param_grid=param_grid,
        show_progress=show_progress,
        show_table=False,
    )
    candidate_pool = train_results[:max(candidate_pool_size, 1)]
    robust_results = []

    if show_progress:
        print(f'开始验证稳健性，候选参数数: {len(candidate_pool)}')

    for index, train_result in enumerate(candidate_pool, start=1):
        params = train_result['params'].copy()
        if show_progress:
            print(f'[{index}/{len(candidate_pool)}] 验证参数: {params}')
        validation_result = run_backtest_for_search(symbol, validation_start_year, validation_end_year, params)
        validation_result['score'] = score_result(validation_result)
        robust_score, consistency_penalty = calculate_robust_score(train_result, validation_result)
        robust_results.append({
            'params': params,
            'robust_score': robust_score,
            'consistency_penalty': consistency_penalty,
            'train_result': train_result,
            'validation_result': validation_result,
        })

    robust_results.sort(key=lambda item: item['robust_score'], reverse=True)
    return robust_results


def print_robust_optimization_result(result, title='稳健参数筛选结果'):
    train_result = result['train_result']
    validation_result = result['validation_result']
    print(f'\n{title}')
    print('=' * 72)
    print(f"稳健评分: {result['robust_score']:.4f}")
    print(f"一致性惩罚: {result['consistency_penalty']:.4f}")
    print(
        f"训练期: {train_result['start_year']}-{train_result['end_year']} | 收益率: {train_result['return_pct']:.4f} | "
        f"夏普: {train_result['sharpe_ratio']:.4f} | 交易次数: {train_result['trade_count']}"
    )
    print(
        f"验证期: {validation_result['start_year']}-{validation_result['end_year']} | "
        f"收益率: {validation_result['return_pct']:.4f} | 夏普: {validation_result['sharpe_ratio']:.4f} | "
        f"交易次数: {validation_result['trade_count']}"
    )
    print(f"参数: {result['params']}")


def build_base_params(args):
    params = DEFAULT_SINGLE_PARAMS.copy()
    params.update({
        'printlog': args.printlog,
        'eventlog': args.eventlog,
        'daily_adx_trend_threshold': args.daily_adx_trend_threshold,
        'daily_boll_compression_threshold': args.daily_boll_compression_threshold,
        'daily_boll_expansion_threshold': args.daily_boll_expansion_threshold,
        'h4_volume_ratio_threshold': args.h4_volume_ratio_threshold,
        'h4_breakout_buffer': args.h4_breakout_buffer,
        'h4_breakout_body_ratio': args.h4_breakout_body_ratio,
        'h4_breakout_close_strength': args.h4_breakout_close_strength,
        'h4_pullback_close_strength': args.h4_pullback_close_strength,
        'h1_breakout_buffer': args.h1_breakout_buffer,
        'h1_breakout_body_ratio': args.h1_breakout_body_ratio,
        'h1_breakout_close_strength': args.h1_breakout_close_strength,
        'require_breakout_retest': args.require_breakout_retest,
        'h1_retest_touch_buffer': args.h1_retest_touch_buffer,
        'h1_retest_hold_buffer': args.h1_retest_hold_buffer,
        'h1_retest_confirm_buffer': args.h1_retest_confirm_buffer,
        'h1_retest_body_ratio': args.h1_retest_body_ratio,
        'h1_retest_close_strength': args.h1_retest_close_strength,
        'h1_retest_volume_ratio_threshold': args.h1_retest_volume_ratio_threshold,
        'h1_reversal_close_strength': args.h1_reversal_close_strength,
        'h1_stop_atr_multiplier': args.h1_stop_atr_multiplier,
        'signal_valid_bars': args.signal_valid_bars,
        'rr_ratio': args.rr_ratio,
        'risk_per_trade': args.risk_per_trade,
        'trend_breakeven_rr': args.trend_breakeven_rr,
        'trend_trailing_activation_rr': args.trend_trailing_activation_rr,
        'trend_trailing_atr_multiplier': args.trend_trailing_atr_multiplier,
        'trend_ema_exit_buffer': args.trend_ema_exit_buffer,
    })
    return params


def build_param_grid(args):
    return {
        'daily_adx_trend_threshold': parse_int_list(args.grid_daily_adx),
        'daily_boll_compression_threshold': parse_float_list(args.grid_compression),
        'h4_breakout_buffer': parse_float_list(args.grid_breakout_buffer),
        'h4_volume_ratio_threshold': parse_float_list(args.grid_volume_ratio),
        'h1_retest_touch_buffer': parse_float_list(args.grid_retest_touch),
        'h1_retest_hold_buffer': parse_float_list(args.grid_retest_hold),
        'h1_retest_confirm_buffer': parse_float_list(args.grid_retest_confirm),
        'h1_retest_body_ratio': parse_float_list(args.grid_retest_body),
        'h1_retest_volume_ratio_threshold': parse_float_list(args.grid_retest_volume_ratio),
    }


def parse_args():
    parser = argparse.ArgumentParser(description='AdvancedStrategy 参数化回测与参数搜索脚本')
    parser.add_argument('--symbol', default='ETH')
    parser.add_argument('--start-year', type=int, default=2025)
    parser.add_argument('--end-year', type=int, default=2025)
    parser.add_argument('--optimize', action='store_true', help='开启参数搜索')
    parser.add_argument('--robust-optimize', action='store_true', help='按训练期/验证期筛选稳健参数，降低过拟合')
    parser.add_argument('--candidate-pool-size', type=int, default=10)
    parser.add_argument('--top-n', type=int, default=5)
    parser.add_argument('--printlog', action='store_true')
    parser.add_argument('--eventlog', action='store_true', help='输出关键事件日志')
    parser.add_argument('--verbose-search', action='store_true', help='输出参数搜索进度明细')

    parser.add_argument('--daily-adx-trend-threshold', type=int, default=DEFAULT_SINGLE_PARAMS['daily_adx_trend_threshold'])
    parser.add_argument('--daily-boll-compression-threshold', type=float, default=DEFAULT_SINGLE_PARAMS['daily_boll_compression_threshold'])
    parser.add_argument('--daily-boll-expansion-threshold', type=float, default=DEFAULT_SINGLE_PARAMS['daily_boll_expansion_threshold'])
    parser.add_argument('--h4-volume-ratio-threshold', type=float, default=DEFAULT_SINGLE_PARAMS['h4_volume_ratio_threshold'])
    parser.add_argument('--h4-breakout-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['h4_breakout_buffer'])
    parser.add_argument('--h4-breakout-body-ratio', type=float, default=DEFAULT_SINGLE_PARAMS['h4_breakout_body_ratio'])
    parser.add_argument('--h4-breakout-close-strength', type=float, default=DEFAULT_SINGLE_PARAMS['h4_breakout_close_strength'])
    parser.add_argument('--h4-pullback-close-strength', type=float, default=DEFAULT_SINGLE_PARAMS['h4_pullback_close_strength'])
    parser.add_argument('--h1-breakout-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['h1_breakout_buffer'])
    parser.add_argument('--h1-breakout-body-ratio', type=float, default=DEFAULT_SINGLE_PARAMS['h1_breakout_body_ratio'])
    parser.add_argument('--h1-breakout-close-strength', type=float, default=DEFAULT_SINGLE_PARAMS['h1_breakout_close_strength'])
    parser.add_argument(
        '--disable-breakout-retest',
        action='store_false',
        dest='require_breakout_retest',
        default=DEFAULT_SINGLE_PARAMS['require_breakout_retest'],
        help='关闭 1H 回踩突破位二次确认',
    )
    parser.add_argument('--h1-retest-touch-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_touch_buffer'])
    parser.add_argument('--h1-retest-hold-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_hold_buffer'])
    parser.add_argument('--h1-retest-confirm-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_confirm_buffer'])
    parser.add_argument('--h1-retest-body-ratio', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_body_ratio'])
    parser.add_argument('--h1-retest-close-strength', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_close_strength'])
    parser.add_argument('--h1-retest-volume-ratio-threshold', type=float, default=DEFAULT_SINGLE_PARAMS['h1_retest_volume_ratio_threshold'])
    parser.add_argument('--h1-reversal-close-strength', type=float, default=DEFAULT_SINGLE_PARAMS['h1_reversal_close_strength'])
    parser.add_argument('--h1-stop-atr-multiplier', type=float, default=DEFAULT_SINGLE_PARAMS['h1_stop_atr_multiplier'])
    parser.add_argument('--signal-valid-bars', type=int, default=DEFAULT_SINGLE_PARAMS['signal_valid_bars'])
    parser.add_argument('--rr-ratio', type=float, default=DEFAULT_SINGLE_PARAMS['rr_ratio'])
    parser.add_argument('--risk-per-trade', type=float, default=DEFAULT_SINGLE_PARAMS['risk_per_trade'])
    parser.add_argument('--trend-breakeven-rr', type=float, default=DEFAULT_SINGLE_PARAMS['trend_breakeven_rr'])
    parser.add_argument('--trend-trailing-activation-rr', type=float, default=DEFAULT_SINGLE_PARAMS['trend_trailing_activation_rr'])
    parser.add_argument('--trend-trailing-atr-multiplier', type=float, default=DEFAULT_SINGLE_PARAMS['trend_trailing_atr_multiplier'])
    parser.add_argument('--trend-ema-exit-buffer', type=float, default=DEFAULT_SINGLE_PARAMS['trend_ema_exit_buffer'])
    parser.add_argument('--csv-output', default='')

    parser.add_argument(
        '--grid-daily-adx',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['daily_adx_trend_threshold']),
    )
    parser.add_argument(
        '--grid-compression',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['daily_boll_compression_threshold']),
    )
    parser.add_argument(
        '--grid-breakout-buffer',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h4_breakout_buffer']),
    )
    parser.add_argument(
        '--grid-volume-ratio',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h4_volume_ratio_threshold']),
    )
    parser.add_argument(
        '--grid-retest-touch',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h1_retest_touch_buffer']),
    )
    parser.add_argument(
        '--grid-retest-hold',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h1_retest_hold_buffer']),
    )
    parser.add_argument(
        '--grid-retest-confirm',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h1_retest_confirm_buffer']),
    )
    parser.add_argument(
        '--grid-retest-body',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h1_retest_body_ratio']),
    )
    parser.add_argument(
        '--grid-retest-volume-ratio',
        default=','.join(str(item) for item in DEFAULT_PARAM_GRID['h1_retest_volume_ratio_threshold']),
    )

    return parser.parse_args()


def main():
    args = parse_args()
    base_params = build_base_params(args)

    if args.optimize or args.robust_optimize:
        param_grid = build_param_grid(args)

        if args.robust_optimize:
            if args.start_year >= args.end_year:
                raise ValueError('稳健优化至少需要两个年份，例如 --start-year 2018 --end-year 2019')
            robust_results = run_robust_parameter_search(
                symbol=args.symbol,
                train_start_year=args.start_year,
                train_end_year=args.end_year - 1,
                validation_start_year=args.end_year,
                validation_end_year=args.end_year,
                base_params=base_params,
                param_grid=param_grid,
                candidate_pool_size=args.candidate_pool_size,
                show_progress=args.verbose_search,
            )
            if robust_results:
                best_result = robust_results[0]
                print_robust_optimization_result(best_result)
                combined_result = run_backtest(
                    symbol=args.symbol,
                    start_year=args.start_year,
                    end_year=args.end_year,
                    strategy_params=best_result['params'],
                )
                print_backtest_result(combined_result, title='稳健参数全区间回测结果')
            return

        results = run_parameter_search(
            symbol=args.symbol,
            start_year=args.start_year,
            end_year=args.end_year,
            base_params=base_params,
            param_grid=param_grid,
            top_n=args.top_n,
            show_progress=args.verbose_search,
            show_table=args.verbose_search,
        )
        if results:
            csv_path = write_results_csv(
                results,
                args.csv_output or build_default_csv_path(args.symbol, args.start_year, args.end_year),
            )
            print(f'CSV 已输出: {csv_path}')
            print_backtest_result(results[0], title='最佳参数回测结果')
        return

    result = run_backtest(
        symbol=args.symbol,
        start_year=args.start_year,
        end_year=args.end_year,
        strategy_params=base_params,
    )
    print_backtest_result(result)


if __name__ == '__main__':
    main()
