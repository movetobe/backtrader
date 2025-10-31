from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import efinance as ef
import datetime
import pandas as pd
import numpy as np
# Import the backtrader platform
import backtrader as bt
from data import *
import config

from KnownOneStrategy import *
from KnownLog import *
from custom_sizer import PercentSizer100
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
    # strats = cerebro.optstrategy(
    #    TestStrategy,
    #    bb_period=range(7, 15),
    #    rsi_period=range(7, 15),
    #    macd_period=range(7, 15),
    #    bb_buy=np.arange(0.2, 0.4, 0.1),
    #    bb_sell=np.arange(0.8, 1.0, 0.1),
    #    rsi_buy = range(50, 60, 10),
    #    rsi_sell=range(70, 100, 10)
    # )

    # 添加数据
    stock_result = HistoricalData(stock_code=stock_code, beg=beg, end=end).get_data()  # 中国神华
    # print("stock_result:", stock_result)
    data = bt.feeds.PandasData(dataname=stock_result)
    # print("data:",data)
    # Add the Data Feed to Cerebro
    cerebro.adddata(data)

    # Set our desired cash start
    cerebro.broker.setcash(init_cash)

    # Add a custom Percent sizer: 每次买入占可用资金的百分比（这里设为10%），
    # 并将股数向上取整到 100 的整数倍
    cerebro.addsizer(PercentSizer100, percents=10, rounding=100)

    # Set the commission
    cerebro.broker.setcommission(commission=0.05)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')  # 收益率分析器:cite[2]
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')  # 回撤分析器:cite[2]
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')  # 夏普比率分析器:cite[2]
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')  # 交易分析器:cite[2]
    # Print out the starting conditions
    # 如果stock_result不为空，则取第一行的'name'字段
    if len(stock_result) > 0:
        stock_name_ = stock_result.iloc[0]['name']
        stock_code_ = stock_result.iloc[0]['code']
    else:
        logger.write('Error: stock_result is empty, stock:%s', stock_code)
        print("Error: stock_result is empty, stock:", stock_code)
        return

    logger.write(
        'Starting Name: %s, code: %s, Portfolio Value: %.2f' % (stock_name_, stock_code_, cerebro.broker.getvalue()))

    # Run over everything
    results = cerebro.run()
    strat = results[0]

    # 打印收益率结果
    returns_result = strat.analyzers.returns.get_analysis()
    # 累计回报率可能是 'rtot' 或 'compound'，具体可打印 returns_result 查看
    drawdown_result = strat.analyzers.drawdown.get_analysis()
    sharpe_result = strat.analyzers.sharpe.get_analysis()
    
    # Print out the final result
    logger.write('Final Name: %s, code: %s, Portfolio Value: %.2f' % (stock_name_, stock_code_, cerebro.broker.getvalue()))
    logger.write('累计收益率： %.2f%%' % (returns_result.get('rtot', 0) * 100 if returns_result.get('rtot') is not None else 0))
    logger.write('最大回撤： %.2f%%' % (drawdown_result['max']['drawdown'] if 'max' in drawdown_result and 'drawdown' in drawdown_result['max'] else 0))
    logger.write('夏普比率： %.2f' % (sharpe_result['sharperatio'] if 'sharperatio' in sharpe_result else 0))
    logger.write('======================')

    print("Backtesting finish:", stock_name_, stock_code_)
    # Plot the result
    # cerebro.plot()

    result = cerebro.broker.getvalue() - init_cash
    print(f"Profit for stock {stock_name_} ({stock_code_}): %.2f" % result)
    return result


if __name__ == '__main__':
    logger = KnownLog()

    # 清空 backtest_results.txt 文件
    logger.clear()

    # 获取股票列表
    stock_list = get_stock_list()
    total_profit = 0
    for stock in stock_list:
        print(f"Backtesting stock: {stock}")
        try:
            profit = backtest_stock(stock_code=stock, beg=backtest_params.get('beg', '20200101'),
                                         end=backtest_params.get('end', '20251231'),
                                         init_cash=backtest_params.get('init_cash', 100000))
            logger.write('收益： %.2f' % profit)
            total_profit += profit
        except Exception as e:
            logger.write(f"Error backtesting stock {stock}: {e}")
        time.sleep(5)  # 避免请求过于频繁

    logger.write('======================')
    logger.write('总收益： %.2f' % total_profit)
