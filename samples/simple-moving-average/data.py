import backtrader as bt
import efinance as ef
import pandas as pd

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

class HistoricalData(bt.feeds.PandasData):
    def __init__(self, stock_code, beg, end):
        stock_result = ef.stock.get_quote_history(stock_code, beg, end)

        stock_result = to_bt_dataframe(stock_result)
        print("typeof stock_result is", type(stock_result))
        print(stock_result)
        #self.data = bt.feeds.PandasData(dataname=stock_result)
        self.data = stock_result

    def get_data(self):
        return self.data