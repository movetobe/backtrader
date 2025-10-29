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
from custom_sizer import PercentSizer100
import time
import yaml  # 新增导入

def load_config():
    """加载配置文件"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(current_dir, 'config.yml')

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found at {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def backtest_stock(stock_code, beg, end, init_cash, klt, fqt, market_type: Union[MarketType, None] = None):
    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    cerebro.addstrategy(KnownOneStrategy)
    # Add a strategy
    #strats = cerebro.optstrategy(
    #    TestStrategy,
    #    bb_period=range(7, 15),
    #    rsi_period=range(7, 15),
    #    macd_period=range(7, 15),
    #    bb_buy=np.arange(0.2, 0.4, 0.1),
    #    bb_sell=np.arange(0.8, 1.0, 0.1),
    #    rsi_buy = range(50, 60, 10),
    #    rsi_sell=range(70, 100, 10)
    #)

    # 添加数据
    stock_result = HistoricalData(stock_code,beg, end, klt, fqt, market_type).get_data()
    data = bt.feeds.PandasData(dataname=stock_result)
    cerebro.adddata(data)

    # Set our desired cash start
    cerebro.broker.setcash(init_cash)

    # Add a custom Percent sizer: 每次买入占可用资金的百分比（这里设为10%），
    # 并将股数向上取整到 100 的整数倍
    cerebro.addsizer(PercentSizer100, percents=10, rounding=100)

    # Set the commission
    cerebro.broker.setcommission(commission=0.05)

    # Print out the starting conditions
    # 如果stock_result不为空，则取第一行的'name'字段
    if len(stock_result) > 0:
        stock_name_ = stock_result.iloc[0]['name']
        stock_code_ = stock_result.iloc[0]['code']
    else:
        logger.write('Error: stock_result is empty, stock:%s', stock_code)
        print("Error: stock_result is empty, stock:", stock_code)
        return

    logger.write('Starting Name: %s, code: %s, Portfolio Value: %.2f' % (stock_name_, stock_code_, cerebro.broker.getvalue()))

    # Run over everything
    cerebro.run()

    # Print out the final result
    logger.write('Final Name: %s, code: %s, Portfolio Value: %.2f' % (stock_name_, stock_code_, cerebro.broker.getvalue()))

    logger.write('======================')

    print("Backtesting finish:", stock_name_, stock_code_)
    # Plot the result
    #cerebro.plot()

    result = cerebro.broker.getvalue()

    return result

if __name__ == '__main__':
    logger = KnownLog()

    # 清空 backtest_results.txt 文件
    logger.clear()

    # 读配置
    config = load_config()
    backtest_params = config.get('backtest_params', {})
    def handle_stock(stock_type):
        stock_list = config.get(stock_type, {})
        if not stock_list:
            return

        # 遍历股票列表
        for stock in stock_list:
            print(f"Backtesting stock: {stock}")
            try:
                if stock_type == 'HK_stock':
                    final_value = backtest_stock(
                        stock_code=stock,
                        beg=backtest_params.get('beg', '20200101'),
                        end=backtest_params.get('end', '20251231'),
                        init_cash=backtest_params.get('init_cash', 100000),
                        klt=backtest_params.get('klt', 102),
                        fqt=backtest_params.get('fqt', 1),
                        market_type=MarketType.Hongkong
                    )
                else:
                    final_value = backtest_stock(
                        stock_code=stock,
                        beg=backtest_params.get('beg', '20200101'),
                        end=backtest_params.get('end', '20251231'),
                        init_cash=backtest_params.get('init_cash', 100000),
                        klt=backtest_params.get('klt', 102),
                        fqt=backtest_params.get('fqt', 1)
                    )
            except Exception as e:
                logger.write(f"Error backtesting stock {stock}: {e}")

            time.sleep(5)

    handle_stock('A_stock')
    handle_stock('HK_stock')