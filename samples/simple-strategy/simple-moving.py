from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import efinance as ef
import datetime
import pandas as pd
import numpy as np
# Import the backtrader platform
import backtrader as bt
from data import *

# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
        ('buy_maperiod', 10),
        ('sell_maperiod', 20),
        ('bb_period', 10),
        ('rsi_period', 10),
        ('macd_period', 10),
        ('bb_buy', 0.2),
        ('bb_sell', 0.9),
        ('rsi_buy', 50),
        ('rsi_sell', 70),
        ('macd_buy', 0),
        ('macd_sell', 0)
    )
    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        print('%s, %s' % (dt.isoformat(), txt))

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        self.bb = None
        self.rsi = None
        self.macd = None
        self.hold = False

        self.buy_count = 0
        self.sell_count = 0

        # Add a MovingAverageSimple indicator
        self.buy_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.buy_maperiod)
        self.sell_sma = bt.indicators.SimpleMovingAverage(
            self.datas[0], period=self.params.sell_maperiod)

        self.bb  = bt.indicators.BollingerBands(self.datas[0], period=self.params.bb_period)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        self.macd = bt.indicators.MACD(self.datas[0], period_me1=12, period_me2=26, period_signal=self.params.macd_period)

        # Indicators for the plotting show
        '''
        bt.indicators.ExponentialMovingAverage(self.datas[0], period=25)
        bt.indicators.WeightedMovingAverage(self.datas[0], period=25,
                                            subplot=True)
        bt.indicators.StochasticSlow(self.datas[0])
        bt.indicators.MACDHisto(self.datas[0])
        rsi = bt.indicators.RSI(self.datas[0])
        bt.indicators.SmoothedMovingAverage(rsi, period=10)
        bt.indicators.ATR(self.datas[0], plot=False)
        '''

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                #self.log(
                #    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                #    (order.executed.price,
                #     order.executed.value,
                #     order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.buy_count += 1
            else:  # Sell
                #self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                #           (order.executed.price,
                #           order.executed.value,
                #          order.executed.comm))
                self.sell_count += 1

            self.bar_executed = len(self)

        #elif order.status in [order.Canceled, order.Margin, order.Rejected]:
        #    self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        #self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
        #         (trade.pnl, trade.pnlcomm))

    def next(self):
        # Simply log the closing price of the series from the reference
        # self.log('Close, %.2f' % self.dataclose[0])

        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # BB% = （股价 - 下轨）/（上轨 - 下轨）
        bbp = (self.dataclose[0] - self.bb.lines.bot[0]) / (self.bb.lines.top[0] - self.bb.lines[0])
        rsi = self.rsi[0]
        macd = self.macd[0]

        # Check if we are in the market
        if not self.position:
            # BB% < 0.2 AND RSI < 45 AND MACD_DIF > 0
            if bbp < self.params.bb_buy and rsi < self.params.rsi_buy and macd > self.params.macd_buy:

                # BUY, BUY, BUY!!! (with all possible default parameters)
                # self.log('BUY CREATE, %.2f' % self.dataclose[0])

                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy()

        else:
            # BB% > 0.8 OR RSI > 70 OR 止损触发（回撤>10%）
            if bbp > self.params.bb_sell or rsi > self.params.rsi_sell:# or self.dataclose[0] < self.position.price * 0.9:

          # SELL, SELL, SELL!!! (with all possible default parameters)
                #self.log('SELL CREATE, %.2f' % self.dataclose[0])

                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()

    def stop(self):
        if ((self.broker.getvalue() - 100000) / 100000) >= 0.05:
            self.log('(bb Period %2d) (rsi period %2d) (macd period %2d) (bb_buy %2f) (bb_sell %2f) (rsi_buy %2d) (rsi_sell %2d) (buy_count %2d) (sell_count %2d) Ending Value %.2f' %
                 (self.params.bb_period, self.params.rsi_period, self.params.macd_period, self.params.bb_buy, self.params.bb_sell, self.params.rsi_buy, self.params.rsi_sell, self.buy_count, self.sell_count, self.broker.getvalue()))

def to_bt_dataframe(df):
    columns_to_copy = ['日期', '开盘', '收盘', '最高', '最低', '成交量', '振幅']
    new_column_names = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'OpenInterest']
    # 创建一个列名映射字典
    column_mapping = dict(zip(columns_to_copy, new_column_names))

    # 拷贝并重命名列
    new_df = df[columns_to_copy].rename(columns=column_mapping).copy()
    new_df['Date'] = pd.to_datetime(new_df['Date'])
    new_df.set_index('Date', inplace=True)

    return new_df

if __name__ == '__main__':
    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    # cerebro.addstrategy(TestStrategy)
    # Add a strategy
    strats = cerebro.optstrategy(
        TestStrategy,
        bb_period=range(7, 15),
        rsi_period=range(7, 15),
        macd_period=range(7, 15),
        bb_buy=np.arange(0.2, 0.4, 0.1),
        bb_sell=np.arange(0.8, 1.0, 0.1),
        rsi_buy = range(50, 60, 10),
        rsi_sell=range(70, 100, 10)
    )

    # 添加数据
    stock_result = HistoricalData(stock_code='601088', beg='20240101', end='20241231').get_data()
    print("stock_result: ", stock_result)
    data = bt.feeds.PandasData(dataname=stock_result)
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    # Set our desired cash start
    cerebro.broker.setcash(100000.0)

    # Add a FixedSize sizer according to the stake
    #cerebro.addsizer(bt.sizers.FixedSize, stake=1000)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)

    # Set the commission
    cerebro.broker.setcommission(commission=0)

    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Run over everything
    cerebro.run()

    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())
    # Plot the result
    # cerebro.plot()