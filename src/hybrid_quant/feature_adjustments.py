"""Causal share-unit normalization; raw execution prices remain untouched.

Features use split/stock-dividend normalized prices (not cash-dividend total-return
prices). Labels measure gross economic open-to-open return including distributions.
Complex corporate actions and ambiguous same-day cash/share events invalidate labels.
"""
import numpy as np
import pandas as pd

FEATURE_CHAIN_VERSION = 3


def events_for(actions, symbol):
    seen, result = set(), []
    for kind, events in (actions or {}).items():
        for event in events:
            if event.get('symbol') != symbol:
                continue
            key = (kind, event.get('id') or repr(sorted(event.items())))
            if key in seen:
                continue
            seen.add(key)
            date = pd.Timestamp(event.get('ex_date', event.get('effective_date', event.get('process_date'))))
            if not pd.isna(date):
                result.append((date, kind, event))
    return sorted(result, key=lambda item: (item[0], item[1]))


def share_ratio(kind, event):
    if kind in ('forward_splits', 'reverse_splits'):
        value = float(event['new_rate']) / float(event['old_rate'])
    elif kind == 'stock_dividends':
        value = float(event['rate'])
        if value < 1:
            raise ValueError('Stock dividend rate must be a total share multiplier')
    else:
        return 1.
    if not np.isfinite(value) or value <= 0:
        raise ValueError('Invalid share adjustment ratio')
    return value


def normalized_minutes(minutes, symbol, actions):
    result = minutes.copy()
    days = pd.to_datetime(result.session_date)
    scale = np.ones(len(result))
    for date, kind, event in events_for(actions, symbol):
        ratio = share_ratio(kind, event)
        if ratio != 1:
            scale[days.ge(date)] *= ratio
    for name in ('open', 'high', 'low', 'close', 'vwap', 'bid', 'ask'):
        if name in result:
            result[name] = result[name] * scale
    if 'volume' in result:
        result['volume'] = result.volume / scale
    return result


def economic_labels(daily, symbol, actions):
    """Use actual opens at both ends; events on entry ex-date are not entitlements."""
    result = daily.copy()
    entry, exit_ = result.open.shift(-1), result.open.shift(-2)
    opening_valid = result.opening_bar_available.shift(-1).fillna(False) & result.opening_bar_available.shift(-2).fillna(False)
    valid = opening_valid & entry.gt(0) & exit_.gt(0)
    entry_dates, exit_dates = result.trade_date.shift(-1), result.trade_date.shift(-2)
    ratios = pd.Series(1., index=result.index)
    cash = pd.Series(0., index=result.index)
    issues = pd.Series(False, index=result.index)
    events = events_for(actions, symbol)
    share_dates = {d for d,k,e in events if share_ratio(k,e) != 1}
    for date, kind, event in events:
        mask = entry_dates.lt(date) & exit_dates.ge(date)
        if kind in ('forward_splits', 'reverse_splits', 'stock_dividends'):
            ratios.loc[mask] *= share_ratio(kind, event)
        elif kind == 'cash_dividends':
            rate = float(event['rate'])
            if date in share_dates or not np.isfinite(rate) or rate < 0:
                issues.loc[mask] = True
            else:
                cash.loc[mask] += ratios.loc[mask] * rate
        elif kind not in ('name_changes', 'unit_splits'):
            issues.loc[mask] = True
        # Identity changes need separate security-master review, not a guessed price factor.
        elif kind == 'name_changes' and event.get('old_cusip') != event.get('new_cusip'):
            issues.loc[mask] = True
    result['forward_return_price_only'] = result.forward_return
    result['label_cash_distribution'] = cash
    result['label_share_multiplier'] = ratios
    result['label_action_review_required'] = issues
    result['forward_return'] = ((exit_ * ratios + cash) / entry - 1).where(valid & ~issues)
    result['feature_chain_version'] = FEATURE_CHAIN_VERSION
    return result
