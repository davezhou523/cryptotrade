import backtrader as bt
import pandas as pd
import numpy as np
from trend.tradingStrategy import TradingStrategy
from trend.ml_signal_filter import MLSignalFilter
from data.base import get_1h_data, get_daily_data

class ModelTrainingStrategy(TradingStrategy):
    """
    用于训练机器学习模型的策略类
    继承自TradingStrategy，用于收集训练数据
    """
    def __init__(self):
        super().__init__()
        self.training_data = []  # 存储训练数据
        self.labels = []  # 存储标签
        self.trade_signals = []  # 存储交易信号
        
    def notify_trade(self, trade):
        """
        重写notify_trade方法，收集交易结果作为标签
        """
        super().notify_trade(trade)
        
        if trade.isclosed:
            # 计算交易结果
            if trade.pnl > 0:
                label = 1  # 好信号
            else:
                label = 0  # 坏信号
            
            # 将标签与对应的信号特征关联
            if self.trade_signals:
                # 取最后一个信号作为当前交易的信号
                features = self.trade_signals[-1]
                self.training_data.append(features)
                self.labels.append(label)
    
    def validate_buy_signal(self, trend_type, stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev):
        """
        重写买入信号验证方法，收集特征数据
        """
        is_valid, validation_results = super().validate_buy_signal(
            trend_type, stoch_rsi_k, stoch_rsi_d, stoch_rsi_k_prev, stoch_rsi_d_prev
        )
        
        # 如果信号有效，收集特征数据
        if is_valid:
            # 提取特征
            ml_filter = MLSignalFilter()
            features = ml_filter.extract_features(self)
            self.trade_signals.append(features.flatten())
        
        return is_valid, validation_results

def train_model():
    """
    训练机器学习模型
    """
    # 创建Cerebro引擎
    cerebro = bt.Cerebro()
    
    # 设置初始资金
    cerebro.broker.setcash(3000)
    cerebro.broker.set_shortcash(True)
    
    # 设置交易手续费和滑点
    cerebro.broker.setcommission(commission=0.001, margin=1.0)
    cerebro.broker.set_slippage_perc(0.001)
    cerebro.broker.set_slippage_fixed(0.01)
    cerebro.broker.set_coc(True)
    
    # 加载数据
    data_1h = get_1h_data("ETH")
    cerebro.adddata(data_1h)
    data_daily = get_daily_data("ETH")
    cerebro.adddata(data_daily)
    
    # 添加训练策略
    cerebro.addstrategy(ModelTrainingStrategy)
    
    # 运行策略收集训练数据
    print("正在运行策略收集训练数据...")
    results = cerebro.run()
    
    # 获取训练数据
    strategy = results[0]
    training_data = np.array(strategy.training_data)
    labels = np.array(strategy.labels)
    
    print(f"收集到 {len(training_data)} 个训练样本")
    print(f"好信号: {np.sum(labels)}")
    print(f"坏信号: {len(labels) - np.sum(labels)}")
    
    # 训练模型
    if len(training_data) > 0:
        print("正在训练机器学习模型...")
        ml_filter = MLSignalFilter("ml_signal_filter_model.pkl")
        ml_filter.train(training_data, labels)
        
        print("模型训练完成！")
    else:
        print("没有收集到足够的训练数据")

if __name__ == "__main__":
    train_model()