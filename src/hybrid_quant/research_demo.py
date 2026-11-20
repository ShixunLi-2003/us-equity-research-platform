"""Deterministic synthetic walk-forward integration example, not investment evidence.

Features are known at close t; labels use open t+1 to open t+2. Training
includes only labels whose exit precedes the next prediction date.
"""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from .native import ExecutionCore


def synthetic_panel(seed=7, sessions=200, symbols=8):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range('2020-01-01', periods=sessions)
    frames = []
    for number in range(symbols):
        opening = 50 * np.exp(np.cumsum(rng.normal(0, .015, sessions)))
        close = opening * np.exp(rng.normal(0, .006, sessions))
        f = pd.DataFrame({'date': dates, 'symbol': f'SYN{number:02}',
                          'open': opening, 'close': close})
        f['momentum'] = f.close.pct_change(5)
        f['volatility'] = f.close.pct_change().rolling(10).std()
        f['label'] = f.open.shift(-2) / f.open.shift(-1) - 1
        f['label_end'] = f.date.shift(-2)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def train_window(panel, day, lookback=80):
    prior = sorted(panel.loc[panel.date < day, 'date'].unique())[-lookback:]
    return panel.loc[panel.date.isin(prior) & (panel.label_end < day)].dropna()


def run(output):
    panel = synthetic_panel()
    dates = sorted(panel.date.unique())
    core = ExecutionCore()
    predictions, curve, fills, windows = [], [], [], []
    with core.account(10000, commission_bps=2, slippage_bps=5) as account:
        held = set()
        for i in range(100, len(dates) - 2):
            day, execution = dates[i], dates[i + 1]
            train = train_window(panel, day)
            current = panel.loc[panel.date == day].dropna(subset=['momentum', 'volatility'])
            model = RandomForestRegressor(n_estimators=30, max_depth=3,
                                          min_samples_leaf=10, random_state=7, n_jobs=1)
            model.fit(train[['momentum', 'volatility']], train.label)
            scores = model.predict(current[['momentum', 'volatility']])
            ranked = current[['symbol']].assign(score=scores).sort_values(
                ['score', 'symbol'], ascending=[False, True])
            target = set(ranked.head(2).symbol)
            bars = panel.loc[panel.date == execution].set_index('symbol')
            for symbol in held:
                account.mark(symbol, float(bars.loc[symbol, 'open']))
            budget = account.equity * .95 / 2
            desired = {s: int(budget / float(bars.loc[s, 'open'])) for s in target}
            # Reduce positions first; never use proceeds from unexecuted sales.
            for side in (-1, 1):
                for symbol in sorted(held | target):
                    delta = desired.get(symbol, 0) - account.quantity(symbol)
                    if delta * side > 0:
                        result = account.execute(symbol, side, abs(delta), float(bars.loc[symbol, 'open']))
                        fills.append({'date': str(pd.Timestamp(execution).date()), 'symbol': symbol,
                                      'side': side, 'quantity': abs(delta), **result})
            held = {s for s in held | target if account.quantity(s)}
            for symbol in held:
                account.mark(symbol, float(bars.loc[symbol, 'close']))
            curve.append({'date': str(pd.Timestamp(execution).date()), 'equity': account.equity})
            windows.append({'signal_date': str(pd.Timestamp(day).date()), 'train_rows': len(train),
                            'latest_label_end': str(train.label_end.max().date())})
            predictions.extend({'signal_date': str(pd.Timestamp(day).date()), **r}
                               for r in ranked.to_dict('records'))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [('equity', curve), ('fills', fills), ('predictions', predictions), ('windows', windows)]:
        pd.DataFrame(rows).to_csv(output / (name + '.csv'), index=False)
    values = [10000] + [r['equity'] for r in curve]
    report = {'data': 'synthetic', 'seed': 7, 'windows': len(windows), 'fills': len(fills),
              'initial_cash': 10000, 'return': values[-1] / 10000 - 1,
              'max_drawdown': core.max_drawdown(values),
              'commission_bps': 2, 'slippage_bps': 5,
              'claim': 'Integration demonstration only; no empirical alpha claim.'}
    (output / 'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts/demo')
    run(parser.parse_args().output)
