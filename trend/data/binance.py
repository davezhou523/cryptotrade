"""
Binance数据获取器实现
"""

import requests
import time
import pandas as pd
import os
from datetime import datetime
from .base import DataFetcher


class BinanceDataFetcher(DataFetcher):
    """
    Binance数据获取器，实现从Binance获取K线数据的功能
    """
    
    def __init__(self, api_key: str = None):
        """
        初始化Binance数据获取器
        :param api_key: Binance API密钥（可选，部分接口需要）
        """
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.api_key = api_key
        self.limit = 1000  # Binance API最大限制
        self.interval_map = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '8h': 8 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '3d': 3 * 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000,
            '1M': 30 * 24 * 60 * 60 * 1000  # 近似值
        }
    
    def fetch_klines(self, symbol: str, interval: str, start_time: datetime, end_time: datetime, save_dir: str = None) -> str | None:
        """
        获取K线数据，支持获取超过1000条的数据（通过循环请求实现）
        :param symbol: 交易对
        :param interval: 时间间隔
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param save_dir: 保存目录（可选）
        :return: 保存数据的CSV文件名
        """
        all_data = []
        current_start_time = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)
        
        # API请求头
        headers = {}
        if self.api_key:
            headers['X-MBX-APIKEY'] = self.api_key
        
        try:
            # 循环请求数据，直到获取所有数据
            while True:
                params = {
                    'symbol': symbol,
                    'interval': interval,
                    'limit': self.limit,
                    'startTime': current_start_time,
                    'endTime': end_time_ms
                }
                
                # 发送请求
                response = requests.get(self.base_url, params=params, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    break  # 没有更多数据
                
                # 添加到所有数据
                all_data.extend(data)
                
                # 获取最后一条数据的时间戳，作为下一次请求的开始时间
                last_timestamp = data[-1][0]
                current_start_time = last_timestamp + self.get_interval_ms(interval)
                
                # 如果请求的数据少于限制，说明已经获取完所有数据
                if len(data) < self.limit:
                    break
                
                # 如果设置了结束时间，检查是否已经超过
                if current_start_time >= end_time_ms:
                    break
                
                # 添加延迟，避免超过API请求频率限制
                time.sleep(0.1)
            
            # 处理数据格式，使其适合Backtrader
            processed_data = []
            for item in all_data:
                timestamp = datetime.fromtimestamp(item[0] / 1000).strftime('%Y-%m-%d %H:%M:%S')
                processed_data.append([
                    timestamp,
                    float(item[1]),  # open
                    float(item[2]),  # high
                    float(item[3]),  # low
                    float(item[4]),  # close
                    float(item[5])  # volume
                ])
            
            # 保存为CSV文件
            df = pd.DataFrame(processed_data, columns=['datetime', 'open', 'high', 'low', 'close', 'volume'])
            
            # 生成带有时间范围的文件名
            start_str = start_time.strftime('%Y%m%d')
            end_str = end_time.strftime('%Y%m%d')
            filename = f'{symbol.lower()}_{interval}_{start_str}_{end_str}.csv'
            
            # 确定保存路径
            if save_dir:
                # 确保保存目录存在
                os.makedirs(save_dir, exist_ok=True)
                file_path = os.path.join(save_dir, filename)
            else:
                file_path = filename
            
            df.to_csv(file_path, index=False)
            print(f"已获取{len(df)}条K线数据并保存到{file_path}")
            return file_path
        except Exception as e:
            print(f"获取数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_supported_intervals(self) -> list:
        """
        获取支持的时间间隔列表
        :return: 时间间隔列表
        """
        return list(self.interval_map.keys())
    
    def get_interval_ms(self, interval: str) -> int:
        """
        获取不同时间间隔对应的毫秒数
        :param interval: 时间间隔字符串
        :return: 毫秒数
        """
        return self.interval_map.get(interval, 4 * 60 * 60 * 1000)  # 默认4小时