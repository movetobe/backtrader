from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# Import the backtrader platform
from data import *
from util.log.KnownLog import logger
import math
from util.log.export_to_excel import exceler


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
        logger.write(txt, dt)

    def __init__(self):
        # Keep a reference to the "close" line in the data[0] dataseries
        self.dataclose = self.datas[0].close

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None
        self.cost = 0

        self.bb = None
        self.rsi = None
        self.macd = None
        self.hold = False

        self.buy_count = 0
        self.sell_count = 0

        self.bb = bt.indicators.BollingerBands(self.datas[0], period=self.params.bb_period)
        self.rsi = bt.indicators.RSI(self.datas[0], period=self.params.rsi_period)
        self.macd = bt.indicators.MACD(self.datas[0], period_me1=12, period_me2=26,
                                       period_signal=self.params.macd_period)
        # 交易单位（按多少股为一单位，向上/向下取整时使用）
        self.rounding = 100
        # 每次交易目标金额（人民币或对应货币），用于按金额计算股数并按 self.rounding 取整
        self.trade_amount = 1000.0

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # Buy/Sell order submitted/accepted to/by broker - Nothing to do
            return

        # Check if an order has been completed
        # Attention: broker could reject order if not enough cash
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    'BUY EXECUTED, Price: %.2f, Cost: %.2f, Comm: %.2f' %
                    (order.executed.price,
                     order.executed.value,
                     order.executed.comm))
                self.buyprice = order.executed.price
                self.buycomm = order.executed.comm
                self.buy_count += 1

                self.cost = self.cost + float(order.executed.price) * abs(order.executed.size)
                self.log("cost: %.2f" % self.cost)
                exceler.write_operation(operation_type="BUY EXECUTED", operation_detail=order.executed,
                                        accumulated_cost=self.cost,
                                        holding_size=self.position.size,
                                        time=self.datas[0].datetime.date(0))
            else:  # Sell
                self.log('SELL EXECUTED, Price: %.2f, Cost: %.2f, Comm: %.2f' %
                         (order.executed.price,
                          order.executed.value,
                          order.executed.comm))
                self.sell_count += 1
                self.cost = self.cost - float(order.executed.price) * abs(order.executed.size)
                self.log("cost: %.2f" % self.cost)
                exceler.write_operation(operation_type="SELL EXECUTED", operation_detail=order.executed,
                                        accumulated_cost=self.cost,
                                        holding_size=self.position.size,
                                        time=self.datas[0].datetime.date(0))
            self.bar_executed = len(self)

        # elif order.status in [order.Canceled, order.Margin, order.Rejected]:
        #    self.log('Order Canceled/Margin/Rejected')

        # Write down: no pending order
        self.order = None
        self.log("当前持仓： %d 股" % self.position.size)

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))
        # todo excel

    def next(self):
        # Check if an order is pending ... if yes, we cannot send a 2nd one
        if self.order:
            return

        # BB% = （股价 - 下轨）/（上轨 - 下轨）
        bbp = (self.dataclose[0] - self.bb.lines.bot[0]) / (self.bb.lines.top[0] - self.bb.lines[0])
        rsi = self.rsi[0]
        macd = self.macd[0]

        if bbp < self.params.bb_buy and rsi < self.params.rsi_buy and macd > self.params.macd_buy:
            # BUY, BUY, BUY!!! (with all possible default parameters)
            self.log('BUY SIGNAL, %.2f' % self.dataclose[0])

            exceler.write_signal(operation_type="BUY SIGNAL", price=self.dataclose[0],
                                 time=self.datas[0].datetime.date(0))
        if (
                bbp > self.params.bb_sell and rsi > self.params.rsi_sell):  # or self.dataclose[0] < self.buyprice * 0.95 or self.dataclose[0] > self.buyprice * 1.1:

            # SELL, SELL, SELL!!! (with all possible default parameters)
            self.log('SELL SIGNAL, %.2f' % self.dataclose[0])
            exceler.write_signal(operation_type="SELL SIGNAL", price=self.dataclose[0],
                                 time=self.datas[0].datetime.date(0))

        # Check if we are in the market
        # if not self.position:
        if self.broker.getcash() > 0:
            # BB% < 0.2 AND RSI < 45 AND MACD_DIF > 0
            if bbp < self.params.bb_buy and rsi < self.params.rsi_buy and macd > self.params.macd_buy:
                # BUY: 计算可买入股数并向上取整到 self.rounding 的整数倍（但不超过可用现金）
                price = float(self.dataclose[0])
                cash = float(self.broker.getcash())
                if price <= 0 or cash <= 0:
                    return

                # 按目标金额计算希望买入的股数，然后向上取整到 self.rounding 的倍数（在不超过现金的前提下）
                amount = min(self.trade_amount, cash)
                # 能买到的最大股数（整数）
                max_affordable = int(math.floor(cash / price))
                if max_affordable <= 0:
                    return

                raw_shares = amount / price
                # 向上取整到 self.rounding 的倍数
                size_up = int(math.ceil(raw_shares / self.rounding) * self.rounding)

                chosen_size = 0
                # 如果向上取整后的金额不超过可用现金，则使用之
                if size_up > 0 and size_up <= max_affordable:
                    chosen_size = size_up
                else:
                    # 否则退回到向下取整（保证不超出现金）
                    size_down = int(math.floor(raw_shares / self.rounding) * self.rounding)
                    # 若向下取整为0，则尝试使用最大可买但向下取整到 rounding 的倍数
                    if size_down <= 0:
                        chosen_size = int((max_affordable // self.rounding) * self.rounding)
                    else:
                        chosen_size = size_down

                if chosen_size <= 0:
                    return
                self.log(
                    'BUY CREATE, Price: %.2f, Size: %d (price=%.2f, cash=%.2f)' % (
                        self.dataclose[0], chosen_size, price, cash))
                exceler.write_op_create(operation_type="BUY CREATE", price=self.dataclose[0], size=chosen_size,
                                        time=self.datas[0].datetime.date(0))
                # Keep track of the created order to avoid a 2nd order
                self.order = self.buy(size=chosen_size)
            # else:
            if self.position.size > 0:
                # BB% > 0.8 OR RSI > 70 OR 止损触发（回撤>10%）
                # 如果超过10个bar，比如？天或者？周，且股票收益有大于5%，是否可以触发卖出？
                if (
                        bbp > self.params.bb_sell and rsi > self.params.rsi_sell):  # or self.dataclose[0] < self.buyprice * 0.95 or self.dataclose[0] > self.buyprice * 1.1:
                    # SELL: 按目标金额计算要卖出的股数，并向下取整到 self.rounding 的倍数（不超过持仓）
                    pos_size = int(self.position.size)
                    if pos_size <= 0:
                        return

                    price = float(self.dataclose[0])
                    raw_shares = self.trade_amount / price
                    # 向下取整到 rounding 的倍数
                    sell_size = int(math.floor(raw_shares / self.rounding) * self.rounding)

                    # 若持仓不足一个 rounding 单位，全部卖出
                    if pos_size < self.rounding:
                        sell_size = pos_size

                    # 限制不超过持仓
                    if sell_size > pos_size:
                        sell_size = pos_size

                    # Ensure minimum sell of 100 shares when possible
                    min_sell = max(100, self.rounding)
                    if pos_size >= min_sell and sell_size < min_sell:
                        # set to min_sell but not exceed current position
                        sell_size = min(min_sell, pos_size)

                    if sell_size <= 0:
                        return

                    self.log('SELL CREATE, Price:  %0.2f, Size: %d (price=%.2f, pos=%d)' % (
                        self.dataclose[0], sell_size, price, pos_size))
                    exceler.write_op_create(operation_type="SELL CREATE", price=self.dataclose[0], size=sell_size,
                                            time=self.datas[0].datetime.date(0))
                    # Keep track of the created order to avoid a 2nd order
                    self.order = self.sell(size=sell_size)

    def stop(self):
        starting = self.broker.startingcash
        final_value = self.broker.getvalue()

        if self.position.size == 0:
            profit_rate = ((final_value - starting) / starting)
            status = f"已卖出（空仓）, 总收益: {profit_rate:.2%}"
            exceler.write_state({
                "position_status": "空仓",
                "gross": final_value - starting,
                "yield_rate": profit_rate
            })
        else:
            # 依据用户要求的公式：收益率 = (当前价格 - 持仓成本) / 持仓数量
            pos_size = abs(int(self.position.size))
            current_price = float(self.dataclose[0])
            cost_price = float(self.cost) / pos_size if pos_size > 0 else float('nan')
            if cost_price > 0:
                profit_rate = ((current_price - cost_price) / cost_price)
            else:  # 成本为负时，每股收益率为无穷大，这里返回0
                profit_rate = 0

            status = f"持仓中，持有价格: {cost_price:.2f}，当前价格：{current_price:.2f}，每股收益: {profit_rate:.2%}"
            exceler.write_state({
                "position_status": "持仓中",
                "gross": final_value - starting,
                "cost_price": cost_price,
                "current_price": current_price,
                "yield_rate": profit_rate
            })
        self.log(f"股票状态: {status}")

        if ((final_value - starting) / starting) >= self.params.profit_target:
            self.log(
                '(bb Period %2d) (rsi period %2d) (macd period %2d) (bb_buy %2f) (bb_sell %2f) (rsi_buy %2d) (rsi_sell %2d) (buy_count %2d) (sell_count %2d) Ending Value %.2f' %
                (self.params.bb_period, self.params.rsi_period, self.params.macd_period, self.params.bb_buy,
                 self.params.bb_sell, self.params.rsi_buy, self.params.rsi_sell, self.buy_count, self.sell_count,
                 final_value))
