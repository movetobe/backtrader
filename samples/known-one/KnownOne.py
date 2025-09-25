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
from KnownOneStrategy import *
from KnownLog import *
import time

def get_stock_list():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    stock_list_path = os.path.join(current_dir, 'stock_list.txt')

    with open(stock_list_path, 'r', encoding='utf-8') as f:
        stock_list = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]

    return stock_list

def backtest_stock(stock_code, beg, end, init_cash):
    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    cerebro.addstrategy(KnownOneStrategy)
    # Add a strategy
    #strats = cerebro.optstrategy(
    #    KnownOneStrategy,
    #    bb_period=range(7, 15),
    #    rsi_period=range(7, 15),
    #    macd_period=range(7, 15),
    #    bb_buy=np.arange(0.2, 0.4, 0.1),
    #    bb_sell=np.arange(0.8, 1.0, 0.1),
    #    rsi_buy = range(50, 60, 10),
    #    rsi_sell=range(70, 100, 10)
    #)

    # 添加数据
    stock_result = HistoricalData(stock_code=stock_code, beg=beg, end=end).get_data() #中国神华
    data = bt.feeds.PandasData(dataname=stock_result)
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    # Set our desired cash start
    cerebro.broker.setcash(init_cash)

    # Add a FixedSize sizer according to the stake
    # cerebro.addsizer(bt.sizers.FixedSize, stake=1000)  # 按固定股份
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)  # 按资金比例

    # Set the commission
    cerebro.broker.setcommission(commission=0)

    # Print out the starting conditions
    logger.write('Starting Name: %s Portfolio Value: %.2f' % (stock_code, cerebro.broker.getvalue()))

    # Run over everything
    cerebro.run()

    # Print out the final result
    logger.write('Final Name: %s Portfolio Value: %.2f' % (stock_code, cerebro.broker.getvalue()))

    logger.write('======================')
    # Plot the result
    #cerebro.plot()

    result = cerebro.broker.getvalue()

    return result

if __name__ == '__main__':
    logger = KnownLog()

    # 清空 backtest_results.txt 文件
    logger.clear()

    # 获取股票列表
    stock_list = get_stock_list()

    for stock in stock_list:
        print(f"Backtesting stock: {stock}")
        try:
            final_value = backtest_stock(stock_code=stock, beg='20240101', end='20251231', init_cash=100000)
        except Exception as e:
            logger.write(f"Error backtesting stock {stock}: {e}")
            
        time.sleep(5)  # 避免请求过于频繁