"""
下载 Gate ETH 数据到指定目录（按年保存一个文件）
- 存储目录: data/ETH/gate
- 时间范围: 2017 年到 2026 年
"""
import sys
import os
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.gateio import GateioDataFetcher
def download_data(fetcher, symbol, interval, start_time, end_time, save_dir):
    """
    下载指定加密货币的数据
    :param fetcher: 数据获取器实例
    :param symbol: 交易对
    :param interval: 时间间隔
    :param start_time: 开始时间
    :param end_time: 结束时间
    :param save_dir: 保存目录
    :return: 是否下载成功
    """
    print(f"\n开始下载 {symbol} {interval} 数据...")
    csv_file = fetcher.fetch_klines(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        save_dir=save_dir
    )
    
    if csv_file:
        print(f"{symbol} {interval} 数据下载完成，保存到: {csv_file}")
        return True
    else:
        print(f"{symbol} {interval} 数据下载失败")
        return False


def main():
    """
    下载 Gate ETH 多周期数据（2017-2026），每年一个文件。
    """
    symbol = "ETH"

    # Gate 交易对格式为 ETH_USDT
    gate_symbol = f"{symbol}_USDT"

    # 创建数据获取器（K线为公开接口，无需 API Key）
    fetcher = GateioDataFetcher()

    # 固定存储目录：data/ETH/gate
    save_dir = os.path.join(os.path.dirname(__file__), "ETH", "gate")

    # 方案一：仅下载可稳定回溯的较大周期（覆盖 2024）
    intervals = ["4h"]

    interval_seconds = {
        "1d": 24 * 60 * 60,
        "4h": 4 * 60 * 60,
        "1h": 60 * 60,
        "15m": 15 * 60,
    }

    # Gate 常见历史回溯上限：10000 根，预留安全缓冲
    max_lookback_points = 9950
    now_utc = datetime.now(timezone.utc)

    for year in range(2021, 2022):
        year_start = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        year_end = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

        print(f"\n=== 开始下载 {symbol} {year} 年数据 ===")

        for interval in intervals:
            oldest_allowed = now_utc - timedelta(
                seconds=max_lookback_points * interval_seconds[interval]
            )

            start_time = max(year_start, oldest_allowed)
            end_time = min(year_end, now_utc)

            if start_time >= end_time:
                print(f"{symbol} {interval} {year} 年超出可回溯范围，已跳过。")
                continue

            download_data(
                fetcher=fetcher,
                symbol=gate_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                save_dir=save_dir
            )

    print(f"\n所有 {symbol} Gate 数据下载任务已完成！")

if __name__ == "__main__":
    main()