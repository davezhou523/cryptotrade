import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from sklearn.preprocessing import StandardScaler
import pickle
import os

class MLSignalFilter:
    """
    机器学习交易信号过滤类
    使用历史数据训练模型，过滤低质量的交易信号
    """
    
    def __init__(self, model_path=None):
        """
        初始化MLSignalFilter
        :param model_path: 预训练模型路径，若为None则创建新模型
        """
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.scaler = StandardScaler()
        self.model_path = model_path
        self.is_trained = False
        
        # 如果提供了模型路径且模型存在，则加载预训练模型
        if model_path and os.path.exists(model_path):
            self.load_model()
    
    def extract_features(self, strategy_instance):
        """
        从策略实例中提取特征用于模型预测
        :param strategy_instance: TradingStrategy实例
        :return: 特征向量
        """
        features = []
        
        # 技术指标特征
        features.append(strategy_instance.stoch_rsi.percK[0])  # Stoch RSI K值
        features.append(strategy_instance.stoch_rsi.percD[0])  # Stoch RSI D值
        features.append(strategy_instance.rsi[0])  # RSI值
        features.append(strategy_instance.macd.macd[0])  # MACD
        features.append(strategy_instance.macd.signal[0])  # MACD Signal
        features.append(strategy_instance.atr[0])  # ATR
        
        # 价格与均线关系
        features.append(strategy_instance.data_close[0] - strategy_instance.fast_ma[0])  # 价格与快MA的距离
        features.append(strategy_instance.fast_ma[0] - strategy_instance.slow_ma[0])  # 快MA与慢MA的距离
        
        # BOLL通道特征
        boll_mid = strategy_instance.boll.mid[0]
        boll_top = strategy_instance.boll.top[0]
        boll_bot = strategy_instance.boll.bot[0]
        features.append(strategy_instance.data_close[0] - boll_mid)  # 价格与BOLL中轨的距离
        features.append((boll_top - boll_bot) / boll_mid)  # BOLL通道宽度
        
        # 趋势特征
        features.append(strategy_instance.trend_detector_daily.trend_type[0])  # 日线趋势类型
        features.append(strategy_instance.trend_detector_daily.lines.adx[0])  # ADX值
        
        # 成交量特征
        features.append(strategy_instance.data_volume[0] / strategy_instance.volume_ma_5[0] if len(strategy_instance.volume_ma_5) > 0 else 1.0)  # 成交量与5日MA的比率
        features.append(strategy_instance.data_volume[0] / strategy_instance.volume_ma_20[0] if len(strategy_instance.volume_ma_20) > 0 else 1.0)  # 成交量与20日MA的比率
        
        # 信号强度特征
        features.append(strategy_instance.signal_strength)  # 信号强度
        
        return np.array(features).reshape(1, -1)
    
    def train(self, X, y):
        """
        训练模型
        :param X: 特征矩阵
        :param y: 标签向量
        """
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 特征标准化
        self.scaler.fit(X_train)
        X_train_scaled = self.scaler.transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 训练模型
        self.model.fit(X_train_scaled, y_train)
        
        # 评估模型
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"模型训练完成，准确率: {accuracy:.4f}")
        
        self.is_trained = True
        
        # 如果提供了模型路径，则保存模型
        if self.model_path:
            self.save_model()
    
    def predict(self, features):
        """
        预测信号质量
        :param features: 特征向量
        :return: 预测结果（1表示好信号，0表示坏信号）和预测概率
        """
        if not self.is_trained:
            raise ValueError("模型尚未训练，请先调用train方法训练模型")
        
        # 特征标准化
        features_scaled = self.scaler.transform(features)
        
        # 预测
        prediction = self.model.predict(features_scaled)[0]
        probability = self.model.predict_proba(features_scaled)[0][1]  # 好信号的概率
        
        return prediction, probability
    
    def save_model(self):
        """
        保存模型到文件
        """
        import joblib
        joblib.dump({
            'model': self.model,
            'scaler': self.scaler,
            'is_trained': self.is_trained
        }, self.model_path)
        print(f"模型已保存到: {self.model_path}")
    
    def load_model(self):
        """
        从文件加载模型
        """
        import joblib
        loaded_data = joblib.load(self.model_path)
        self.model = loaded_data['model']
        self.scaler = loaded_data['scaler']
        self.is_trained = loaded_data['is_trained']
        print(f"模型已从 {self.model_path} 加载")
    
    def filter_signal(self, strategy_instance, signal_type):
        """
        过滤交易信号
        :param strategy_instance: TradingStrategy实例
        :param signal_type: 信号类型 ('buy' 或 'sell')
        :return: 是否保留信号和信号质量概率
        """
        # 提取特征
        features = self.extract_features(strategy_instance)
        
        # 预测信号质量
        try:
            prediction, probability = self.predict(features)
            
            # 根据预测结果和概率阈值决定是否保留信号
            if signal_type == 'buy':
                return prediction == 1 and probability > 0.6, probability
            elif signal_type == 'sell':
                return prediction == 1 and probability > 0.55, probability
            else:
                return True, 1.0  # 未知信号类型，默认保留
        except Exception as e:
            print(f"信号过滤出错: {e}")
            return True, 1.0  # 出错时默认保留信号