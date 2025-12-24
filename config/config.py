# 创建config.py文件保存所有参数
STRATEGY_PARAMS = {
    # 趋势检测参数
    'boll_period': 20,
    'boll_dev': 2,
    'dmi_period': 7,
    'adx_threshold': 15,
    
    # Stoch RSI参数
    'rsi_period': 14,
    'stoch_period': 14,
    'stoch_d_period': 4,
    'oversold': 25,
    'overbought': 75,
    
    # ATR参数
    'atr_period': 14,
    
    # 优化建议
    'stop_loss_multiplier': 2.0,
    'take_profit_multiplier': 3.0,
    'trailing_stop_multiplier': 2.0,
    
    # 移动平均线参数
    'ma_period': 60,
    
    # 风险控制参数
    'max_loss_per_trade': 0.01,
    'min_hold_periods': 3,
    'max_trades_per_day': 1,
    
    # 其他参数
    'printlog': True,
}