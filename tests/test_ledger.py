import unittest
from hybrid_quant.ledger import STRATEGIES, initial_books, make_plan, replay, reconcile

A, B = STRATEGIES

class LedgerTests(unittest.TestCase):
    def setup_plan(self):
        initial = initial_books('0')
        plan = make_plan(initial, {A: {'SYN': 2}, B: {'SYN': 3}}, {'SYN': '10'}, {}, 'test')
        ids = {plan['external_orders'][0]['client_order_id']: 'fake-order'}
        return initial, plan, ids

    def test_shared_fills_conserve_positions_and_cash(self):
        initial, plan, ids = self.setup_plan()
        fills = [{'id': str(i), 'order_id': 'fake-order', 'activity_type': 'FILL',
                  'symbol': 'SYN', 'side': 'buy', 'qty': '1', 'price': '10'} for i in range(5)]
        books = replay(initial, plan, fills, ids)
        self.assertEqual(books['strategies'][A]['positions']['SYN'], 2)
        self.assertEqual(books['strategies'][B]['positions']['SYN'], 3)
        report = reconcile(books, [{'symbol': 'SYN', 'qty': '5'}], '19950', {'SYN': '10'}, '20000')
        self.assertTrue(report['ok'])
        self.assertEqual(initial['strategies'][A]['positions'], {})
        with self.assertRaises(ValueError):
            replay(initial, plan, fills + fills[:1], ids)

    def test_cannot_spend_another_strategy_cash(self):
        with self.assertRaises(ValueError):
            make_plan(initial_books('80000'), {A: {'SYN': 1001}, B: {}}, {'SYN': '10'}, {}, 'test')

    def test_equity_mismatch_is_not_silently_accepted(self):
        report = reconcile(initial_books('0'), [], '20000', {}, '20002')
        self.assertFalse(report['ok'])
        self.assertTrue(report['checks']['cash_matches'])
        self.assertFalse(report['checks']['equity_matches'])
