"""
下载 Binance ETH 数据到指定目录（按年保存一个文件）
- 存储目录: data/ETH/binance
- 当前配置时间范围: 2020 年
"""
import sys
import os
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.binance import BinanceDataFetcher
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
    从 Binance 下载 ETHUSDT 永续 1h K线到 data/ETH/binance（按年一个文件）。
    """
    symbol = "ETH"

    # Binance 交易对格式为 ETHUSDT
    binance_symbol = f"{symbol}USDT"

    # 创建数据获取器（永续合约）
    fetcher = BinanceDataFetcher(market_type="futures")

    # 固定存储目录：data/ETH/binance
    save_dir = os.path.join(os.path.dirname(__file__), "ETH", "binance")

    intervals = ["5m", "15m", "1h", "4h", "1d"]
    now_utc = datetime.now(timezone.utc)

    for year in range(2018, 2019):
        start_time = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        end_time = min(end_time, now_utc)

        if start_time >= end_time:
            print(f"{symbol} {year} 年在未来区间，已跳过。")
            continue

        print(f"\n=== 开始下载 {symbol} {year} 年数据 ===")

        for interval in intervals:
            download_data(
                fetcher=fetcher,
                symbol=binance_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                save_dir=save_dir
            )

    print(f"\n所有 {symbol} 数据下载任务已完成！")

if __name__ == "__main__":
    main()