"""
Binance数据获取器实现
"""

import requests
import time
import pandas as pd
import os
import numpy as np
from datetime import datetime, timezone
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
        
        # 增加重试机制
        max_retries = 1
        retry_delay = 1
        
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
                
                # 发送请求，带重试机制
                for attempt in range(max_retries):
                    try:
                        # 发送请求，增加超时设置
                        response = requests.get(
                            self.base_url, 
                            params=params, 
                            headers=headers,
                            timeout=10,  # 10秒超时
                            verify=True  # 验证SSL证书
                        )
                        response.raise_for_status()
                        data = response.json()
                        break  # 成功获取数据，退出重试循环
                    except requests.exceptions.SSLError as e:
                        print(f"SSL错误 (尝试 {attempt+1}/{max_retries}): {e}")
                        if attempt < max_retries - 1:
                            time.sleep(retry_delay)
                            retry_delay *= 2  # 指数退避
                        else:
                            raise
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
                timestamp = datetime.fromtimestamp(item[0] / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
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

    def get_ema_from_binance(self, symbol: str = None, interval: str = None, period: int = 12, 
                           start_time: datetime = None, end_time: datetime = None, csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算EMA值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param period: EMA周期
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和EMA值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        
        # 计算EMA值（与Binance算法一致）
        # 平滑因子 = 2 / (周期 + 1)
        smoothing = 2 / (period + 1)
        
        # 使用SMA作为初始值
        df['EMA'] = df['close'].ewm(span=period, adjust=False).mean()
        
        return df
    
    def get_dmi_from_binance(self, symbol: str = None, interval: str = None, period: int = 14, 
                           start_time: datetime = None, end_time: datetime = None, csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算DMI值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param period: DMI周期
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和DMI值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        


        # 在binance.py文件中修改get_dmi_from_binance方法：

        # 在binance.py文件中修改get_dmi_from_binance方法：

        # 1. 修复前一天价格数据的计算（原错误行200-202）
        df['prev_high'] = df['high'].shift(1)  # 正确：对high列进行shift
        df['prev_low'] = df['low'].shift(1)  # 修复：将prev_low改为low
        df['prev_close'] = df['close'].shift(1)  # 正确：对close列进行shift

        # 2. 修复TR计算（之前已修复）
        df['TR1'] = df['high'] - df['low']
        df['TR2'] = abs(df['high'] - df['prev_close'])
        df['TR3'] = abs(df['low'] - df['prev_close'])
        df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

        # 3. 修复+DM计算（原错误行206）
        df['high_diff'] = df['high'] - df['prev_high']
        df['low_diff'] = df['prev_low'] - df['low']

        # 计算SMMA（平滑移动平均）
        def calculate_smma(series, period):
            smma = series.rolling(window=period).mean().iloc[period-1]
            result = [0] * len(series)
            result[period-1] = smma
            for i in range(period, len(series)):
                smma = (smma * (period - 1) + series.iloc[i]) / period
                result[i] = smma
            return result
        
        df['SMMA_TR'] = calculate_smma(df['TR'], period)
        df['SMMA_PLUS_DM'] = calculate_smma(df['+DM'], period)
        df['SMMA_MINUS_DM'] = calculate_smma(df['-DM'], period)
        
        # 计算+DI和-DI
        df['+DI'] = 100 * (df['SMMA_PLUS_DM'] / df['SMMA_TR'])
        df['-DI'] = 100 * (df['SMMA_MINUS_DM'] / df['SMMA_TR'])
        
        # 计算DX
        df['DX'] = 100 * (abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']))
        
        # 计算ADX
        df['ADX'] = calculate_smma(df['DX'], period)
        
        return df
    
    def get_boll_from_binance(self, symbol: str = None, interval: str = None, period: int = 20, 
                             devfactor: float = 2.0, start_time: datetime = None, end_time: datetime = None, 
                             csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算BOLL值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param period: BOLL周期
        :param devfactor: 标准差乘数
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和BOLL值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        
        # 计算BOLL值（与Binance算法一致）
        df['BOLL_MID'] = df['close'].rolling(window=period).mean()  # 中轨：SMA
        df['BOLL_STD'] = df['close'].rolling(window=period).std()  # 标准差
        df['BOLL_TOP'] = df['BOLL_MID'] + devfactor * df['BOLL_STD']  # 上轨
        df['BOLL_BOT'] = df['BOLL_MID'] - devfactor * df['BOLL_STD']  # 下轨
        
        return df
    
    def get_stoch_rsi_from_binance(self, symbol: str = None, interval: str = None, rsi_period: int = 14, 
                                  stoch_period: int = 14, start_time: datetime = None, end_time: datetime = None, 
                                  csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算Stoch RSI值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param rsi_period: RSI周期
        :param stoch_period: Stoch RSI周期
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和Stoch RSI值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        
        # 计算RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=rsi_period).mean()
        avg_loss = loss.rolling(window=rsi_period).mean()
        
        rs = avg_gain / avg_loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 计算Stoch RSI
        df['RSI_LOW'] = df['RSI'].rolling(window=stoch_period).min()
        df['RSI_HIGH'] = df['RSI'].rolling(window=stoch_period).max()
        
        # 避免除零错误
        df['STOCH_RSI'] = 100 * ((df['RSI'] - df['RSI_LOW']) / (df['RSI_HIGH'] - df['RSI_LOW']))
        df['STOCH_RSI'] = df['STOCH_RSI'].fillna(50)  # 当最高价等于最低价时，设置为中间值50
        
        # 计算%K和%D
        df['PERC_K'] = df['STOCH_RSI'].rolling(window=3).mean()
        df['PERC_D'] = df['PERC_K'].rolling(window=3).mean()
        
        # 将结果限制在0-100范围内
        df['PERC_K'] = df['PERC_K'].clip(0, 100)
        df['PERC_D'] = df['PERC_D'].clip(0, 100)
        
        return df
    
    def get_atr_from_binance(self, symbol: str = None, interval: str = None, period: int = 14, 
                            start_time: datetime = None, end_time: datetime = None, csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算ATR值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param period: ATR周期
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和ATR值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        
        # 计算ATR值（与Binance算法一致）
        # 计算真实波幅
        df['TR1'] = df['high'] - df['low']
        df['TR2'] = abs(df['high'] - df['close'].shift(1))
        df['TR3'] = abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
        
        # 计算ATR（使用SMA）
        df['ATR'] = df['TR'].rolling(window=period).mean()
        
        return df
    
    def get_technical_indicators_from_binance(self, symbol: str = None, interval: str = None, params: dict = None, 
                                             start_time: datetime = None, end_time: datetime = None, 
                                             csv_file: str = None) -> pd.DataFrame:
        """
        使用Binance API获取K线数据并计算所有技术指标值，或直接从CSV文件计算
        :param symbol: 交易对（当使用API时需要）
        :param interval: 时间间隔（当使用API时需要）
        :param params: 各指标参数，格式: {'ema_period': 12, 'dmi_period': 14, 'boll_period': 20, 'boll_dev': 2, 'rsi_period': 14, 'stoch_period': 14, 'atr_period': 14}
        :param start_time: 开始时间（当使用API时需要）
        :param end_time: 结束时间（当使用API时需要）
        :param csv_file: 本地CSV文件路径（可选，直接从文件读取数据）
        :return: 包含K线数据和所有技术指标值的DataFrame
        """
        # 获取或读取K线数据
        if csv_file:
            if not os.path.exists(csv_file):
                print(f"文件不存在: {csv_file}")
                return None
            df = pd.read_csv(csv_file)
        else:
            klines_file = self.fetch_klines(symbol, interval, start_time, end_time)
            if not klines_file:
                return None
            df = pd.read_csv(klines_file)
        
        # 使用默认参数如果没有提供
        if params is None:
            params = {
                'ema_period': 12,
                'dmi_period': 14,
                'boll_period': 20,
                'boll_dev': 2.0,
                'rsi_period': 14,
                'stoch_period': 14,
                'atr_period': 14
            }
        
        # 计算所有技术指标
        if 'ema_period' in params:
            # 计算EMA
            df['EMA'] = df['close'].ewm(span=params['ema_period'], adjust=False).mean()
        
        if 'dmi_period' in params:
            # 计算DMI
            dmi_period = params['dmi_period']
            # 1. 计算前一天的收盘价（在方法开头添加）
            df['prev_close'] = df['close'].shift(1)
            df['prev_high'] = df['high'].shift(1)
            df['prev_low'] = df['low'].shift(1)
            df['high_diff'] = df['high'] - df['prev_high']
            df['low_diff'] = df['prev_low'] - df['low']
            # 2. 计算TR的三个组成部分（使用向量运算，替代原来的apply+lambda）
            df['TR1'] = df['high'] - df['low']
            df['TR2'] = abs(df['high'] - df['prev_close'])
            df['TR3'] = abs(df['low'] - df['prev_close'])

            # 3. 取最大值得到TR
            df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

            # 3. 计算+DM：如果high_diff > low_diff 且 high_diff > 0，则为high_diff，否则为0
            df['+DM'] = df.apply(
                lambda x: x['high_diff'] if (x['high_diff'] > x['low_diff'] and x['high_diff'] > 0) else 0, axis=1)

            # 4. 计算-DM：如果low_diff > high_diff 且 low_diff > 0，则为low_diff，否则为0
            df['-DM'] = df.apply(
                lambda x: x['low_diff'] if (x['low_diff'] > x['high_diff'] and x['low_diff'] > 0) else 0, axis=1)

            def calculate_smma(series, period):
                smma = series.rolling(window=period).mean().iloc[period-1]
                result = [0] * len(series)
                result[period-1] = smma
                for i in range(period, len(series)):
                    smma = (smma * (period - 1) + series.iloc[i]) / period
                    result[i] = smma
                return result
            
            df['SMMA_TR'] = calculate_smma(df['TR'], dmi_period)
            df['SMMA_PLUS_DM'] = calculate_smma(df['+DM'], dmi_period)
            df['SMMA_MINUS_DM'] = calculate_smma(df['-DM'], dmi_period)
            
            df['+DI'] = 100 * (df['SMMA_PLUS_DM'] / df['SMMA_TR'])
            df['-DI'] = 100 * (df['SMMA_MINUS_DM'] / df['SMMA_TR'])
            
            df['DX'] = 100 * (abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']))
            df['ADX'] = calculate_smma(df['DX'], dmi_period)
        
        if 'boll_period' in params and 'boll_dev' in params:
            # 计算BOLL
            boll_period = params['boll_period']
            boll_dev = params['boll_dev']
            df['BOLL_MID'] = df['close'].rolling(window=boll_period).mean()
            df['BOLL_STD'] = df['close'].rolling(window=boll_period).std()
            df['BOLL_TOP'] = df['BOLL_MID'] + boll_dev * df['BOLL_STD']
            df['BOLL_BOT'] = df['BOLL_MID'] - boll_dev * df['BOLL_STD']
        
        if 'rsi_period' in params and 'stoch_period' in params:
            # 计算Stoch RSI
            rsi_period = params['rsi_period']
            stoch_period = params['stoch_period']
            
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=rsi_period).mean()
            avg_loss = loss.rolling(window=rsi_period).mean()
            
            rs = avg_gain / avg_loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            df['RSI_LOW'] = df['RSI'].rolling(window=stoch_period).min()
            df['RSI_HIGH'] = df['RSI'].rolling(window=stoch_period).max()
            
            df['STOCH_RSI'] = 100 * ((df['RSI'] - df['RSI_LOW']) / (df['RSI_HIGH'] - df['RSI_LOW']))
            df['STOCH_RSI'] = df['STOCH_RSI'].fillna(50)
            
            df['PERC_K'] = df['STOCH_RSI'].rolling(window=3).mean()
            df['PERC_D'] = df['PERC_K'].rolling(window=3).mean()
            
            df['PERC_K'] = df['PERC_K'].clip(0, 100)
            df['PERC_D'] = df['PERC_D'].clip(0, 100)
        
        if 'atr_period' in params:
            # 计算ATR
            atr_period = params['atr_period']
            df['TR1'] = df['high'] - df['low']
            df['TR2'] = abs(df['high'] - df['close'].shift(1))
            df['TR3'] = abs(df['low'] - df['close'].shift(1))
            df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
            df['ATR'] = df['TR'].rolling(window=atr_period).mean()
        
        return df
    
    def calculate_indicators_from_csv(self, csv_file: str, params: dict = None) -> pd.DataFrame:
        """
        直接从本地CSV文件计算所有技术指标
        :param csv_file: 本地CSV文件路径
        :param params: 各指标参数，格式: {'ema_period': 12, 'dmi_period': 14, 'boll_period': 20, 'boll_dev': 2, 'rsi_period': 14, 'stoch_period': 14, 'atr_period': 14}
        :return: 包含K线数据和所有技术指标值的DataFrame
        """
        return self.get_technical_indicators_from_binance(csv_file=csv_file, params=params)
    
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