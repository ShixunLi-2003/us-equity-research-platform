import sys
from pathlib import Path
import unittest
import pandas as pd
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hybrid_quant.feature_adjustments import normalized_minutes, economic_labels


class FeatureAdjustmentTests(unittest.TestCase):
    def test_stock_dividend_is_forward_only_and_preserves_notional(self):
        frame = pd.DataFrame({'session_date':['2024-01-01','2024-01-02'],
            'close':[100., 50.], 'vwap':[100.,50.], 'volume':[10.,20.]})
        actions = {'stock_dividends':[{'symbol':'A','ex_date':'2024-01-02','rate':2.}]}
        adj = normalized_minutes(frame, 'A', actions)
        np.testing.assert_allclose(adj.close, [100.,100.])
        np.testing.assert_allclose(adj.volume, [10.,10.])
        np.testing.assert_allclose(adj.close*adj.volume, frame.close*frame.volume)
        pd.testing.assert_frame_equal(adj.iloc[:1], normalized_minutes(frame.iloc[:1], 'A', actions))
        self.assertEqual(frame.close.iloc[-1], 50.)

    def test_dividend_label_entry_excluded_exit_included(self):
        dates = pd.bdate_range('2024-01-01', periods=4)
        daily = pd.DataFrame({'trade_date':dates,'open':[10.,10.,9.,9.],
            'opening_bar_available':True, 'forward_return':[-.1,0.,np.nan,np.nan]})
        actions={'cash_dividends':[{'symbol':'A','ex_date':str(dates[2].date()),'rate':1.}]}
        result=economic_labels(daily,'A',actions)
        self.assertAlmostEqual(result.forward_return.iloc[0],0.)
        self.assertAlmostEqual(result.forward_return.iloc[1],0.)
        self.assertEqual(result.label_cash_distribution.iloc[1],0.)
        daily.loc[2,'opening_bar_available']=False
        result=economic_labels(daily,'A',actions)
        self.assertTrue(result.forward_return.iloc[:2].isna().all())

    def test_stock_label_and_duplicate_action(self):
        dates=pd.bdate_range('2024-01-01',periods=3)
        daily=pd.DataFrame({'trade_date':dates,'open':[10.,10.,5.],
            'opening_bar_available':True,'forward_return':[-.5,np.nan,np.nan]})
        event={'symbol':'A','ex_date':str(dates[2].date()),'rate':2.,'id':'same'}
        result=economic_labels(daily,'A',{'stock_dividends':[event,event]})
        self.assertEqual(result.forward_return.iloc[0],0.)
        self.assertEqual(result.label_share_multiplier.iloc[0],2.)

    def test_ambiguous_same_day_cash_and_split_invalidated(self):
        dates=pd.bdate_range('2024-01-01',periods=3)
        daily=pd.DataFrame({'trade_date':dates,'open':[10.,10.,5.],
            'opening_bar_available':True,'forward_return':[-.5,np.nan,np.nan]})
        event={'symbol':'A','ex_date':str(dates[2].date())}
        actions={'stock_dividends':[dict(event,rate=2.)], 'cash_dividends':[dict(event,rate=1.)]}
        result=economic_labels(daily,'A',actions)
        self.assertTrue(result.label_action_review_required.iloc[0])
        self.assertTrue(pd.isna(result.forward_return.iloc[0]))


if __name__=='__main__': unittest.main()
