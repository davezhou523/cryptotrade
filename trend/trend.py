import backtrader as bt
import sys
from datetime import datetime

# Binance API configuration
API_KEY = "34Y19F0ilIFbUlb0z3JbBZG99B7Qx42CKVMs35G69P6qMhngGgtzu1VadUmue4Z6"
API_SECRET = "0dGiAwz9qRCmarEFA4HehoYwdJOA5O4rdSOop9vD2hmV8zrrFPuSu31VdjbHFzZp"


class DMI(bt.Indicator):
    """
    Custom DMI Indicator Class
    Directional Movement Index (DMI) is used to determine trend strength and direction
    """
    lines = ('plus_di', 'minus_di', 'adx')
    params = (('period', 14),)

    def __init__(self):
        # Use Backtrader's built-in DMI indicator
        self.dmi = bt.indicators.DirectionalMovement(self.data, period=self.params.period)
        self.lines.plus_di = self.dmi.plusDI
        self.lines.minus_di = self.dmi.minusDI
        self.lines.adx = self.dmi.adx


class TrendDetector(bt.Indicator):
    """
    Trend Detection Class, uses DMI+BOLL technical indicators to determine three trend types
    - Sideways Trend
    - Bullish Trend
    - Bearish Trend
    """
    lines = ('trend_type',)
    params = (
        # BOLL parameters
        ('boll_period', 20),
        ('boll_dev', 2),

        # DMI parameters
        ('dmi_period', 14),
        ('adx_threshold', 25),  # ADX threshold for trend strength

        # Trend type definitions
        ('sideways_trend', 0),
        ('bullish_trend', 1),
        ('bearish_trend', -1),
    )

    def __init__(self):
        # Initialize indicators
        self.dmi = DMI(self.data, period=self.params.dmi_period)
        self.boll = bt.indicators.BBands(
            self.data,
            period=self.params.boll_period,
            devfactor=self.params.boll_dev
        )

    def next(self):
        """
        Calculate current trend type
        - Sideways Trend: ADX < adx_threshold
        - Bullish Trend: +DI > -DI and ADX >= adx_threshold
        - Bearish Trend: -DI > +DI and ADX >= adx_threshold
        """
        adx_value = self.dmi.adx[0]
        plus_di_value = self.dmi.plus_di[0]
        minus_di_value = self.dmi.minus_di[0]

        # Determine trend type
        if adx_value < self.params.adx_threshold:
            # Sideways trend
            self.lines.trend_type[0] = self.params.sideways_trend
        elif plus_di_value > minus_di_value and adx_value >= self.params.adx_threshold:
            # Bullish trend
            self.lines.trend_type[0] = self.params.bullish_trend
        elif minus_di_value > plus_di_value and adx_value >= self.params.adx_threshold:
            # Bearish trend
            self.lines.trend_type[0] = self.params.bearish_trend
        else:
            # Default: Sideways trend
            self.lines.trend_type[0] = self.params.sideways_trend


class TrendStrategy(bt.Strategy):
    """
    Example strategy using TrendDetector
    """
    params = (
        ('boll_period', 20),
        ('boll_dev', 2),
        ('dmi_period', 14),
        ('adx_threshold', 25),
        ('printlog', True),
    )

    def log(self, txt, dt=None, doprint=False):
        """Logging function"""
        if self.params.printlog or doprint:
            dt = dt or self.datas[0].datetime.datetime(0)
            print(f'{dt.strftime("%Y-%m-%d %H:%M:%S")} {txt}')

    def __init__(self):
        # Initialize data reference
        self.data_close = self.datas[0].close

        # Initialize trend detector
        self.trend_detector = TrendDetector(
            self.datas[0],
            boll_period=self.params.boll_period,
            boll_dev=self.params.boll_dev,
            dmi_period=self.params.dmi_period,
            adx_threshold=self.params.adx_threshold
        )

        # Track order status
        self.order = None
        self.trend_names = {
            0: 'Sideways Trend', # 横盘
            1: 'Bullish Trend', # 涨
            -1: 'Bearish Trend' #跌
        }

    def notify_order(self, order):
        """Order status notification"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'Buy Executed | Price: {order.executed.price:.2f}')
            else:
                self.log(f'Sell Executed | Price: {order.executed.price:.2f}')

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Insufficient Margin/Rejected')

        self.order = None

    def next(self):
        """Main strategy logic"""
        if self.order:
            return

        # Get current trend type
        trend_type = int(self.trend_detector.trend_type[0])
        trend_name = self.trend_names[trend_type]

        # Print trend detection result
        self.log(f'Trend Detection: {trend_name}', doprint=True)

        # Example trading logic (can be modified as needed)
        if not self.position:
            # No position, decide whether to buy based on trend type
            if trend_type == 1:  # Bullish trend
                self.log(f'Bullish Trend, Executing Buy | Current Price: {self.data_close[0]:.2f}')
                # Calculate appropriate buy size to avoid insufficient funds
                size = int(self.broker.getvalue() / self.data_close[0] * 0.9)  # Use 90% of capital to buy
                self.order = self.buy(size=size if size > 0 else 1)
        else:
            # Holding position, decide whether to sell based on trend type
            if trend_type == -1:  # Bearish trend
                self.log(f'Bearish Trend, Executing Sell | Current Price: {self.data_close[0]:.2f}')
                self.order = self.sell(size=self.position.size)
            elif trend_type == 0:  # Sideways trend, consider taking profit
                if self.position.price * 1.03 <= self.data_close[0]:  # More than 3% profit
                    self.log(f'Sideways Trend, Profit Over 3%, Executing Take Profit | Current Price: {self.data_close[0]:.2f}')
                    self.order = self.sell(size=self.position.size)


# Example: How to use this trend detection class
def main():
    """
    Example main function showing how to use the TrendDetector class
    """
    # Set time range (January 1, 2025 to December 22, 2025)
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 12, 22)

    # Choose data source to test
    # Can be selected via command line parameters: python trend.py ETH or python trend.py BTC
    # Or directly modify the variable below
    if len(sys.argv) > 1:
        asset = sys.argv[1].upper()
    else:
        asset = "ETH"  # Default to testing ETH data
    
    if asset not in ["ETH", "BTC"]:
        print("Please select a valid data source: ETH or BTC")
        return
    
    # Set data file path
    if asset == "ETH":
        csv_file = "../data/ETH/ethusdt_1d_20250101_20251222.csv"
    else:
        csv_file = "../data/BTC/btcusdt_1d_20250101_20251222.csv"
    
    print(f"Testing {asset} daily data...")
    
    # Create Cerebro engine
    cerebro = bt.Cerebro()

    # Set initial capital
    initial_cash = 1000  # Can modify initial capital here
    cerebro.broker.setcash(initial_cash)

    # Set trading fees and leverage (leverage is 1, i.e., 100% margin)
    cerebro.broker.setcommission(commission=0.001, margin=1.0)

    # Load data - daily data configuration
    data = bt.feeds.GenericCSVData(
        dataname=csv_file,
        datetime=0,
        open=1,
        high=2,
        low=3,
        close=4,
        volume=5,
        openinterest=-1,  # Our CSV file doesn't have open interest data, set to -1
        dtformat='%Y-%m-%d %H:%M:%S',
        timeframe=bt.TimeFrame.Days,  # Daily data
        compression=1,  # Compression ratio of 1 for daily data
        headers=True  # Skip header row in CSV file
    )
    cerebro.adddata(data)

    # Add strategy
    cerebro.addstrategy(TrendStrategy, printlog=True)

    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # Print initial capital
    print(f'Initial Capital: {cerebro.broker.getvalue():.2f}')

    # Run backtest
    results = cerebro.run()

    # Get analysis results
    strat = results[0]
    sharpe_ratio = strat.analyzers.sharpe.get_analysis()
    drawdown = strat.analyzers.drawdown.get_analysis()
    trade_analysis = strat.analyzers.trades.get_analysis()

    # Print final capital and analysis results
    final_value = cerebro.broker.getvalue()
    print(f'Final Capital: {final_value:.2f}')
    # Calculate return using actual initial capital
    print(f'Total Return: {(final_value / initial_cash - 1) * 100:.2f}%')

    if isinstance(sharpe_ratio, dict) and 'sharperatio' in sharpe_ratio:
        print(f"Sharpe Ratio: {sharpe_ratio.get('sharperatio', 'N/A')}")
    else:
        print("Sharpe Ratio: N/A")

    if hasattr(drawdown, 'max') and hasattr(drawdown.max, 'drawdown'):
        print(f"Maximum Drawdown: {drawdown.max.drawdown:.2f}%")
    else:
        print("Maximum Drawdown: 0.00%")

    # Safely check trade analysis data
    try:
        if hasattr(trade_analysis, 'total') and hasattr(trade_analysis.total, 'total'):
            total_trades = trade_analysis.total.total
            if total_trades > 0:
                # Try to get number of winning and losing trades
                won_trades = 0
                lost_trades = 0

                if hasattr(trade_analysis, 'won') and hasattr(trade_analysis.won, 'total'):
                    won_trades = trade_analysis.won.total

                if hasattr(trade_analysis, 'lost') and hasattr(trade_analysis.lost, 'total'):
                    lost_trades = trade_analysis.lost.total

                win_rate = won_trades / total_trades * 100 if total_trades > 0 else 0
                print(f"Number of Trades: {total_trades}")
                print(f"Winning Trades: {won_trades}")
                print(f"Losing Trades: {lost_trades}")
                print(f"Win Rate: {win_rate:.2f}%")
            else:
                print("Number of Trades: 0")
                print("No trades executed")
        else:
            print("Number of Trades: 0")
            print("No trades executed")
    except Exception as e:
        print(f"Trade analysis error: {str(e)}")
        print("No trades executed")

    # Plot chart
    # cerebro.plot(style='candlestick')


if __name__ == '__main__':
    main()