import backtrader as bt
from config import STRATEGY_PARAMS
class TestStrategy(bt.Strategy):
    params=(('printlog', True),)
    def __init__(self):
        super().__init__()
        self.dataclose = self.datas[1].close
        for i,data in enumerate(self.datas):
            print(f"\n数据源 {i}:")
            print(f"  类型: {type(data).__name__}")
            print(f"  数据点数量: {len(data)}")
            print(f"  可用字段: ['datetime', 'open', 'high', 'low', 'close', 'volume']")
            print(f"  最近数据点:")
            # print(f"    datetime: {data.datetime.datetime()}")
            # print(f"    open: {data.open[0]:.2f}")
            # print(f"    high: {data.high[0]:.2f}")
            # print(f"    low: {data.low[0]:.2f}")
            # print(f"    close: {data.close[0]:.2f}")
            # print(f"    volume: {data.volume[0]:.2f}")
        print(len(self.datas[1].open))

        print(self.datas[1].datetime.date(0), self.datas[1].open[0], self.datas[1].high[0], self.datas[1].low[0], self.datas[1].close[0], self.datas[1].volume[0])
        print(self.datas[1].datetime.date(1), self.datas[1].open[0], self.datas[1].high[1], self.datas[1].low[1], self.datas[1].close[1], self.datas[1].volume[1])
        print(self.datas[1].datetime.date(-1), self.datas[1].open[-1], self.datas[1].high[-1], self.datas[1].low[-1], self.datas[1].close[-1], self.datas[1].volume[-1])
        print(self.datas[1].datetime.date(-2), self.datas[1].open[-2], self.datas[1].high[-2], self.datas[1].low[-2], self.datas[1].close[-2], self.datas[1].volume[-2])
        print(self.datas[1].datetime.date(-3), self.datas[1].open[-3], self.datas[1].high[-3], self.datas[1].low[-3], self.datas[1].close[-3], self.datas[1].volume[-3])

    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print('%s, %s' % (dt.isoformat(), txt))




    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log('Close, %.2f' % self.dataclose[0])
        pass