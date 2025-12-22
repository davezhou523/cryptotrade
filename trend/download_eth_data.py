"""
下载ETH 4小时周期数据（2025年1月到现在）到指定目录
"""

import sys
import os
from datetime import datetime
from data.binance import BinanceDataFetcher

# 设置API密钥
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"

def main():
    """
    下载ETH 4小时周期数据
    """
    # 设置参数
    symbol = "ETHUSDT"
    interval = "4h"
    start_time = datetime(2025, 1, 1)
    end_time = datetime.now()
    save_dir = "./data/ETH"
    
    # 创建数据获取器
    fetcher = BinanceDataFetcher(api_key=API_KEY)
    
    # 下载数据
    csv_file = fetcher.fetch_klines(
        symbol=symbol,
        interval=interval,
        start_time=start_time,
        end_time=end_time,
        save_dir=save_dir
    )
    
    if csv_file:
        print(f"数据下载完成，保存到: {csv_file}")
    else:
        print("数据下载失败")

if __name__ == "__main__":
    main()
