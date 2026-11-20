import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hybrid_quant import ExecutionCore, OrderRejected


class NativeCoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = ExecutionCore()

    def test_quantity_and_risk(self):
        self.assertEqual(self.core.order_quantity(10000, 250, 1, 1.0), 40)
        self.assertEqual(self.core.pretrade_check(10000, 250, 40, 0, 10000, 10000, 1), 0)
        self.assertEqual(self.core.pretrade_check(1000, 250, 40, 0, 10000, 10000, 1), 2)

    def test_round_trip_costs_reduce_profit(self):
        raw = (110 - 100) * 10
        self.assertLess(self.core.round_trip_pnl(100, 110, 10), raw)

    def test_execution_primitives_are_exposed(self):
        self.assertGreater(self.core.slipped_price(100, 1, 2), 100)
        self.assertGreater(self.core.transaction_cost(10000, -1, 1, 0, 2), 0)
        self.assertAlmostEqual(self.core.max_drawdown([100, 120, 90, 110]), -0.25)

    def test_stateful_account_buy_mark_and_sell(self):
        with self.core.account(10000, commission_bps=1, slippage_bps=2) as account:
            buy = account.execute("AAPL", 1, 10, 100)
            self.assertEqual(account.quantity("AAPL"), 10)
            self.assertLess(account.cash, 9000)
            self.assertGreater(buy["fill_price"], 100)
            account.mark("AAPL", 110)
            self.assertGreater(account.equity, 10090)
            self.assertGreater(account.gross_exposure, 1090)
            sell = account.execute("AAPL", -1, 10, 110)
            self.assertEqual(account.quantity("AAPL"), 0)
            self.assertGreater(sell["realized_pnl"], 90)
            self.assertAlmostEqual(account.equity, account.cash)
            self.assertGreater(account.total_fees, 0)

    def test_stateful_account_rejects_invalid_orders(self):
        with self.core.account(1000) as account:
            with self.assertRaises(OrderRejected) as cash_error:
                account.execute("AAPL", 1, 20, 100)
            self.assertEqual(cash_error.exception.code, 2)
            with self.assertRaises(OrderRejected) as position_error:
                account.execute("AAPL", -1, 1, 100)
            self.assertEqual(position_error.exception.code, 3)

    def test_limit_order_partial_fill_cancel_and_halt(self):
        with self.core.account(10000, slippage_bps=0) as account:
            order_id = account.submit_limit("AAPL", 1, 90, 101)
            fills = account.process_bar("AAPL", 100, 102, 99, 101, 1000, 0.05)
            self.assertEqual(sum(fill["quantity"] for fill in fills), 50)
            self.assertEqual(account.order_remaining(order_id), 40)
            self.assertEqual(account.quantity("AAPL"), 50)
            self.assertEqual(account.cancel(order_id), 40)
            self.assertEqual(account.order_remaining(order_id), 0)
            account.set_tradable("AAPL", False)
            with self.assertRaises(OrderRejected) as halted:
                account.execute("AAPL", 1, 1, 100)
            self.assertEqual(halted.exception.code, 5)
            account.set_tradable("AAPL", True)

    def test_split_and_dividend_adjust_account_and_orders(self):
        with self.core.account(10000, commission_bps=0, slippage_bps=0) as account:
            account.execute("AAPL", 1, 3, 100)
            order_id = account.submit_limit("AAPL", -1, 1, 120)
            before = account.cash
            cash_in_lieu = account.apply_split("AAPL", 1.5, 70)
            self.assertEqual(account.quantity("AAPL"), 4)
            self.assertAlmostEqual(cash_in_lieu, 35.0)
            self.assertEqual(account.order_remaining(order_id), 1)
            self.assertAlmostEqual(account.average_cost("AAPL"), 100 / 1.5)
            dividend = account.apply_dividend("AAPL", 1.0, 10.0)
            self.assertAlmostEqual(dividend, 3.996)
            self.assertAlmostEqual(account.cash, before + 35.0 + 3.996)


if __name__ == "__main__":
    unittest.main()
