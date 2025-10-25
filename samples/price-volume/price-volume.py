import efinance as ef
import backtrader as bt
import pandas as pd
import numpy as np
import datetime
import time
from tqdm import tqdm
import warnings
from data import *
import math
warnings.filterwarnings('ignore')

# 设置中文字体显示
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC"]

watching = []
class price_volume_strategy(bt.Strategy):
    """
    连续三天收盘价和成交量都上涨，第四天买入，持有3-5天卖出的策略
    """
    params = (
        ('hold_days_min', 3),   # 最短持有天数
        ('hold_days_max', 3),   # 最长持有天数
    )
    
    def __init__(self):
        # 记录持仓天数
        self.hold_days = 0
        # 收盘价
        self.close = self.datas[0].close
        self.open = self.datas[0].open
        self.high = self.datas[0].high
        self.stock_code = self.datas[0].params.dataname  # 获取股票代码
        # 成交量
        self.volume = self.datas[0].volume

        #self.year_sma = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=120)

        # To keep track of pending orders and buy price/commission
        self.order = None
        self.buyprice = None
        self.buycomm = None

        self.buy_count = 0
        self.sell_count = 0

    def log(self, txt, dt=None):
        ''' Logging function fot this strategy'''
        dt = dt or self.datas[0].datetime.date(-1)
        print('%s, %s' % (dt.isoformat(), txt))

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

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('Order Canceled/Margin/Rejected')
        elif order.status in [order.Expired]:
            self.log('Order Expired')
        # Write down: no pending order
        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return

        self.log('OPERATION PROFIT, GROSS %.2f, NET %.2f' %
                 (trade.pnl, trade.pnlcomm))

    def warn_to_buy(self):
        # 检查是否有连续3天收盘价和成交量都上涨
        if len(self) < 2:
            return

        close_up = ((self.close[0] > self.close[-1]))

        open_up = ((self.open[0] > self.open[-1]))

        volume_up = ((self.volume[0] > self.volume[-1]))

        red = (self.close[0] > self.open[0]) and (self.close[-1] > self.open[-1])
        red = True
        if close_up and open_up and volume_up and red:
            print(f"关注买入信号：{self.datas[0].datetime.date(0)}, 近2天收盘价: {self.close[0]}, {self.close[-1]}, 近2天成交量: {self.volume[0]}, {self.volume[-1]}")
            if (self.datas[0].datetime.date(0) == '2023-08-01'):
                watching = [watching, self.stock_code]

    def next(self):
        if self.order:
            return
        # 如果没有持仓
        if not self.position:
            # 检查是否有连续3天收盘价和成交量都上涨
            # warning to buy
            self.warn_to_buy()
            if len(self) >= 3:  # 确保有足够的数据
                # 连续3天收盘价上涨
                close_up = ((self.close[0] > self.close[-1]) and 
                           (self.close[-1] > self.close[-2]))

                open_up = ((self.open[0] > self.open[-1]) and 
                           (self.open[-1] > self.open[-2]))

                red = (((self.close[0] > self.open[0])) and
                       ((self.close[-1] > self.open[-1])) and
                       ((self.close[-2] > self.open[-2])))
                print(f"{self.datas[0].datetime.date()}, close: {self.close[0]}, {self.close[-1]}, {self.close[-2]}, open: {self.open[0]}, {self.open[-1]}, {self.open[-2]}")
                #up = ((self.open[0] > self.open[-1] and self.open[0] < self.close[-1]) and
                #(self.open[-1] > self.open[-2] and self.open[-1] < self.close[-2]))
                up = True
                # 连续3天成交量上涨
                volume_up = ((self.volume[0] > self.volume[-1]) and 
                             (self.volume[-1] > self.volume[-2]))

                # 年线之上
                #year_sma_up = (self.close[0] > self.year_sma[0])
                year_sma_up = True
                # 如果满足条件，则买入
                if red and close_up and open_up and up and volume_up and year_sma_up:
                    # 全仓买入
                    self.size = (math.floor(((self.broker.getcash() / self.close[0]) / 100) * 0.8) * 100)
                    print(f"买入信号：{self.datas[0].datetime.date(0)} - 收盘价: {self.close[0]}, 成交量: {self.volume[0]}, cash: {self.broker.getcash()}, size: {self.size}")
                    print(f"近3天价格: {self.close[0]}, {self.close[-1]}, {self.close[-2]}, 近3天成交量: {self.volume[0]}, {self.volume[-1]}, {self.volume[-2]}")
                    if self.size > 0:
                        self.order = self.buy(size=self.size)
                        self.hold_days = 0  # 重置持仓天数计数
        else:
            # 已经持仓，增加持仓天数
            self.hold_days += 1
            #print(f"持仓天数: {self.hold_days}, 当前收盘价: {self.close[0]}, 成交量: {self.volume[0]}")
            if (self.hold_days >= self.params.hold_days_min):
                print(f"卖出信号：{self.datas[0].datetime.date(0)} - 持仓天数: {self.hold_days}, 卖出价: {self.close[0]}, 收益率: {(self.close[0] - self.buyprice) / self.buyprice:.2%}")
                self.order = self.sell(size=self.position.size)
            elif (((self.high[0] - self.buyprice) / self.buyprice) >= 0.05):
                print(f"卖出信号：{self.datas[0].datetime.date(0)} - 持仓天数: {self.hold_days}, 卖出价: {self.high[0]}, 收益率: {(self.close[0] - self.buyprice) / self.buyprice:.2%}")
                self.order = self.sell(size=self.position.size)

    def stop(self):
        if (self.buy_count == self.sell_count) and self.buy_count > 0:
            print(f"策略结束，最终资金: {self.broker.getvalue():.2f}, 买入次数: {self.buy_count}, 卖出次数: {self.sell_count}")

def get_index_members():
    """
    获取沪深300指数、中证500指数和创业板指的成分股代码
    返回一个包含所有成分股代码的列表
    """
    # 指数代码：沪深300(000300)、中证500(000905)、创业板指(399006)
    index_codes = {
        "沪深300": "000300",
        "中证500": "000905",
        "创业板指": "399006"
    }
    
    all_members = []
    
    for name, code in index_codes.items():
        try:
            # 获取指数成分股
            members = ef.stock.get_members(code)
            print(members)
            # 提取股票代码并添加到列表
            stock_codes = members["股票代码"].astype(str).tolist()
            all_members.extend(stock_codes)
            
            print(f"成功获取{name}成分股，共{len(stock_codes)}只股票")
        except Exception as e:
            print(f"获取{name}成分股失败: {e}")
    
    # 去重处理（有些股票可能同时属于多个指数）
    all_members = list(set(all_members))
    all_members = [code for code in all_members if not code.startswith('688')]
    print(f"三个指数成分股去重后共{len(all_members)}只股票")
    
    return all_members

def get_stock_codes():
    return get_index_members()

def get_stock_info(stock_code, start_date, end_date):
    """获取指定股票的历史数据"""
    try:
        # 调用efinance的get_quote_history函数获取数据
        df = ef.stock.get_quote_history(stock_code, start_date=start_date, end_date=end_date)
        
        # 数据处理
        if df is None or df.empty:
            return None
            
        # 重命名列名以适应backtrader
        df = df.rename(columns={
            '日期': 'datetime',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '成交额': 'amount'
        })
        
        # 转换日期格式
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        
        # 按日期排序
        df = df.sort_index()
        
        # 添加换手率列（如果需要）
        if '换手率' in df.columns:
            df = df.rename(columns={'换手率': 'turnover'})
        
        return df
    except Exception as e:
        print(f"获取股票 {stock_code} 数据出错: {e}")
        return None

def backtrade_one_stock(stock_code, start_date, end_date, initial_cash=100000):
    """回测单个股票"""
    # 获取股票数据
    #df = get_stock_info(stock_code, start_date, end_date)
    #if df is None or len(df) < 10:  # 数据不足则跳过
    #    return None
    
    # 创建回测引擎
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(price_volume_strategy)
    cerebro.broker.set_coc(True)  # 允许在收盘价成交

    stock_result = HistoricalData(stock_code = stock_code, beg=start_date, end=end_date).get_data()
    data = bt.feeds.PandasData(dataname=stock_result)
    # 将数据转换为backtrader可识别的格式
    cerebro.adddata(data, name=stock_code)
    
    # 设置初始资金
    cerebro.broker.setcash(initial_cash)
    
    # 设置佣金（千分之一）
    cerebro.broker.setcommission(commission=0)
    
    # 记录交易
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trade_analyzer')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    
    # 运行回测
    print(f"\n开始回测股票: ({stock_code})")
    results = cerebro.run()
    strategy = results[0]
    
    # 获取回测结果
    final_value = cerebro.broker.getvalue()
    returns = strategy.analyzers.returns.get_analysis()
    drawdown = strategy.analyzers.drawdown.get_analysis()
    
    # 计算交易统计
    trade_analyzer = strategy.analyzers.trade_analyzer.get_analysis()
    total_trades = trade_analyzer.total.total if hasattr(trade_analyzer.total, 'total') else 0
    time.sleep(1)
    if total_trades == 0:
        return None

    # 打印结果
    print(f"初始资金: {initial_cash:.2f}")
    print(f"最终资金: {final_value:.2f}")
    print(f"总收益率: {(final_value/initial_cash - 1)*100:.2f}%")
    print(f"最大回撤: {drawdown.max.drawdown:.2f}%")
    print(f"总交易次数: {total_trades}")
    
    # 保存结果
    result = {
        'stock_code': stock_code,
        'initial_cash': initial_cash,
        'final_value': final_value,
        'return_rate': (final_value/initial_cash - 1)*100,
        'max_drawdown': drawdown.max.drawdown,
        'total_trades': total_trades,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    # 绘制回测图
    #cerebro.plot(style='candlestick', iplot=False, volume=True)[0][0]
    #plt.title(f"({stock_code}) 回测结果")
    #plt.savefig(f"{stock_code}_backtest.png")
    #plt.close()
    with open('backtest_results.txt', 'a', encoding='utf-8') as f:
        f.write(str(result) + '\n')

    time.sleep(5)
    return result

def start_price_volume(start_date, end_date, initial_cash=100000, max_stocks=None):
    """批量回测多个股票"""
    # 获取A股股票列表
    print("获取A股股票列表中...")
    stock_list = get_stock_codes()
    print(f"get number of stocks: {len(stock_list)}")
    
    # 如果设置了最大股票数量，则截断列表
    if max_stocks and len(stock_list) > max_stocks:
        stock_list = stock_list[:max_stocks]
    
    # 存储所有回测结果
    all_results = []
    total_revenue = 0
    stock_list = ['601138']
    # 逐个回测
    for i, stock_code in enumerate(tqdm(stock_list, desc="回测进度")):
        try:
            # 回测
            result = backtrade_one_stock(stock_code, start_date, end_date, initial_cash)
            
            if result:
                all_results.append(result)
                total_revenue += (result['final_value'] - initial_cash)
                print(f"累计总收益: {total_revenue:.2f}")
            # 每回测5只股票休息一下，避免请求过于频繁
            if (i + 1) % 5 == 0:
                time.sleep(5)
                
        except Exception as e:
            print(f"处理股票 {stock_code} 时出错: {e}")
            continue
    
    return result

if __name__ == "__main__":
    # 设置回测时间段
    start_date = "20250728"
    end_date = "20250801"

    # 初始资金
    initial_cash = 50000

    result = start_price_volume(start_date, end_date, initial_cash)
    print("watching: ", watching)
    # 打印最终资金
    print("final: ", result)