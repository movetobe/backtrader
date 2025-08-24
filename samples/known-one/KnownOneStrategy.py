from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import efinance as ef
import datetime
import pandas as pd
import numpy as np
# Import the backtrader platform
import backtrader as bt
from data import *
import os
from KnownLog import *

# Create a Strategy
class KnownOneStrategy(bt.Strategy):
    params = (
        ('buy_maperiod', 10),
        ('sell_maperiod', 20),
        ('bb_period', 9),
        ('rsi_period', 7),
        ('macd_period', 10),
        ('bb_buy', 0.2),
        ('bb_sell', 0.9),
        ('rsi_buy', 50),
        ('rsi_sell', 80),
        ('macd_buy', 0),
        ('macd_sell', 0),
        ('profit_target', 0.08)
    )
    def log(self, txt, dt=None):
        ''' Logging function for this strategy'''
        dt = dt or self.datas[0].datetime.date(0)
        logger = KnownLog()
        logger.write(txt, dt)

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

        self.bb  = bt.indicators.BollingerBands(self.datas[0], period=self.params.bb_period)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        self.macd = bt.indicators.MACD(self.datas[0], period_me1=12, period_me2=26, period_signal=self.params.macd_period)

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.buy_count += 1
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                           (order.executed.price,
                           order.executed.value,
                          order.executed.comm))
                self.sell_count += 1

            self.bar_executed = len(self)

        #elif order.status in [order.Canceled, order.Margin, order.Rejected]:
        #    self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def next(self):
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
                self.log('BUY CREATE, %.2f' % self.dataclose[0])
                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy()
        else:
            # BB% > 0.8 OR RSI > 70 OR 止损触发（回撤>10%）
            # 如果超过10个bar，比如？天或者？周，且股票收益有大于5%，是否可以触发卖出？
            if (bbp > self.params.bb_sell and rsi > self.params.rsi_sell): # or self.dataclose[0] < self.buyprice * 0.95 or self.dataclose[0] > self.buyprice * 1.1:
            # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.dataclose[0])
                # Keep track of the created order to avoid a 2nd order
                self.order = self.sell()

    def stop(self):
        starting = self.broker.startingcash
        final_value = self.broker.getvalue()
        
        if self.position.size == 0:
            status = "已卖出（空仓）"
        else:
            status = f"持仓中，持有价格: {self.buyprice}，当前价格：{self.dataclose[0]}，持有数量: {self.position.size}"
        self.log(f"股票状态: {status}")

        if ((final_value - starting) / starting) >= self.params.profit_target:
            self.log('(bb Period %2d) (rsi period %2d) (macd period %2d) (bb_buy %2f) (bb_sell %2f) (rsi_buy %2d) (rsi_sell %2d) (buy_count %2d) (sell_count %2d) Ending Value %.2f' %
                 (self.params.bb_period, self.params.rsi_period, self.params.macd_period, self.params.bb_buy, self.params.bb_sell, self.params.rsi_buy, self.params.rsi_sell, self.buy_count, self.sell_count, final_value))