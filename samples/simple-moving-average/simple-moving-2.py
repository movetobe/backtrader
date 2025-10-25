from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import efinance as ef
import datetime
import pandas as pd
import numpy as np
# Import the backtrader platform
import backtrader as bt
from indicators import *

# Create a Stratey
class TestStrategy(bt.Strategy):
    params = (
        ('verbose', True),  # 是否打印交易日志
        ('risk_per_trade', 0.01),  # 单笔交易风险比例
        ('atr_period', 12),  # ATR周期
        ('trend_filter', 1.01),  # 趋势强度阈值
        ('sc_buy', 1.1),  # 买入信号阈值
        ('ts_sell', 0.99),  # 卖出信号阈值
        ('vr_buy', 0.5),
        ('vr_sell', 0.85),
    )


    def log(self, txt, dt=None):
        '''日志函数'''
        if self.params.verbose:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt.isoformat()}, {txt}')

    def __init__(self):
        # 数据引用
        self.data_close = self.datas[0].close
        self.data_high = self.datas[0].high
        self.data_low = self.datas[0].low
        self.data_volume = self.datas[0].volume

        # 1. 趋势维度指标
        self.hma = bt.indicators.HullMovingAverage(self.data_close, period=20)
        self.ema = bt.indicators.ExponentialMovingAverage(self.data_close, period=50)
        self.trend_strength = self.hma / self.ema

        # 2. 动量维度指标
        self.macd = bt.indicators.MACD(self.data_close)
        self.rsi = bt.indicators.RelativeStrengthIndex(self.data_close, period=14)

        # 动量因子计算
        rsi_component = (self.rsi - 45) * 0.5
        macd_component = self.macd.macd * 2
        self.momentum_factor = bt.Max(rsi_component, macd_component)

        # 波动率标准化
        self.stddev = bt.indicators.StdDev(self.data_close, period=14)
        self.stddev_norm = bt.DivByZero(self.momentum_factor, self.stddev, zero=1.0)

        # 3. 波动率维度指标
        self.bbands = bt.indicators.BollingerBands(self.data_close, period=20)
        self.volatility_ratio = (self.data_close - self.bbands.bot) / (self.bbands.top - self.bbands.bot)

        # 4. 成交量维度指标
        self.obv = CustomOBV(self.data)
        self.obv_slope = LinearRegressionIndicator(self.obv, period=5)

        # 量能加速器 (非线性变换)
        self.obv_accel = ApplyFunction(input_line = self.obv_slope.lr, func=obv_transform)
        # 5. 辅助指标
        self.atr = bt.indicators.AverageTrueRange(
            self.datas[0], period=self.params.atr_period
        )

        # 6. 核心复合信号
        self.composite_signal = bt.If(
            self.trend_strength > self.params.trend_filter,
            self.stddev_norm * self.volatility_ratio * self.obv_accel,
            0
        )

        # 7. 信号变化率 (用于检测突破)
        # 在策略的__init__方法中：
        self.signal_change = bt.DivByZero(self.composite_signal, self.composite_signal(-1), zero=1.0)

        # 跟踪变量
        self.order = None
        self.buy_price = None
        self.buy_size = None
        self.stop_loss = None
        self.buy_comm = None

        self.buy_count = 0
        self.sell_count = 0

    def next(self):
        # 取消未完成订单
        if self.order:
            return

        # 交易信号
        # buy_signal =  (self.signal_change[0] > 1.3) and (self.volatility_ratio[0] < 0.5)
        buy_signal = (self.signal_change[0] > self.params.sc_buy) and (self.volatility_ratio[0] < self.params.vr_buy)
        # 检查持仓
        if not self.position:
            # 买入条件
            if buy_signal:
                # 执行买入
                # BUY, BUY, BUY!!! (with all possible default parameters)
                self.log('BUY CREATE, %.2f' % self.data.close[0])
                self.order = self.buy()
        else:
            # 卖出条件1: 触及布林带上轨
            #exit_bb = self.volatility_ratio[0] > 0.85
            exit_bb = self.volatility_ratio[0] > self.params.vr_sell

            # 卖出条件2: MACD动能衰减
            exit_macd = self.macd.macd[0] < 0

            # 卖出条件3: 动态止损
            #exit_stop = self.data_close[0] < self.stop_loss

            # 卖出条件4: 趋势反转
            #exit_trend = self.trend_strength[0] < 0.98
            exit_trend = self.trend_strength[0] < self.params.ts_sell

            # 任一条件满足则卖出
            #if exit_bb or exit_macd or exit_stop or exit_trend:
            if exit_bb or exit_macd or exit_trend:
                # SELL, SELL, SELL!!! (with all possible default parameters)
                self.log('SELL CREATE, %.2f' % self.data.close[0])
                self.order = self.sell()

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
                self.buy_price = order.executed.price
                self.buy_comm = order.executed.comm
                self.buy_size = order.executed.size
                self.buy_count += 1
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm %.2f' %
                           (order.executed.price,
                           order.executed.value,
                          order.executed.comm))
                self.sell_count += 1

        #elif order.status in [order.Canceled, order.Margin, order.Rejected]:
        #    self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def stop(self):
        if ((self.broker.getvalue() - 100000) / 100000) >= 0.15:
            self.log('(risk_per_trade %.2f) (atr_period %.2f) (trend_filter %.2f) (sc_buy %.2f)   (ts_sell %.2f) (vr_buy %.2f) (vr_sell %.2f) (buy_count %2d) (sell_count %2d) Ending Value %.2f' %
                 (self.params.risk_per_trade, self.params.atr_period, self.params.trend_filter, self.params.sc_buy, self.params.ts_sell, self.params.vr_buy, self.params.vr_sell, self.buy_count, self.sell_count, self.broker.getvalue()))


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
    #cerebro.addstrategy(TestStrategy)
    # Add a strategy

    strats = cerebro.optstrategy(
        TestStrategy,
        risk_per_trade=np.arange(0.01, 0.03, 0.01),  # 单笔交易风险比例
        atr_period=range(12, 15),  # ATR周期
        trend_filter=np.arange(1, 1.05, 0.01),  # 趋势强度阈值
        sc_buy=np.arange(1.1, 1.5, 0.1),  # 买入信号阈值
        ts_sell=np.arange(0.95, 1.00, 0.01),  # 卖出信号阈值
        vr_buy=np.arange(0.4, 0.6, 0.1),
        vr_sell=np.arange(0.80, 0.90, 0.01),
    )


    stock_code = '601088'
    stock_result = ef.stock.get_quote_history(stock_code, beg='20230101', end='20231231')

    stock_result = to_bt_dataframe(stock_result)
    print("typeof stock_result is", type(stock_result))
    print(stock_result)

    data = bt.feeds.PandasData(dataname = stock_result)
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
    cerebro.plot()