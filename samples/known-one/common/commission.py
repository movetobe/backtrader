from backtrader import CommInfoBase
from efinance.common.config import MarketType


class StockCommission(CommInfoBase):
    """
    股票交易佣金计算类

    继承自backtrader的CommInfoBase，用于计算股票交易中的各种费用

    Attributes:
        market_type: 市场类型，区分A股、港股等
        is_etf: 是否为ETF基金
    """

    params = (
        ('market_type', None),
        ('is_etf', False),
    )

    def __init__(self):
        super().__init__()

    def _getcommission(self, size, price, pseudoexec):
        """
        backtrader标准接口

        计算交易费用（佣金+过户费）
        size>0 : 买入
        size<0 : 卖出

        pseudoexec：是否为模拟交易，
        - True 模拟计算
        - False，真实交易
        """
        if self.p.market_type == MarketType.Hongkong:
            return self.hk_stock_connect_commission(size, price)
        else:
            return self.a_stock_commission(size, price)
        return

    def a_stock_commission(self, size, price):
        """
        A股交易费，其中的佣金费率为海通的收费
        """

        if size == 0:  # 无交易
            return 0

        # 如果是etf，仅收取交易佣金（0.3%,双向收取，最低5元）
        if self.p.is_etf:
            return max(abs(size) * price * 0.003, 5)

        # 基础佣金（0.0285%,双向收取，最低5元）
        commission = max(abs(size) * price * 0.000285, 5)

        # 过户费（双向收取0.001%）
        transfer_fee = abs(size) * price * 0.00001

        # 印花税（仅卖出收取0.05%）
        stamp_duty = 0
        if size < 0:  # 卖出
            stamp_duty = abs(size) * price * 0.0005

        return commission + transfer_fee + stamp_duty

    def hk_stock_connect_commission(self, size, price):
        """
        港股通交易费
        参考：https://www.sse.com.cn/services/hkexsc/tax/
        is_etf: 是否为ETF，ETF不收印花税
        """
        if size == 0:  # 无交易
            return 0

        amount = abs(size) * price

        # 佣金
        commission = max(amount * 0.000275, 5)

        # 印花税（双向收取0.1%，取整到元，不足一元按一元计）
        stamp_duty = 0 if self.p.is_etf else max(round(amount * 0.001), 1) if amount > 0 else 1

        # 交易费（双向收取0.00565%，四舍五入至小数点后两位）
        trading_fee = round(amount * 0.0000565, 2)

        # 证监会交易征费（双向收取0.0027%，四舍五入至小数点后两位）
        levy = round(amount * 0.000027, 2)

        # 会财局交易征费（双向收取0.00015%，四舍五入至小数点后两位）
        accounting_levy = round(amount * 0.0000015, 2)

        # 股份交收费（双向收取0.0042%，四舍五入至小数点后两位）
        system_fee = round(amount * 0.000042, 2)

        # todo 证券组合费，每日缴纳证券组合费, 不高于港币500亿元时年费率0.008%

        return commission + stamp_duty + trading_fee + levy + accounting_levy + system_fee
