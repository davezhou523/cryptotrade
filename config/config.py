# 创建config.py文件保存所有参数
STRATEGY_PARAMS = {
    # 趋势类型定义
    # 震荡趋势
    'sideways_trend': 0,
    # 单边上涨趋势
    'bullish_trend': 1,
    # 单边下跌趋势
    'bearish_trend': -1,

    # 趋势检测参数
    'boll_period': 20,
    'boll_dev': 2,
    'dmi_period': 14,
    'adx_threshold': 20,
    
    # BOLL通道优化参数
    'boll_channel_width_threshold': 2,  # 通道宽度阈值（百分比），小于此值视为窄幅震荡
    'boll_top_percentage': 0.7,  # 上涨趋势的BOLL上轨百分比要求（0.7表示价格需要在上轨70%范围内）
    'boll_bottom_percentage': 0.3,  # 下跌趋势的BOLL下轨百分比要求（0.3表示价格需要在下轨30%范围内）
    
    # 新增：趋势确认参数
    'boll_mid_rising_periods': 3,  # BOLL中轨连续上升的期数要求
    'volume_ratio_threshold': 1.2,  # 成交量放大比例阈值，大于此值视为有效放量
    'atr_volatility_multiplier': 1.5,  # ATR波动率乘数，用于判断趋势强度
    
    # Stoch RSI参数
    'rsi_period': 14,
    'stoch_period': 14,
    'stoch_d_period': 4,
    'oversold': 25,
    'overbought': 75,
    'smooth_period': 5,
    'rsi_smooth_period': 7,

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