from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import efinance as ef
import datetime
import pandas as pd
import numpy as np
# Import the backtrader platform
import backtrader as bt
from data import *


from KnownOneStrategy import *
from util.log.KnownLog import logger
from util.log.export_to_excel import exceler
from custom_sizer import PercentSizer100
import time
import util.conf.config as config
import os
import sys


def get_stock_list(file):
    if not os.path.exists(file):
        logger.write(f"file not exist:{file}\n")
        return []

    with open(file, 'r', encoding='utf-8') as f:
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
    exceler.write_state({
        "stock_name": stock_name_,
        "stock_code": stock_code_,
        "portfolio": cerebro.broker.getvalue()})

    # Run over everything
    results = cerebro.run()
    strat = results[0]

    # 打印收益率结果
    returns_result = strat.analyzers.returns.get_analysis()
    # 累计回报率可能是 'rtot' 或 'compound'，具体可打印 returns_result 查看
    drawdown_result = strat.analyzers.drawdown.get_analysis()
    sharpe_result = strat.analyzers.sharpe.get_analysis()

    # Print out the final result
    final_portfolio = cerebro.broker.getvalue()
    cumulative_return = returns_result.get('rtot', 0) * 100 if returns_result.get('rtot') is not None else 0
    max_drawdown = drawdown_result['max']['drawdown'] if 'max' in drawdown_result and 'drawdown' in drawdown_result[
        'max'] else 0
    sharpe_ratio = sharpe_result['sharperatio'] if 'sharperatio' in sharpe_result else 0

    logger.write('Final Name: %s, code: %s, Portfolio Value: %.2f' % (stock_name_, stock_code_, final_portfolio))
    logger.write('累计收益率： %.2f%%' % cumulative_return)
    logger.write('最大回撤： %.2f%%' % max_drawdown)
    logger.write('夏普比率： %.2f' % sharpe_ratio)

    exceler.write_state({
        "final_portfolio": final_portfolio,
        "cumulative_return": cumulative_return,
        "max_drawdown": max_drawdown,
        "sharpe_ratio": sharpe_ratio
    })

    logger.write('======================')

    print(f"Backtesting finish:{stock_name_}({stock_code_})")
    # Plot the result
    # cerebro.plot()

    result = cerebro.broker.getvalue() - init_cash
    print(f"Profit for stock {stock_name_} ({stock_code_}): %.2f" % result)
    return result


if __name__ == '__main__':

    backtest_params = config.backtest_param()
    stock_file_list = config.stock_file_list()
    total_profit = 0

    if len(stock_file_list) == 0:
        print(f"Error: stock_file_list is empty, please check config.yml")
        exit(1)

    for stock_file in stock_file_list:
        print(f"====== stock file: {stock_file} ======")

        base_name = os.path.splitext(os.path.basename(stock_file))[0]

        logger.init(filename=base_name + '.log')
        exceler.init(filename=base_name + '.xlsx')

        stock_list = get_stock_list(stock_file)

        if not stock_list:
            continue

        for stock in stock_list:
            print(f"Backtesting stock: {stock}")
            try:
                profit = backtest_stock(stock_code=stock, beg=backtest_params.get('beg', '20200101'),
                                        end=backtest_params.get('end', '20251231'),
                                        init_cash=backtest_params.get('init_cash', 100000))

                logger.write('收益： %.2f' % profit)
                total_profit += profit
                exceler.write_finish()
            except Exception as e:

                exc_type, exc_obj, exc_tb = sys.exc_info()

                # 获取完整调用栈
                stack_summary = []
                while exc_tb is not None:
                    frame = exc_tb.tb_frame
                    stack_summary.append(
                        f"File \"{frame.f_code.co_filename}\", line {exc_tb.tb_lineno}, "
                        f"in {frame.f_code.co_name}\n"
                        f"  Local vars: {frame.f_locals}\n"
                    )
                    exc_tb = exc_tb.tb_next

                print(f"Backtesting fail: {stock}, Exception: {exc_type.__name__}: {str(e)}\n")
                logger.write(
                    f"\n===== ERROR TRACE =====\n"
                    f"Stock: {stock}\n"
                    f"Exception: {exc_type.__name__}: {str(e)}\n"
                    f"Full traceback:\n"
                    f"{''.join(reversed(stack_summary))}\n"
                    f"======================\n"
                )

            time.sleep(5)  # 避免请求过于频繁

        exceler.export_to_excel()

    logger.write('======================')
    logger.write('总收益： %.2f' % total_profit)
