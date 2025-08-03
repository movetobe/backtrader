import backtrader as bt
import math
import numpy as np

##############################
# 基本面指标自定义实现
##############################
class FCFYield(bt.Indicator):
    """
    自由现金流收益率（FCF Yield）：
       (经营活动现金流净额 - 资本支出) / 总市值
    假设数据源中包含字段：
       self.data.cash_flow, self.data.capex, self.data.total_market_cap
    """
    lines = ('fcf_yield',)
    plotinfo = dict(subplot=False)

    def next(self):
        # 注意除数为 0 的判断
        tm = self.data.total_market_cap[0]
        if tm and tm != 0:
            self.lines.fcf_yield[0] = (self.data.cash_flow[0] - self.data.capex[0]) / tm
        else:
            self.lines.fcf_yield[0] = 0.0


class DCI(bt.Indicator):
    """
    分红承诺强度（DCI）：
       (当期分红率 - 行业平均分红率) * 未来三年承诺分红比例下限
    假设数据源中包含字段：
       self.data.dividend_rate, self.data.industry_avg_dividend_rate, self.data.future_dividend_lower_bound
    """
    lines = ('dci',)
    plotinfo = dict(subplot=False)

    def next(self):
        self.lines.dci[0] = (self.data.dividend_rate[0] - self.data.industry_avg_dividend_rate[0]) * \
                            self.data.future_dividend_lower_bound[0]


class CPR(bt.Indicator):
    """
    长协价格韧性（CPR）：
       1 - (现货煤价跌幅 / 公司自产煤售价跌幅)
    假设数据源中包含字段：
       self.data.spot_price_decline, self.data.self_price_decline
    """
    lines = ('cpr',)
    plotinfo = dict(subplot=False)

    def next(self):
        sp = self.data.spot_price_decline[0]
        cp = self.data.self_price_decline[0]
        if cp and cp != 0:
            self.lines.cpr[0] = 1 - (sp / cp)
        else:
            self.lines.cpr[0] = 0.0


#####################################
# 技术指标自定义实现
#####################################
class TSI(bt.Indicator):
    """
    趋势强度指数（TSI）：
       100 * EMA(EMA(价格差, long_period), short_period) /
           EMA(EMA(绝对价格差, long_period), short_period)
    参数默认 long_period=25, short_period=13
    使用收盘价差值作为价格差
    """
    lines = ('tsi',)
    params = (('long_period', 25), ('short_period', 13))
    plotinfo = dict(subplot=False)

    def __init__(self):
        price_diff = self.data.close - self.data.close(-1)
        abs_price_diff = abs(price_diff)
        ema_long = bt.indicators.EMA(price_diff, period=self.p.long_period)
        ema_long_short = bt.indicators.EMA(ema_long, period=self.p.short_period)
        ema_abs_long = bt.indicators.EMA(abs_price_diff, period=self.p.long_period)
        ema_abs_long_short = bt.indicators.EMA(ema_abs_long, period=self.p.short_period)
        # 注意除数需判断不为零
        self.lines.tsi = bt.If(ema_abs_long_short != 0,
                               100 * ema_long_short / ema_abs_long_short,
                               0)


class VWAPIndicator(bt.Indicator):
    """
    成交量加权平均价格（VWAP）
    VWAP = 累计(成交量*典型价格) / 累计(成交量)
    为便于和布林带结合，这里采用一个滚动窗口计算 VWAP，窗口长由 period 参数确定。
    假设典型价格采用 (高+低+收盘)/3
    """
    lines = ('vwap',)
    params = (('period', 20),)
    plotinfo = dict(subplot=False)

    def __init__(self):
        self.addminperiod(self.p.period)

    def next(self):
        period = self.p.period
        vol_sum = 0.0
        vtp_sum = 0.0
        for i in range(period):
            if len(self.data) > i:
                typical = (self.data.high[-i] + self.data.low[-i] + self.data.close[-i]) / 3.0
                vol = self.data.volume[-i]
                vol_sum += vol
                vtp_sum += vol * typical
        if vol_sum != 0:
            self.lines.vwap[0] = vtp_sum / vol_sum
        else:
            self.lines.vwap[0] = self.data.close[0]


class VWAP_BB(bt.Indicator):
    """
    成交量加权布林带百分比指标（VWAP-BB%）：
      (股价 - VWAP下轨) / (VWAP上轨 - VWAP下轨)
    计算步骤：
      1. 使用上面 VWAPIndicator 计算 VWAP 序列；
      2. 对 VWAP 序列使用 BollingerBands 得到上轨和下轨；
      3. 用当时的收盘价代替股价。
    """
    lines = ('vwap_bb_pct',)
    params = (('vwap_period', 20), ('bb_period', 20), ('devfactor', 2))
    plotinfo = dict(subplot=False)

    def __init__(self):
        self.vwap = VWAPIndicator(self.data, period=self.p.vwap_period)
        self.bb = bt.indicators.BollingerBands(self.vwap, period=self.p.bb_period, devfactor=self.p.devfactor)

    def next(self):
        upper = self.bb.lines.top[0]
        lower = self.bb.lines.bot[0]
        # 防止分母为 0
        if (upper - lower) != 0:
            self.lines.vwap_bb_pct[0] = (self.data.close[0] - lower) / (upper - lower)
        else:
            self.lines.vwap_bb_pct[0] = 0.0


#####################################
# 市场情绪指标自定义实现
#####################################
class DYSpread(bt.Indicator):
    """
    股息率溢价（DY Spread）：
      (动态股息率 - 10年期国债收益率) - 过去5年均值
    假设数据源中包含字段：
      self.data.dynamic_dividend_yield, self.data.treasury_10y, self.data.five_year_avg
    """
    lines = ('dy_spread',)
    plotinfo = dict(subplot=False)

    def next(self):
        self.lines.dy_spread[0] = (self.data.dynamic_dividend_yield[0] - self.data.treasury_10y[0]) - \
                                  self.data.five_year_avg[0]


class IHC(bt.Indicator):
    """
    机构持仓变化（IHC）：
      (季度基金持仓占比 - 上季度占比) * 成交量放大倍数
    假设数据源中包含字段：
      self.data.fund_hold_pct, self.data.last_quarter_fund_hold_pct, self.data.volume_multiplier
    """
    lines = ('ihc',)
    plotinfo = dict(subplot=False)

    def next(self):
        self.lines.ihc[0] = (self.data.fund_hold_pct[0] - self.data.last_quarter_fund_hold_pct[0]) * \
                            self.data.volume_multiplier[0]


import backtrader as bt
import math
import pandas as pd
import yfinance as yf
from datetime import datetime


# 自定义OBV指标实现（替代内置版本）
class CustomOBV(bt.Indicator):
    lines = ('obv',)
    params = (('period', 1),)

    def __init__(self):
        self.addminperiod(2)  # 需要至少2个数据点
        # 初始化第一个OBV值
        #self.lines.obv[0] = 0

    def next(self):
        # 确保有足够的数据点（至少2个）
        if len(self.data) < 2:
            self.lines.obv[0] = 0
            return

        # 获取当前和前一日收盘价
        current_close = self.data.close[0]
        prev_close = self.data.close[-1]
        current_volume = self.data.volume[0]

        # 获取前一日OBV值
        prev_obv = self.lines.obv[-1]

        # 计算当前OBV
        if np.isnan(prev_obv):
            #print("NO prev_OBv!!!")
            self.lines.obv[0] = current_volume
            return

        if current_close > prev_close:
            self.lines.obv[0] = prev_obv + current_volume
        elif current_close < prev_close:
            self.lines.obv[0] = prev_obv - current_volume
        else:
            self.lines.obv[0] = prev_obv

# 自定义线性回归指标
class LinearRegressionIndicator(bt.Indicator):
    lines = ('lr',)
    params = (('period', 5),)

    def __init__(self):
        self.addminperiod(self.params.period)

    def next(self):
        # 获取最近period个数据点
        y = self.data.get(size=self.params.period)
        x = np.arange(len(y))

        # 计算线性回归斜率
        if len(y) >= 2:
            slope, _ = np.polyfit(x, y, 1)
            self.lines.lr[0] = slope
        else:
            self.lines.lr[0] = 0

# 自定义函数应用指标
class ApplyFunction(bt.Indicator):
    lines = ('output',)
    params = (('func', None),)

    def __init__(self, input_line):
        self.input_line = input_line
        super(ApplyFunction, self).__init__()

    def next(self):
        try:
            self.lines.output[0] = self.p.func(self.input_line[0])
        except:
            self.lines.output[0] = 0.0


# 自定义信号变化率指标
class SignalChangeRate(bt.Indicator):
    lines = ('change_rate',)

    def __init__(self, signal_line):
        self.signal = signal_line
        super(SignalChangeRate, self).__init__()
        self.addminperiod(2)

    def next(self):
        if len(self.signal) > 1 and self.signal[-1] != 0:
            self.lines.change_rate[0] = self.signal[0] / self.signal[-1]
        else:
            self.lines.change_rate[0] = 1.0

def obv_transform(x):
    try:
        # 使用双曲正切函数替代对数函数，避免极端值问题
        return math.tanh(x * 0.1) * 2
    except:
        return 0.0
