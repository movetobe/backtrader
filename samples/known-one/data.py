import backtrader as bt
import efinance as ef
import pandas as pd
from efinance.common.config import MarketType
import util.conf.config as config


def to_bt_dataframe(df):
    columns_to_copy = ['股票名称', '股票代码', '日期', '开盘', '收盘', '最高', '最低', '成交量', '振幅']
    new_column_names = ['name', 'code', 'Date', 'Open', 'Close', 'High', 'Low', 'Volume', 'OpenInterest']
    # 创建一个列名映射字典
    column_mapping = dict(zip(columns_to_copy, new_column_names))

    # 拷贝并重命名列
    new_df = df[columns_to_copy].rename(columns=column_mapping).copy()
    new_df['Date'] = pd.to_datetime(new_df['Date'])
    new_df.set_index('Date', inplace=True)

    return new_df


def handle_stock_code(stock_code):
    is_hk = stock_code.endswith('-HK')
    code = stock_code.replace('-HK', '').strip() if is_hk else stock_code
    return is_hk, code


class HistoricalData(bt.feeds.PandasData):
    def __init__(self, stock_code, beg, end):
        # 周线 前复权
        backtest_params = config.backtest_param()

        is_hk, code = handle_stock_code(stock_code)
        if is_hk:
            stock_result = ef.stock.get_quote_history(code, beg, end, klt=backtest_params.get('klt', 102),
                                                      fqt=backtest_params.get('fqt', 1),
                                                      market_type=MarketType.Hongkong)
        else:
            stock_result = ef.stock.get_quote_history(code, beg, end, klt=backtest_params.get('klt', 102),
                                                      fqt=backtest_params.get('fqt', 1))

        stock_result = to_bt_dataframe(stock_result)
        # self.data = bt.feeds.PandasData(dataname=stock_result)
        self.data = stock_result

    def get_data(self):
        return self.data
