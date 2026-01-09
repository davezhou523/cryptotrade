#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import pandas as pd
from datetime import datetime
from data.binance import BinanceDataFetcher

def test_local_indicators():
    """
    测试从本地CSV文件计算技术指标
    """
    print("开始测试本地CSV文件的技术指标计算...")
    
    # 创建数据获取器实例
    fetcher = BinanceDataFetcher()
    
    # 本地CSV文件路径
    csv_file = "data/ETH/ethusdt_1h_20250101_20251222.csv"
    
    if not os.path.exists(csv_file):
        print(f"错误：文件不存在 - {csv_file}")
        return
    
    print(f"\n使用的CSV文件: {csv_file}")
    
    # 测试1: 计算单个EMA指标
    print("\n1. 测试从CSV计算EMA指标:")
    df_ema = fetcher.get_ema_from_binance(csv_file=csv_file, period=20)
    if df_ema is not None:
        print(f"✓ EMA计算成功，数据行数: {len(df_ema)}")
        print("最后5行数据:")
        print(df_ema[['datetime', 'close', 'EMA']].tail())
    
    # 测试2: 计算DMI指标
    print("\n2. 测试从CSV计算DMI指标:")
    df_dmi = fetcher.get_dmi_from_binance(csv_file=csv_file, period=14)
    if df_dmi is not None:
        print(f"✓ DMI计算成功，数据行数: {len(df_dmi)}")
        print("最后5行数据:")
        print(df_dmi[['datetime', '+DI', '-DI', 'ADX']].tail())
    
    # 测试3: 计算BOLL指标
    print("\n3. 测试从CSV计算BOLL指标:")
    df_boll = fetcher.get_boll_from_binance(csv_file=csv_file, period=20, devfactor=2.0)
    if df_boll is not None:
        print(f"✓ BOLL计算成功，数据行数: {len(df_boll)}")
        print("最后5行数据:")
        print(df_boll[['datetime', 'close', 'BOLL_TOP', 'BOLL_MID', 'BOLL_BOT']].tail())
    
    # 测试4: 计算ATR指标
    print("\n4. 测试从CSV计算ATR指标:")
    df_atr = fetcher.get_atr_from_binance(csv_file=csv_file, period=14)
    if df_atr is not None:
        print(f"✓ ATR计算成功，数据行数: {len(df_atr)}")
        print("最后5行数据:")
        print(df_atr[['datetime', 'high', 'low', 'close', 'ATR']].tail())
    
    # 测试5: 计算所有指标
    print("\n5. 测试从CSV计算所有指标:")
    params = {
        'ema_period': 12,
        'dmi_period': 14,
        'boll_period': 20,
        'boll_dev': 2.0,
        'rsi_period': 14,
        'stoch_period': 14,
        'atr_period': 14
    }
    
    # 使用两种方法测试
    df_all1 = fetcher.get_technical_indicators_from_binance(csv_file=csv_file, params=params)
    df_all2 = fetcher.calculate_indicators_from_csv(csv_file=csv_file, params=params)
    
    if df_all1 is not None and df_all2 is not None:
        print(f"✓ 所有指标计算成功，数据行数: {len(df_all1)}")
        print(f"✓ calculate_indicators_from_csv 方法同样成功")
        print(f"所有列: {list(df_all1.columns)}")
        
        # 保存结果到新的CSV文件
        output_file = "eth_indicators_result.csv"
        df_all1.to_csv(output_file, index=False)
        print(f"\n计算结果已保存到: {output_file}")
        
        # 显示部分结果
        print("\n最后5行数据（部分指标）:")
        print(df_all1[['datetime', 'close', 'EMA', 'ATR', 'BOLL_MID', 'RSI', 'PERC_K']].tail())

if __name__ == "__main__":
    test_local_indicators()