import unittest
import pandas as pd
from hybrid_quant.research_demo import synthetic_panel, train_window

class TemporalTests(unittest.TestCase):
    def test_training_excludes_unrealized_labels(self):
        p = synthetic_panel()
        day = pd.Timestamp('2020-07-01')
        train = train_window(p, day)
        self.assertGreater(len(train), 0)
        self.assertTrue((train.label_end < day).all())

    def test_future_price_changes_do_not_change_past_features(self):
        p = synthetic_panel()
        q = p.copy()
        cutoff = pd.Timestamp('2020-06-01')
        q.loc[q.date > cutoff, 'close'] *= 100
        recomputed = q.groupby('symbol').close.transform(lambda s: s.pct_change(5))
        pd.testing.assert_series_equal(p.loc[p.date <= cutoff, 'momentum'],
            recomputed.loc[q.date <= cutoff], check_names=False)
