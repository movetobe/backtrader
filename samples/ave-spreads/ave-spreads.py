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
plt.rcParams["font.family"] = ["Heiti TC"]

watching = []
class ave_spreads_strategy(bt.Strategy):
    """
    连续三天均线开屏，第四天买入，持有3-5天卖出的策略
    """

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
        # 均线指标
        self.sma5 = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=5)
        self.sma10 = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=10)
        self.sma20 = bt.indicators.SimpleMovingAverage(self.datas[0].close, period=20)

        # 策略可调参数（也可以改为 params）
        self.ma_days = 5
        self.ma_overlap_pct = 0.05
        # 连续缩口触发天数（当开口连续缩小多少天时触发清仓）
        self.ma_shrink_days = 3
        # 当5/10日均线开口相对缩小超过该比例时触发清仓（例如 0.01 表示缩小超过1%触发）
        self.ma_shrink_pct = 0.01
        # 买入使可用现金的百分比（0.8 表示用 80% 的现金买入）
        self.buy_cash_pct = 0.8
        # 取整单位（每次买卖按多少股为一单位，默认100）
        self.rounding = 100
        # 用于追踪开口扩张事件：买入后第2次开口扩张时减仓1半，第3次清仓
        self.expansion_events = 0
        self.prev_expanded = False
        # 标记第2次扩张是否已执行过减仓（防止重复减仓）
        self.second_sold = False
        # 最大持仓天数作为兜底（可按需调整）
        self.hold_days_max = 20

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

    def _ma_opening_expanding(self, days=5):
        """检查过去 `days` 个交易日中，5/10/20 日均线是否呈开口扩张趋势，且最新满足 5>10>20

        实现细节：计算每一天的差值 d1 = sma5-sma10, d2 = sma10-sma20，
        要求这两组差值在过去 `days` 天内呈严格递增趋势（即开口逐日放大），并且最新一天的差值均为正。
        """
        # 需要足够的数据来计算 20 日均线
        need_bars = 20 + days
        if len(self) < need_bars:
            return False

        d1_list = []  # sma5 - sma10
        d2_list = []  # sma10 - sma20

        # 组织从古到今的序列：offset days-1 ... 0
        for off in range(days - 1, -1, -1):
            try:
                a = float(self.sma5[-off])
                b = float(self.sma10[-off])
                c = float(self.sma20[-off])
            except Exception:
                return False

            d1_list.append(a - b)
            d2_list.append(b - c)

        # 判断窗口起始日（最老一天）是否“几乎重叠”
        try:
            # 使用起始日的 sma20 作为基准标尺，允许以百分比判断重叠
            start_sma20 = float(self.sma20[-(days - 1)])
            overlap_thresh = abs(start_sma20) * self.ma_overlap_pct
        except Exception:
            overlap_thresh = 0.0

        if not (abs(d1_list[0]) <= overlap_thresh and abs(d2_list[0]) <= overlap_thresh):
            # 起始日并非近似重叠
            return False

        # 最新一天必须为正（5>10>20）
        if not (d1_list[-1] > 0 and d2_list[-1] > 0):
            return False

        # 要求两组差值在窗口内呈单调递增（即从几乎重叠到逐日放大）
        for i in range(1, len(d1_list)):
            if not (d1_list[i] >= d1_list[i - 1] and d2_list[i] >= d2_list[i - 1]):
                return False

        return True

    def _ma_consecutive_squeezed(self, days=20):
        """检查过去 `days` 个交易日中，5/10/20 日均线是否始终近似重叠（即缝合）

        实现细节：对每一天计算 d1 = abs(sma5 - sma10), d2 = abs(sma10 - sma20)，
        要求这两组差值在过去 `days` 天内均小于等于起始日的 overlap_thresh（基于 sma20 的百分比阈值）。
        """
        # 需要足够的数据来计算 20 日均线
        need_bars = 20 + days
        if len(self) < need_bars:
            return False

        d1_list = []  # abs(sma5 - sma10)
        d2_list = []  # abs(sma10 - sma20)

        for off in range(days - 1, -1, -1):
            try:
                a = float(self.sma5[-off])
                b = float(self.sma10[-off])
                c = float(self.sma20[-off])
            except Exception:
                return False

            d1_list.append(abs(a - b))
            d2_list.append(abs(b - c))

        try:
            start_sma20 = float(self.sma20[-(days - 1)])
            overlap_thresh = abs(start_sma20) * self.ma_overlap_pct
        except Exception:
            overlap_thresh = 0.0

        # 要求窗口内所有天的 d1 和 d2 均在阈值以内
        for i in range(len(d1_list)):
            if not (d1_list[i] <= overlap_thresh and d2_list[i] <= overlap_thresh):
                return False

        return True

    def _ma_narrowing_consecutive(self, days=3):
        """检查最近是否出现连续 `days` 天的 5/10 日均线开口缩小。

        实现：构造长度为 days+1 的开口绝对值序列 d_t,...,d_{t-days}，
        检查每一天是否相较于前一天按照相对阈值 self.ma_shrink_pct 缩小：
            d_i < d_{i-1} * (1 - self.ma_shrink_pct)
        若全部为真则返回 True。
        """
        need_bars = 20 + days + 1
        if len(self) < need_bars:
            return False

        d_list = []
        # 从更早到当前，索引 offset 从 days 到 0
        for off in range(days, -1, -1):
            try:
                a = float(self.sma5[-off])
                b = float(self.sma10[-off])
            except Exception:
                return False
            d_list.append(abs(a - b))

        # 需要 days 次严格相对缩小判断（比较 d[i] 与 d[i-1]）
        for i in range(1, len(d_list)):
            prev = d_list[i - 1]
            cur = d_list[i]
            # 若前一天开口为 0，则无法判断相对缩小，视为不满足
            if prev <= 0:
                return False
            if not (cur < prev * (1.0 - self.ma_shrink_pct)):
                return False

        return True

    def next(self):
        if self.order:
            return

        # 只使用开口扩张策略：当均线由近似重叠转为开口扩张时买入
        if not self.position:
            # 更严格的买入条件：要求过去 self.ma_days 天均线缝合（squeezed），且当天出现开口（5>10>20）
            ma_squeezed = self._ma_consecutive_squeezed(days=self.ma_days)
            try:
                d1_today = float(self.sma5[0]) - float(self.sma10[0])
                d2_today = float(self.sma10[0]) - float(self.sma20[0])
            except Exception:
                d1_today = d2_today = 0.0

            if ma_squeezed and d1_today > 0 and d2_today > 0:
                cash = self.broker.getcash()
                price = float(self.close[0])
                if price <= 0 or cash <= 0:
                    return

                raw_shares = (cash * self.buy_cash_pct) / price
                size = int(math.floor(raw_shares / self.rounding) * self.rounding)
                if size <= 0:
                    return

                self.log(f'BUY CREATE by MA opening expansion, price: {price:.2f}, size: {size}')
                self.order = self.buy(size=size)
                # reset expansion tracking after 进仓
                self.hold_days = 0
                self.expansion_events = 0
                self.prev_expanded = False
                self.second_sold = False
        else:
            # 当5/10日均线的“开口”连续缩小 self.ma_shrink_days 天时，清仓卖出
            try:
                if self._ma_narrowing_consecutive(days=self.ma_shrink_days):
                    self.log(f'FULL SELL on MA narrowing for {self.ma_shrink_days} days: {self.datas[0].datetime.date(0)}, hold_days: {self.hold_days}')
                    self.order = self.sell(size=self.position.size)
                    return
            except Exception:
                # 如果均线数据不足或检测失败，则忽略该条件，继续执行后续逻辑
                pass

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
    cerebro.addstrategy(ave_spreads_strategy)

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
    cerebro.plot()
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

def start_ave_spreads(start_date, end_date, initial_cash=100000, max_stocks=None):
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
    stock_list = ['小米集团']  # 测试用
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

if __name__ == "__main__":
    # 设置回测时间段
    start_date = "20240101"
    end_date = "20251231"

    # 初始资金
    initial_cash = 50000

    start_ave_spreads(start_date, end_date, initial_cash)