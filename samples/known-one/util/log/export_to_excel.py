import os
# import time
import pandas as pd
# import atexit
from util.log.KnownLog import logger

from openpyxl import Workbook
from openpyxl import load_workbook
from openpyxl.styles import Alignment
import util.conf.config as config


class ToExcel:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, filename=None):
        if self._initialized or filename is None:
            return
        filedir = config
        self.init(filename, filedir)
        self._initialized = True

    def init(self, filename="backtrade_result.xlsx"):
        excel_path = config.output_dir()
        os.makedirs(excel_path, exist_ok=True)

        self.file_path = os.path.abspath(os.path.join(excel_path, filename))

        if os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                logger.write(f"Cleared existing file: {self.file_path}")
            except Exception as e:
                logger.write(f"Error clearing file {self.file_path}: {str(e)}")

        self.data = []
        self.reset()

    def reset(self):
        self.stock_name = None
        self.stock_code = None
        self.portfolio = None
        self.final_portfolio = None
        self.position_status = None
        self.yield_rate = None
        self.error_msg = None
        self.hold_size = None

    # def write(self, txt, dt=None):
    #     self._parse(txt, dt)

    def _create_record(self, **kwargs):
        """Helper method to create a standardized record dictionary"""
        record = {
            '股票名称': self.stock_name,
            '代码': self.stock_code,
            '启动资金': f"{self.portfolio:.2f}" if self.portfolio is not None else None,
            '时间': kwargs.get('time'),
            '操作': kwargs.get('op_type'),
            '价格': kwargs.get('price'),
            '数量': kwargs.get('size'),
            '交易金额': kwargs.get('value'),
            '交易佣金': kwargs.get('comm'),
            '持仓状态': kwargs.get('position_status'),
            '当前持仓': kwargs.get('hold_size'),
            '收益率': f"{self.yield_rate:.2f}%" if self.yield_rate is not None else None,
            '最终资金': f"{self.final_portfolio:.2f}" if self.final_portfolio is not None else None
        }
        return record

    def write_init(self, name, code, portfolio):
        self.reset()
        self.stock_name = name
        self.stock_code = code
        self.portfolio = portfolio
        self.data.append(self._create_record())

    def write_final(self, final_portfolio):
        self.final_portfolio = final_portfolio
        self.data.append(self._create_record(
            position_status=self.position_status,
            hold_size=self.hold_size
        ))

    def write_op(self, op_type, op_detail, time):
        self.data.append(self._create_record(time=time,
                                             op_type=op_type,
                                             price=op_detail.price,
                                             size=op_detail.size,
                                             value=op_detail.value,
                                             comm=op_detail.comm))

    def _parse(self, txt, dt):
        op_time = dt
        op_type = None
        price = None
        size = None
        cost = None
        comm = None

        logger.write(f"parse:{txt},{dt}\n")

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
            cost = float(txt.split('Cost: ')[1].split(',')[0])
            comm = float(txt.split('Comm: ')[1].split(' ')[0])

        elif "SELL EXECUTED" in txt:
            op_type = "卖出"
            price = float(txt.split('Price: ')[1].split(',')[0])
            cost = float(txt.split('Cost: ')[1].split(',')[0])
            comm = float(txt.split('Comm: ')[1].split(' ')[0])

        elif "BUY SIGNAL" in txt:
            op_type = "买入信号"
            price = float(txt.split(', ')[1])

        elif "SELL SIGNAL" in txt:
            op_type = "卖出信号"
            price = float(txt.split(', ')[1])

        elif "BUY CREATE" in txt:
            op_type = "买入创建"
            price = float(txt.split('Price: ')[1].split(',')[0])
            size = int(txt.split('Size: ')[1].split(' ')[0])

        elif "SELL CREATE" in txt:
            op_type = "卖出创建"
            price = float(txt.split('Price: ')[1].split(',')[0])
            size = int(txt.split('Size: ')[1].split(' ')[0])

        elif "股票状态: 持仓中" in txt:
            self.position_status = "持有中"
            self.yield_rate = float(txt.split('收益: ')[1].strip('%'))

        elif "股票状态: 已卖出" in txt:
            self.position_status = "已卖出"
            self.yield_rate = float(txt.split('收益: ')[1].strip('%'))

        elif "当前持仓" in txt:
            size = int(txt.split("当前持仓：")[1].split("股")[0].strip())

        else:
            logger.write("[error] cannot parse:", txt)
            return

        # elif "Error backtesting stock" in txt:
        #     self.stock_code = txt.split("stock ")[1].split(':')[0]
        #     self.error_msg = txt.split(": ")[1]
        # 如果有足够的信息，创建一条记录
        if self.stock_name and self.stock_code:
            self.data.append({
                '股票名称': self.stock_name,
                '代码': self.stock_code,
                '启动资金': None,
                '时间': op_time,
                '操作': op_type,
                '价格': price,
                '数量': size,
                '交易金额': cost,
                '交易佣金': comm,
                '持仓状态': None,
                '当前持仓': None,
                '收益率': f"{self.yield_rate:.2f}%" if self.yield_rate is not None else None,
                '最终资金': None
            })

        logger.write("finish parse")

    def export_to_excel(self):
        if not self.data or not self.file_path:
            logger.write(f"Error: export_to_excel: data is empty or file_path is None")
            return

        df = pd.DataFrame(self.data)
        df.to_excel(self.file_path, index=False, engine='openpyxl')

        # 使用 openpyxl 合并单元格
        wb = load_workbook(self.file_path)
        ws = wb.active

        merge_config = {
            '股票名称': 'A',
            '代码': 'B',
            '启动资金': 'C',
            '持仓状态': 'J',
            '当前持仓': 'K',
            '收益率': 'L',
            '最终资金': 'M'
        }

        # 获取所有股票代码
        stock_codes = df['代码'].unique()

        for code in stock_codes:
            # 找到该股票的所有行
            rows = [i for i, row in enumerate(ws.iter_rows(min_row=1, values_only=True)) if row[1] == code]

            if len(rows) > 1:
                start_row = rows[0] + 1  # Excel 行号从 1 开始
                end_row = rows[-1] + 1
                # 合并
                for field, col in merge_config.items():
                    ws.merge_cells(f"{col}{start_row}:{col}{end_row}")
                    # 居中对齐合并后的单元格
                    ws[f"{col}{start_row}"].alignment = Alignment(horizontal='center', vertical='center')

                ws.merge_cells(f'A{start_row}:A{end_row}')
                ws.merge_cells(f'B{start_row}:B{end_row}')

        wb.save(self.file_path)


exceler = ToExcel()
