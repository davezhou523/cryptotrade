"""
下载加密货币数据到指定目录
- ETH 日线数据（2025年1月到现在）
- BTC 日线数据（2025年1月到现在）
- BTC 4小时数据（2025年1月到现在）
"""

from datetime import datetime
from data import BinanceDataFetcher

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
    下载ETH和BTC的不同时间周期数据
    """
    # 设置时间参数
    start_time = datetime(2025, 1, 1)
    end_time = datetime.now()
    
    # 创建数据获取器
    fetcher = BinanceDataFetcher(api_key=API_KEY)
    
    # 下载ETH 1小时线数据
    download_data(
        fetcher=fetcher,
        symbol="ETHUSDT",
        interval="15m",
        start_time=start_time,
        end_time=end_time,
        save_dir="ETH"
    )

    # 下载BTC日线和4小时数据到指定目录
    btc_save_dir = "BTC"
    
    # 下载BTC日线数据
    # download_data(
    #     fetcher=fetcher,
    #     symbol="BTCUSDT",
    #     interval="1d",
    #     start_time=start_time,
    #     end_time=end_time,
    #     save_dir=btc_save_dir
    # )
    
    # 下载BTC 4小时数据
    # download_data(
    #     fetcher=fetcher,
    #     symbol="BTCUSDT",
    #     interval="4h",
    #     start_time=start_time,
    #     end_time=end_time,
    #     save_dir=btc_save_dir
    # )
    # 下载BTC 1小时数据
    download_data(
        fetcher=fetcher,
        symbol="BTCUSDT",
        interval="15m",
        start_time=start_time,
        end_time=end_time,
        save_dir=btc_save_dir
    )
    
    print("\n所有数据下载任务已完成！")

if __name__ == "__main__":
    main()