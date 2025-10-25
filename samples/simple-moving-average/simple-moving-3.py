import backtrader as bt
import math
from data import *
from indicators import *
import logging
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

def obv_transform(x):
    try:
        # 使用双曲正切函数替代对数函数，避免极端值问题
        return math.tanh(x * 0.1) * 2
    except:
        return 0.0

class MultiFactorStrategy(bt.Strategy):
    params = (
        ('verbose', True),  # 是否打印交易日志
        ('risk_per_trade', 0.01),  # 单笔交易风险比例
        ('atr_period', 14),  # ATR周期
        ('trend_filter', 1.02),  # 趋势强度阈值
        ('sc_buy', 1.3),  # 买入信号阈值
        ('ts_sell', 0.98),  # 卖出信号阈值
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
                # 动态仓位计算
                risk_capital = self.broker.getvalue() * self.params.risk_per_trade
                position_size = risk_capital / self.atr[0]

                # 转换为股票数量
                size = int(position_size / self.data_close[0])

                if size > 0:
                    # 执行买入
                    self.order = self.buy(size=size)
                    self.log(f'BUY EXECUTED, Price: {self.data_close[0]:.2f}, Size: {size}')

                    # 设置初始止损
                    self.stop_loss = self.data_close[0] - 1.5 * self.atr[0]
        else:
            # 卖出条件1: 触及布林带上轨
            #exit_bb = self.volatility_ratio[0] > 0.85
            exit_bb = self.volatility_ratio[0] > self.params.vr_sell

            # 卖出条件2: MACD动能衰减
            exit_macd = self.macd.macd[0] < 0

            # 卖出条件3: 动态止损
            exit_stop = self.data_close[0] < self.stop_loss

            # 卖出条件4: 趋势反转
            #exit_trend = self.trend_strength[0] < 0.98
            exit_trend = self.trend_strength[0] < self.params.ts_sell

            # 更新移动止损 (追踪最高价的回撤)
            self.stop_loss = max(
                self.stop_loss,
                self.data_high[0] - 1.5 * self.atr[0]
            )

            # 任一条件满足则卖出
            if exit_bb or exit_macd or exit_stop or exit_trend:
                self.order = self.sell(size=self.position.size)
                reason = "BB" if exit_bb else "MACD" if exit_macd else "STOP" if exit_stop else "TREND"
                self.log(f'SELL EXECUTED ({reason}), Price: {self.data_close[0]:.2f}')
                self.stop_loss = None

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.buy_price = order.executed.price
                self.buy_size = order.executed.size
            elif order.issell():
                self.buy_price = None
                self.buy_size = None

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')

        self.order = None

    def stop(self):
        if ((self.broker.getvalue() - 100000) / 100000) >= 0:
            self.log('Ending Value: %.2f' % self.broker.getvalue())
        #self.log('Final Portfolio Value: %.2f' % self.broker.getvalue())


# 策略优化扩展
class MultiFactorOpt(MultiFactorStrategy):
    params = (
        ('trend_filter', (1.01, 1.03)),  # 趋势强度阈值范围
        ('signal_threshold', (1.25, 1.35)),  # 信号变化率阈值范围
        ('stop_multiplier', (1.3, 1.7)),  # 止损乘数范围
    )

    def __init__(self):
        super().__init__()
        # 动态调整参数
        market_vol = bt.indicators.StdDev(self.data_close, period=30)[0] / self.data_close[0]

        if market_vol > 0.03:  # 高波动市场
            self.p.trend_filter = self.p.trend_filter[1]  # 使用上限
            self.p.signal_threshold = self.p.signal_threshold[1]
            self.p.stop_multiplier = self.p.stop_multiplier[1]
        else:  # 低波动市场
            self.p.trend_filter = self.p.trend_filter[0]  # 使用下限
            self.p.signal_threshold = self.p.signal_threshold[0]
            self.p.stop_multiplier = self.p.stop_multiplier[0]

        # 更新信号阈值
        self.buy_signal = bt.And(
            self.signal_change > self.p.signal_threshold,
            self.volatility_ratio < 0.5
        )

        # 更新止损计算
        self.stop_multiplier = self.p.stop_multiplier

    def next(self):
        # 更新止损乘数
        if not self.position:
            self.stop_multiplier = self.p.stop_multiplier
        super().next()


# 使用示例
if __name__ == '__main__':
    logging.getLogger().setLevel(logging.ERROR)
    cerebro = bt.Cerebro()

    # 添加数据
    stock_result = HistoricalData(stock_code='601088', beg='20240101', end='20251231').get_data()
    print("stock_result: ", stock_result)
    data = bt.feeds.PandasData(dataname=stock_result)
    cerebro.adddata(data)

    # 添加策略
    # cerebro.addstrategy(MultiFactorStrategy)
    cerebro.optstrategy(MultiFactorStrategy,
                        risk_per_trade=np.arange(0.01, 0.03, 0.01),  # 单笔交易风险比例
                        atr_period=range(12, 15),  # ATR周期
                        trend_filter=np.arange(1, 1.05, 0.01),  # 趋势强度阈值
                        sc_buy=np.arange(1.1, 1.5, 0.1),  # 买入信号阈值
                        ts_sell=np.arange(0.95, 1.00, 0.01),  # 卖出信号阈值
                        vr_buy=np.arange(0.4, 0.6, 0.1),
                        vr_sell=np.arange(0.80, 0.90, 0.01),
                        )

    # 设置初始资金
    cerebro.broker.set_cash(100000.0)
    cerebro.addsizer(bt.sizers.PercentSizer, percents=95)
    # 设置交易手续费
    cerebro.broker.setcommission(commission=0.0005)  # 0.05%手续费

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual_return')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', riskfreerate=0.0)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    # 运行回测
    results = cerebro.run(runonce=False)

    # 打印结果
    strat = results[0]
    print("result: ", strat.analyzers.annual_return.get_analysis())
    '''
    print("\n年化收益率: {:.2f}%".format(
        strat.analyzers.annual_return.get_analysis()['annreturn']
    ))
    print("夏普比率: {:.3f}".format(
        strat.analyzers.sharpe.get_analysis()['sharperatio']
    ))
    print("最大回撤: {:.2f}%".format(
        strat.analyzers.drawdown.get_analysis()['max']['drawdown']
    ))
    '''
    # 绘制图表
    cerebro.plot(style='candlestick', volume=False)
