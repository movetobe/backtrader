import unittest
from backtrader import CommInfoBase
from efinance.common.config import MarketType
from commission import *


class TestStockCommission(unittest.TestCase):
    def setUp(self):
        self.commission = StockCommission()

    def test_a_stock_buy_commission(self):
        """测试A股买入佣金计算（非ETF）"""
        self.commission.p.market_type = MarketType.A_stock
        self.commission.p.is_etf = False

        # 测试佣金最低5元
        # commission = self.commission.a_stock_commission(100, 10)  # 1000元 * 0.0285% = 0.285元 < 5元
        # self.assertAlmostEqual(commission, 5.1, places=2)  # 5元佣金 + 0.1元过户费

        # 测试佣金超过最低限额，卖出
        commission = self.commission.a_stock_commission(-500, 22.49)
        self.assertAlmostEqual(commission, 5 + 5.62, places=2)

    def test_a_stock_sell_commission(self):
        """测试A股卖出佣金计算（非ETF）"""
        self.commission.p.market_type = MarketType.A_stock
        self.commission.p.is_etf = False

        # 测试包含印花税
        commission = self.commission.a_stock_commission(-500, 22.49)  # 卖出100000元
        expected = 5 + 5.62  # 5佣金+5.62印花税
        self.assertAlmostEqual(commission, expected, places=2)

    def test_a_stock_etf_commission(self):
        """测试A股ETF佣金计算"""
        self.commission.p.market_type = MarketType.A_stock
        self.commission.p.is_etf = True

        # 测试ETF最低佣金
        commission = self.commission.a_stock_commission(100, 10)  # 1000元 * 0.3% = 3元 < 5元
        self.assertEqual(commission, 5)

        # 测试ETF佣金超过最低限额
        commission = self.commission.a_stock_commission(1000, 10)  # 10000元 * 0.3% = 30元
        self.assertEqual(commission, 30)

    def test_hk_stock_connect_commission(self):
        """测试港股通佣金计算（非ETF）"""
        self.commission.p.market_type = MarketType.Hongkong
        self.commission.p.is_etf = False

        # 测试最低佣金
        commission = self.commission.hk_stock_connect_commission(100, 1)  # 100港元
        # 佣金: max(100*0.0275%, 5) = 5
        # 印花税: max(round(100*0.1%), 1) = 1
        # 其他费用约 0.00565% + 0.0027% + 0.00015% + 0.0042% = 0.0127% → 0.01港元
        expected = 5 + 1 + 0.01 + 0.01 + 0.0 + 0.01  # 四舍五入后
        self.assertAlmostEqual(commission, expected, places=2)

        # 测试大额交易
        commission = self.commission.hk_stock_connect_commission(10000, 10)  # 100000港元
        # 佣金: 100000*0.0275% = 27.5
        # 印花税: round(100000*0.1%) = 100
        # 其他费用: 5.65 + 2.7 + 0.15 + 4.2 ≈ 12.7
        expected = 27.5 + 100 + 5.65 + 2.7 + 0.15 + 4.2
        self.assertAlmostEqual(commission, expected, places=2)

    def test_hk_stock_connect_etf_commission(self):
        """测试港股通ETF佣金计算"""
        self.commission.p.market_type = MarketType.Hongkong
        self.commission.p.is_etf = True

        # ETF不收印花税
        commission = self.commission.hk_stock_connect_commission(10000, 10)  # 100000港元
        expected = 27.5 + 0 + 5.65 + 2.7 + 0.15 + 4.2  # 无印花税
        self.assertAlmostEqual(commission, expected, places=2)

    def test_zero_quantity(self):
        """测试零数量交易"""
        self.commission.p.market_type = MarketType.A_stock
        commission = self.commission.a_stock_commission(0, 10)
        self.assertEqual(commission, 0)

        self.commission.p.market_type = MarketType.Hongkong
        commission = self.commission.hk_stock_connect_commission(0, 10)
        self.assertEqual(commission, 0)


if __name__ == '__main__':
    unittest.main()
