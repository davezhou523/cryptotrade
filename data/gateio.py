"""
Gate.io数据获取器实现
"""

import requests
import time
import pandas as pd
import os
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from .base import DataFetcher


class GateioDataFetcher(DataFetcher):
    """
    Gate.io数据获取器，实现从Gate.io获取K线数据的功能
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, proxy: str = None):
        """
        初始化Gate.io数据获取器
        :param api_key: Gate.io API密钥
        :param api_secret: Gate.io API密钥
        :param proxy: 代理服务器地址，格式为 "http://host:port"
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.proxy = proxy
        self.base_url = "https://api.gateio.ws/api/v4"
        self.limit = 1000  # Gate.io API最大限制
        self.interval_map = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '2h': '2h',
            '4h': '4h',
            '6h': '6h',
            '8h': '8h',
            '12h': '12h',
            '1d': '1d',
            '3d': '3d',
            '7d': '7d'
        }
        
        # 如果设置了代理，打印代理信息
        if self.proxy:
            print(f"使用代理: {self.proxy}")
    
    def _generate_signature(self, method, url, params=None, data=None):
        """
        生成Gate.io API签名
        :param method: HTTP方法
        :param url: API路径
        :param params: URL参数
        :param data: 请求体数据
        :return: 签名和时间戳
        """
        timestamp = str(int(time.time() * 1000))
        message = f"{method}{url}"
        
        if params:
            sorted_params = sorted(params.items())
            query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
            message += f"?{query_string}"
        
        if data:
            message += str(data)
        
        message += timestamp
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).digest()
        
        return base64.b64encode(signature).decode('utf-8'), timestamp
    
    def fetch_klines(self, symbol: str, interval: str, start_time: datetime, end_time: datetime, save_dir: str = None) -> str | None:
        """
        获取K线数据，支持获取超过1000条的数据（通过循环请求实现）
        :param symbol: 交易对 (如: ETH_USDT)
        :param interval: 时间间隔 (如: 1m, 1h, 4h, 1d)
        :param start_time: 开始时间
        :param end_time: 结束时间
        :param save_dir: 保存目录（可选）
        :return: 保存数据的CSV文件名
        """
        all_data = []
        current_start_time = int(start_time.timestamp())  # 秒级时间戳
        end_time_sec = int(end_time.timestamp())  # 秒级时间戳
        
        # 转换时间间隔
        gate_interval = self.interval_map.get(interval, '4h')
        
        # API路径
        api_path = "/spot/candlesticks"
        
        # 增加重试机制
        max_retries = 3
        retry_delay = 2
        
        # 计算每个请求的时间范围
        interval_ms = self._get_interval_ms(interval)
        interval_sec = interval_ms // 1000
        max_points_per_request = 1000
        max_seconds_per_request = interval_sec * max_points_per_request
        
        try:
            # 循环请求数据，直到获取所有数据
            while current_start_time < end_time_sec:
                # 计算本次请求的结束时间
                request_end_time = min(current_start_time + max_seconds_per_request, end_time_sec)
                
                params = {
                    'currency_pair': symbol,
                    'interval': gate_interval,
                    'limit': max_points_per_request,
                    'from': current_start_time,
                    'to': request_end_time
                }
                
                # 构建完整URL
                url = f"{self.base_url}{api_path}"
                
                # 发送请求，带重试机制
                for attempt in range(max_retries):
                    try:
                        # 发送请求，增加超时设置和代理
                        proxies = {}
                        if self.proxy:
                            proxies = {
                                'http': self.proxy,
                                'https': self.proxy
                            }
                        
                        response = requests.get(
                            url, 
                            params=params,
                            timeout=30,  # 30秒超时
                            proxies=proxies
                        )
                        response.raise_for_status()
                        data = response.json()
                        break  # 成功获取数据，退出重试循环
                    except requests.exceptions.RequestException as e:
                        print(f"请求错误 (尝试 {attempt+1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                        else:
                            raise
                
                if not data:
                    break  # 没有更多数据
                
                # 添加到所有数据
                all_data.extend(data)
                
                # 获取最后一条数据的时间戳，作为下一次请求的开始时间
                if data:
                    last_timestamp = data[-1][0]
                    current_start_time = last_timestamp + interval_sec
                else:
                    # 如果没有数据，增加一个时间间隔
                    current_start_time += max_seconds_per_request
                
                # 如果设置了结束时间，检查是否已经超过
                if current_start_time >= end_time_sec:
                    break
                
                # 添加延迟，避免超过API请求频率限制
                time.sleep(1)
            
            # 处理数据格式，使其适合Backtrader
            processed_data = []
            for item in all_data:
                timestamp = datetime.fromtimestamp(item[0], timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                processed_data.append([
                    timestamp,
                    float(item[2]),  # open
                    float(item[3]),  # high
                    float(item[4]),  # low
                    float(item[5]),  # close
                    float(item[6])  # volume
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
    
    def _get_interval_ms(self, interval: str) -> int:
        """
        获取不同时间间隔对应的毫秒数
        :param interval: 时间间隔字符串
        :return: 毫秒数
        """
        interval_map = {
            '1m': 60 * 1000,
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
            '7d': 7 * 24 * 60 * 60 * 1000
        }
        return interval_map.get(interval, 4 * 60 * 60 * 1000)  # 默认4小时
    
    def get_supported_intervals(self) -> list:
        """
        获取支持的时间间隔列表
        :return: 时间间隔列表
        """
        return list(self.interval_map.keys())
    
    def place_order(self, symbol: str, side: str, amount: float, price: float = None) -> dict:
        """
        下单交易
        :param symbol: 交易对 (如: ETH_USDT)
        :param side: 交易方向 ('buy' 或 'sell')
        :param amount: 交易数量
        :param price: 交易价格（限价单），如果为None则为市价单
        :return: 订单信息
        """
        if not self.api_key or not self.api_secret:
            raise ValueError("API密钥和密钥不能为空")
        
        api_path = "/spot/orders"
        url = f"{self.base_url}{api_path}"
        
        # 构建订单参数
        order_data = {
            'currency_pair': symbol,
            'type': 'limit' if price else 'market',
            'side': side,
            'amount': str(amount)
        }
        
        if price:
            order_data['price'] = str(price)
        
        # 生成签名
        signature, timestamp = self._generate_signature('POST', api_path, data=order_data)
        
        # 请求头
        headers = {
            'KEY': self.api_key,
            'SIGN': signature,
            'Timestamp': timestamp,
            'Content-Type': 'application/json'
        }
        
        try:
            # 发送请求，带重试机制
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # 发送请求，增加超时设置和代理
                    proxies = {}
                    if self.proxy:
                        proxies = {
                            'http': self.proxy,
                            'https': self.proxy
                        }
                    
                    response = requests.post(
                        url,
                        json=order_data,
                        headers=headers,
                        timeout=30,
                        proxies=proxies
                    )
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.RequestException as e:
                    print(f"请求错误 (尝试 {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        raise
        except Exception as e:
            print(f"下单失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_balance(self, currency: str = None) -> dict:
        """
        获取账户余额
        :param currency: 货币符号，如 'USDT', 'ETH' 等，如果为None则获取所有货币余额
        :return: 余额信息
        """
        if not self.api_key or not self.api_secret:
            raise ValueError("API密钥和密钥不能为空")
        
        api_path = "/spot/accounts"
        url = f"{self.base_url}{api_path}"
        
        # 生成签名
        signature, timestamp = self._generate_signature('GET', api_path)
        
        # 请求头
        headers = {
            'KEY': self.api_key,
            'SIGN': signature,
            'Timestamp': timestamp
        }
        
        try:
            # 发送请求，带重试机制
            max_retries = 3
            retry_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # 发送请求，增加超时设置和代理
                    proxies = {}
                    if self.proxy:
                        proxies = {
                            'http': self.proxy,
                            'https': self.proxy
                        }
                    
                    response = requests.get(
                        url,
                        headers=headers,
                        timeout=30,
                        proxies=proxies
                    )
                    response.raise_for_status()
                    balances = response.json()
                    
                    if currency:
                        for balance in balances:
                            if balance['currency'] == currency:
                                return balance
                        return None
                    else:
                        return balances
                except requests.exceptions.RequestException as e:
                    print(f"请求错误 (尝试 {attempt+1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 2  # 指数退避
                    else:
                        raise
        except Exception as e:
            print(f"获取余额失败: {e}")
            import traceback
            traceback.print_exc()
            return None