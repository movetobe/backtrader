import os
import time
import pandas as pd
import atexit


# from openpyxl import Workbook
# from openpyxl import load_workbook

class ToExcel:

    def __init__(self, filename, filedir="../../log/"):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        excel_path = os.path.join(current_dir, filedir)
        os.makedirs(excel_path, exist_ok=True)

        self.file_path = os.path.abspath(os.path.join(excel_path, filename))
        self.data = []
        self.reset()

        # 退出时写表格
        atexit.register(self.export_to_excel)

    def reset(self):
        self.stock_name = None
        self.stock_code = None
        self.portfolio = None
        self.final_portfolio = None
        self.position_status = None
        self.yield_rate = None
        self.error_msg = None

    def write(self, txt, dt=None):
        self._parse(txt, dt)

    def _parse(self, txt, dt):
        op_time = dt
        signal_type = None
        signal_price = None
        op_type = None
        price = None
        size = None

        # 提取股票名称和代码
        if "Starting Name" in txt:
            self.reset()

            parts = txt.split(',')
            self.stock_name = parts[0].split(':')[1].strip()
            self.stock_code = parts[1].split(':')[1].strip()
            self.portfolio = float(parts[2].split(':')[1].strip())

        elif "Final Name" in txt:
            parts = txt.split(',')
            self.final_portfolio = float(parts[2].split(':')[1].strip())

        elif "BUY EXECUTED" in txt:
            op_type = "买入"
            price = float(txt.split('Price: ')[1].split(',')[0])
            size = int(txt.split('size=')[1].split(' ')[0])

        elif "SELL EXECUTED" in txt:
            op_type = "卖出"
            price = float(txt.split('Price: ')[1].split(',')[0])
            size = int(txt.split('size=')[1].split(' ')[0])

        elif "BUY SIGNAL" in txt:
            signal_type = "买入信号"
            signal_price = float(txt.split(', ')[1])

        elif "SELL SIGNAL" in txt:
            signal_type = "卖出信号"
            signal_price = float(txt.split(', ')[1])

        elif "股票状态: 持仓中" in txt:
            self.position_status = "持有中"
            self.yield_rate = float(txt.split('收益: ')[1].strip('%'))

        elif "股票状态: 已卖出" in txt:
            self.position_status = "已卖出"
            self.yield_rate = float(txt.split('收益: ')[1].strip('%'))

        elif "Error backtesting stock" in txt:
            self.stock_code = txt.split("stock ")[1].split(':')[0]
            self.error_msg = txt.split(": ")[1]

        # 如果有足够的信息，创建一条记录
        if self.stock_name and self.stock_code:
            self.data.append({
                '股票名称': self.stock_name,
                '代码': self.stock_code,
                '启动资金': f"{self.portfolio:.2f}%" if self.portfolio is not None else None,
                '时间': op_time,
                '买卖信号': signal_type,
                '信号价格': signal_price,
                '买卖操作': op_type,
                '价格': price,
                '数量': size,
                '持仓状态': self.position_status,
                '收益率': f"{self.yield_rate:.2f}%" if self.yield_rate is not None else None,
                '最终资金': f"{self.final_portfolio:.2f}%" if self.final_portfolio is not None else None,
                '错误信息': self.error_msg
            })

    def export_to_excel(self):
        df = pd.DataFrame(self.data)

        # 导出到 Excel
        df.to_excel(self.file_path, index=False, engine='openpyxl')

        # 使用 openpyxl 合并单元格
        # wb = load_workbook(self.file_path)
        # ws = wb.active
        #
        # # 获取所有股票代码
        # stock_codes = df['代码'].unique()
        #
        # for code in stock_codes:
        #     # 找到该股票的所有行
        #     rows = [i for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)) if row[1] == code]
        #
        #     if len(rows) > 1:
        #         start_row = rows[0] + 1  # Excel 行号从 1 开始
        #         end_row = rows[-1] + 1
        #         # 合并 '股票名称' 和 '代码' 列
        #         ws.merge_cells(f'A{start_row}:A{end_row}')
        #         ws.merge_cells(f'B{start_row}:B{end_row}')
        #
        # wb.save(self.file_path)
