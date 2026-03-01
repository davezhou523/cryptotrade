"""
下载加密货币数据到指定目录
- ETH 日线数据（2025年1月到现在）
- BTC 日线数据（2025年1月到现在）
- BTC 4小时数据（2025年1月到现在）
"""
import sys
import os
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from data.binance import BinanceDataFetcher
# 设置API密钥
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"

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
    下载ETH和BTC的不同时间周期数据，每一年一个文件
    """
    # 解析命令行参数
    symbol = "ETH"
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    
    # 验证参数
    if symbol not in ["ETH", "BTC"]:
        print("错误：只支持ETH或BTC")
        return
    
    # 创建数据获取器
    fetcher = BinanceDataFetcher(api_key=API_KEY)
    
    # 下载指定加密货币各周期数据（2017-2025年，每年一个文件）
    save_dir = symbol
    intervals = ["1w", "1d", "4h", "1h"]
    intervals = ["15m"]
    #2018 15m 数据下载失败，提示：Binance API error: 1002, Invalid symbol.
    # 从2017年到2025年，每年下载一次
    for year in range(2020, 2025):
        start_time = datetime(year, 1, 1)
        end_time = datetime(year, 12, 31)
        
        print(f"\n=== 开始下载{symbol} {year}年数据 ===")
        
        for interval in intervals:
            download_data(
                fetcher=fetcher,
                symbol=f"{symbol}USDT",
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                save_dir=save_dir
            )
    
    print(f"\n所有{symbol}数据下载任务已完成！")

if __name__ == "__main__":
    main()