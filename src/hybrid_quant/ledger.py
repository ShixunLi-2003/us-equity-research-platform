"""Deterministic, order-neutral virtual books for one Alpaca Paper account.

Pure planning and replay; importing this file cannot submit an order. Broker
FILL activities, not order status estimates, are the source of executed shares.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

STRATEGIES = ('deep_asset_pricing_mlp', 'extra_trees')
STARTING_CASH = Decimal('10000')


def parse_broker_timestamp(value):
    """Parse Alpaca timestamps, including its nine-digit fractional seconds."""
    normalized = re.sub(r'\.(\d+)(?=Z|[+-]\d{2}:\d{2}$)',
                        lambda match: '.' + (match.group(1) + '000000')[:6], value)
    return datetime.fromisoformat(normalized.replace('Z', '+00:00'))


def dec(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('Invalid amount') from exc
    if not number.is_finite():
        raise ValueError('Non-finite amount')
    return number


def shares(value):
    number = dec(value)
    if number != number.to_integral_value():
        raise ValueError('Only whole-share virtual books supported')
    return int(number)


def initial_books(unallocated_cash):
    other = dec(unallocated_cash)
    if other < 0:
        raise ValueError('Broker cash below pilot allocation')
    return {'unallocated_cash': str(other),
            'strategies': {s: {'cash': str(STARTING_CASH), 'positions': {}}
                           for s in STRATEGIES}}


def _holdings(books, strategy, symbol):
    return shares(books['strategies'][strategy]['positions'].get(symbol, 0))


def _apply_fill(books, strategy, symbol, signed_qty, price, fee=Decimal(0)):
    account = books['strategies'][strategy]
    price, fee = dec(price), dec(fee)
    if price <= 0 or fee < 0:
        raise ValueError('Invalid execution price or fee')
    qty = _holdings(books, strategy, symbol) + signed_qty
    cash = dec(account['cash']) - price * signed_qty - fee
    if qty < 0 or cash < 0:
        raise ValueError('Virtual short or cash deficit: ' + strategy)
    if qty:
        account['positions'][symbol] = qty
    else:
        account['positions'].pop(symbol, None)
    account['cash'] = str(cash)


def make_plan(books, intents, limit_prices, internal_prices, key):
    """Net two strategies, crossing opposing intents internally at an agreed mark.

    Returned external orders each contain the *remaining* strategy allocation.
    No internal transfer is applied until the immutable plan is replayed.
    """
    if not isinstance(key, str) or not key:
        raise ValueError('Plan key required')
    if set(intents) != set(STRATEGIES):
        raise ValueError('Both strategy intents required')
    symbols = sorted(set().union(*(set(intents[s]) for s in STRATEGIES)))
    if not symbols:
        raise ValueError('Empty strategy intents')
    if any(s not in limit_prices or dec(limit_prices[s]) <= 0 for s in symbols):
        raise ValueError('Every traded symbol needs a positive limit')
    transfers, external = [], []
    for strategy in STRATEGIES:
        reserve = Decimal(0)
        for symbol, qty_raw in intents[strategy].items():
            qty = shares(qty_raw)
            if qty < 0 and -qty > _holdings(books, strategy, symbol):
                raise ValueError('Intent sells another strategy holding: ' + strategy)
            if qty > 0:
                if symbol not in limit_prices or dec(limit_prices[symbol]) <= 0:
                    raise ValueError('Missing positive buy limit: ' + symbol)
                reserve += qty * dec(limit_prices[symbol])
        if reserve > dec(books['strategies'][strategy]['cash']):
            # Conservative: proceeds of sells are not available to fund buys.
            raise ValueError('Buy limit exceeds isolated strategy cash: ' + strategy)
    for symbol in symbols:
        remaining = {s: shares(intents[s].get(symbol, 0)) for s in STRATEGIES}
        sellers = [s for s in STRATEGIES if remaining[s] < 0]
        buyers = [s for s in STRATEGIES if remaining[s] > 0]
        if buyers and sellers:
            price = dec(internal_prices.get(symbol, 0))
            if price <= 0:
                raise ValueError('Internal crossing needs contemporaneous price: ' + symbol)
            for seller in sellers:
                for buyer in buyers:
                    qty = min(-remaining[seller], remaining[buyer])
                    if qty:
                        if price != dec(limit_prices[symbol]):
                            # A single symbol limit is both buyer maximum and
                            # seller minimum for an internal cross. A different
                            # price would advantage one book at the other's cost.
                            raise ValueError('Internal cross must use shared limit mark')
                        transfers.append({'symbol': symbol, 'seller': seller, 'buyer': buyer,
                                          'qty': qty, 'price': str(price)})
                        remaining[seller] += qty
                        remaining[buyer] -= qty
        net = sum(remaining.values())
        if net:
            side = 'buy' if net > 0 else 'sell'
            allocations = {s: abs(q) for s, q in remaining.items() if q and (q > 0) == (net > 0)}
            identity = hashlib.sha256((key + '|' + symbol + '|' + side).encode()).hexdigest()[:24]
            external.append({'symbol': symbol, 'side': side, 'qty': abs(net),
                             'allocations': allocations, 'limit_price': str(dec(limit_prices[symbol])),
                             'client_order_id': 'us500-' + identity})
    return {'key': key, 'intents': intents, 'transfers': transfers,
            'external_orders': external, 'paper_only': True}


def _fair_cumulative(quantity, allocations):
    """Monotone highest-averages apportionment for partial fills."""
    if quantity < 0 or quantity > sum(allocations.values()):
        raise ValueError('Fill exceeds planned shares')
    assigned = {s: 0 for s in allocations}
    for _ in range(quantity):
        choices = [s for s in assigned if assigned[s] < allocations[s]]
        chosen = sorted(choices, key=lambda s: (-Decimal(allocations[s]) /
                                                Decimal(assigned[s] + 1), s))[0]
        assigned[chosen] += 1
    return assigned


def replay(initial, plan, activities, order_ids):
    """Rebuild both books from an immutable plan and unique broker FILL events."""
    books = json.loads(json.dumps(initial))
    for transfer in plan['transfers']:
        seller, buyer = transfer['seller'], transfer['buyer']
        symbol, qty, price = transfer['symbol'], shares(transfer['qty']), dec(transfer['price'])
        _apply_fill(books, seller, symbol, -qty, price)
        _apply_fill(books, buyer, symbol, qty, price)
    by_order = {}
    for order in plan['external_orders']:
        cid = order['client_order_id']
        oid = order_ids.get(cid)
        if not oid or oid in by_order:
            raise ValueError('Unknown or duplicate broker order ID')
        by_order[oid] = order
    seen, used, allocated = set(), defaultdict(int), defaultdict(dict)
    for event in sorted(activities, key=lambda e: (e.get('transaction_time', ''), e.get('id', ''))):
        event_id = event.get('id')
        if not event_id or event_id in seen:
            raise ValueError('Missing or duplicate fill activity ID')
        seen.add(event_id)
        oid = event.get('order_id')
        if oid not in by_order or event.get('activity_type') != 'FILL':
            raise ValueError('Unknown order or non-fill account activity')
        order = by_order[oid]
        if event.get('symbol') != order['symbol'] or event.get('side') != order['side']:
            raise ValueError('Fill symbol/side differs from intent')
        qty, price = shares(event.get('qty')), dec(event.get('price'))
        if qty <= 0 or price <= 0:
            raise ValueError('Invalid fill quantity or price')
        order_type = order.get('order_type', 'limit')
        if order_type == 'market':
            if order['side'] != 'buy' or order.get('time_in_force') != 'opg':
                raise ValueError('Only Paper MOO buys are supported')
            # limit_price is a conservative planning *reserve* for MOO, not
            # an execution cap. Cash and holdings are still checked below.
        elif order_type == 'limit':
            if order['side'] == 'buy' and price > dec(order['limit_price']):
                raise ValueError('Buy fill above limit')
            if order['side'] == 'sell' and price < dec(order['limit_price']):
                raise ValueError('Sell fill below limit')
        else:
            raise ValueError('Unknown broker order type in virtual replay')
        used[oid] += qty
        current = _fair_cumulative(used[oid], order['allocations'])
        previous = allocated[oid]
        for strategy, cumulative in current.items():
            increment = cumulative - previous.get(strategy, 0)
            if increment < 0:
                raise ValueError('Non-monotone partial fill allocation')
            if increment:
                signed = increment if order['side'] == 'buy' else -increment
                fee = (event.get('paper_fee_by_strategy') or {}).get(
                    strategy, event.get('paper_fee', 0))
                _apply_fill(books, strategy, order['symbol'], signed, price,
                            dec(fee))
        allocated[oid] = current
    return books


def replay_many(initial, entries):
    """Replay settled daily plans in order; reject cross-day duplicated fills."""
    books, seen_keys, seen_orders, seen_activities = initial, set(), set(), set()
    for item in entries:
        plan = item['plan']
        if plan['key'] in seen_keys:
            raise ValueError('Repeated strategy plan key')
        seen_keys.add(plan['key'])
        if item.get('settled') is not True:
            raise ValueError('Unsettled plan cannot be followed by another plan')
        ids = item['order_ids']
        for oid in ids.values():
            if oid in seen_orders:
                raise ValueError('Broker order ID reused across plans')
            seen_orders.add(oid)
        for activity in item['activities']:
            if activity['id'] in seen_activities:
                raise ValueError('Broker activity ID reused across plans')
            seen_activities.add(activity['id'])
        books = replay(books, plan, item['activities'], ids)
    return books


def traded_notional(entries):
    """Gross executed notional per model, including marked internal crosses."""
    totals = {s: Decimal(0) for s in STRATEGIES}
    for entry in entries:
        plan, ids = entry['plan'], entry['order_ids']
        for transfer in plan['transfers']:
            value = shares(transfer['qty']) * dec(transfer['price'])
            totals[transfer['seller']] += value
            totals[transfer['buyer']] += value
        by_order = {ids[o['client_order_id']]: o for o in plan['external_orders']}
        used, assigned = defaultdict(int), defaultdict(dict)
        for event in sorted(entry['activities'],
                            key=lambda e: (e.get('transaction_time', ''), e.get('id', ''))):
            oid = event['order_id']
            if oid not in by_order:
                raise ValueError('Unowned activity in turnover calculation')
            order = by_order[oid]
            used[oid] += shares(event['qty'])
            current = _fair_cumulative(used[oid], order['allocations'])
            for strategy, quantity in current.items():
                increment = quantity - assigned[oid].get(strategy, 0)
                if increment < 0:
                    raise ValueError('Non-monotone turnover allocation')
                totals[strategy] += increment * dec(event['price'])
            assigned[oid] = current
    return {s: str(value) for s, value in totals.items()}


def fetch_order_fills(client, order_id):
    """Fetch every FILL activity page for a Paper order ID."""
    fills, token, seen = [], None, set()
    for _ in range(100):
        params = {'order_id': order_id, 'page_size': 100}
        if token:
            params['page_token'] = token
        page = client.get('/v2/account/activities/FILL', params)
        if not isinstance(page, list):
            raise ValueError('Alpaca FILL endpoint returned non-list')
        for activity in page:
            if activity.get('order_id') != order_id:
                raise ValueError('FILL endpoint returned unrelated order')
            if activity.get('id') in seen:
                raise ValueError('Repeated FILL activity')
            seen.add(activity.get('id'))
            fills.append(activity)
        if len(page) < 100:
            return fills
        token = page[-1].get('id')
        if not token:
            raise ValueError('Missing FILL pagination token')
    raise ValueError('Too many FILL pages; manual audit needed')


def fetch_account_activities(client, after):
    """Read *all* post-baseline activities to detect foreign fills and cash events."""
    activities, token, seen = [], None, set()
    for _ in range(1000):
        params = {'after': after, 'page_size': 100, 'direction': 'asc'}
        if token:
            params['page_token'] = token
        page = client.get('/v2/account/activities', params)
        if not isinstance(page, list):
            raise ValueError('Alpaca activities endpoint returned non-list')
        for item in page:
            identity = item.get('id')
            if not identity or identity in seen:
                raise ValueError('Missing or duplicate account activity ID')
            seen.add(identity)
            activities.append(item)
        if len(page) < 100:
            return activities
        token = page[-1]['id']
    raise ValueError('Too many activity pages; manual audit needed')


def attribute_paper_fees(entries, account_activities):
    """Attribute an aggregate CAT fee to verified owned fills, cent-exactly."""
    fills = {event['id']: (entry, event, order)
             for entry in entries for order in entry['plan']['external_orders']
             for event in entry['activities']
             if event.get('order_id') == entry['order_ids'][order['client_order_id']]}
    if len(fills) != sum(len(entry['activities']) for entry in entries):
        raise ValueError('Duplicate or unowned Paper fill activity')
    seen, fees = set(), {}
    for activity in account_activities:
        identity = activity.get('id')
        if identity in fills:
            if activity.get('activity_type') != 'FILL':
                raise ValueError('Owned activity is not a FILL')
            seen.add(identity)
            continue
        if (activity.get('activity_type') != 'FEE' or
                activity.get('activity_sub_type') != 'CAT' or
                activity.get('currency') != 'USD' or
                activity.get('status') != 'executed'):
            raise ValueError('Unattributed post-baseline broker activity')
        day = activity.get('date')
        description = activity.get('description', '')
        match = re.fullmatch(r'CAT fee for proceed of (\d+) trades on (\d{4}-\d{2}-\d{2}) by [A-Za-z0-9]+',
                             description)
        amount = -dec(activity.get('net_amount'))
        if (not match or match.group(2) != day or
                amount <= 0 or amount > Decimal('1') or day in fees or
                amount % Decimal('0.01') != 0):
            raise ValueError('Ambiguous Paper CAT fee')
        matches = [(fid, row) for fid, row in fills.items()
                   if parse_broker_timestamp(row[1]['transaction_time'])
                   .astimezone(ZoneInfo('America/New_York')).date().isoformat() == day]
        if not matches or int(match.group(1)) != len(matches):
            raise ValueError('CAT fee trade count differs from owned FILL activities')
        matches.sort(key=lambda item: (item[1][1]['transaction_time'], item[0]))
        used, allocated = defaultdict(int), defaultdict(dict)
        notionals, first_fill = defaultdict(Decimal), {}
        for fill_id, (_, event, order) in matches:
            oid = event['order_id']
            used[oid] += shares(event['qty'])
            current = _fair_cumulative(used[oid], order['allocations'])
            previous = allocated[oid]
            for strategy, cumulative in current.items():
                increment = cumulative - previous.get(strategy, 0)
                if increment < 0:
                    raise ValueError('Non-monotone CAT fee fill allocation')
                if increment:
                    notionals[strategy] += increment * dec(event['price'])
                    first_fill.setdefault(strategy, fill_id)
            allocated[oid] = current
        if not notionals or any(value <= 0 for value in notionals.values()):
            raise ValueError('CAT fee has no positive owned traded notional')
        cents = int(amount / Decimal('0.01'))
        total = sum(notionals.values(), Decimal(0))
        ideal = {strategy: cents * value / total
                 for strategy, value in notionals.items()}
        assigned = {strategy: int(value.to_integral_value(rounding=ROUND_DOWN))
                    for strategy, value in ideal.items()}
        remaining = cents - sum(assigned.values())
        for strategy in sorted(ideal, key=lambda s: (-(ideal[s] - assigned[s]), s))[:remaining]:
            assigned[strategy] += 1
        fee_allocations = {}
        for strategy, count in assigned.items():
            if not count:
                continue
            fill_id = first_fill[strategy]
            portion = str(Decimal(count) * Decimal('0.01'))
            fill_event = fills[fill_id][1]
            fill_event.setdefault('paper_fee_by_strategy', {})[strategy] = portion
            fee_allocations[strategy] = {'fill_activity_id': fill_id, 'amount': portion}
        fees[day] = {'fee_activity_id': identity, 'amount': str(amount),
                     'fill_activity_ids': [fid for fid, _ in matches],
                     'allocation_method': 'traded_notional_largest_remainder_cent',
                     'allocations': fee_allocations}
        if len(fee_allocations) == 1:
            strategy = next(iter(fee_allocations))
            fees[day]['strategy'] = strategy
            fees[day]['fill_activity_id'] = fee_allocations[strategy]['fill_activity_id']
    if seen != set(fills):
        raise ValueError('Unattributed post-baseline broker activity')
    return fees


def broker_entry(client, plan, order_ids):
    activities, settled, order_outcomes = [], True, []
    terminal = {'filled', 'canceled', 'expired', 'rejected'}
    for order in plan['external_orders']:
        cid, oid = order['client_order_id'], order_ids.get(order['client_order_id'])
        if not oid:
            raise ValueError('Missing broker order ID for plan')
        response = client.get('/v2/orders/' + oid)
        if (response.get('id') != oid or response.get('client_order_id') != cid or
                response.get('symbol') != order['symbol'] or response.get('side') != order['side']):
            raise ValueError('Broker order differs from planned order')
        if shares(response.get('qty')) != order['qty']:
            raise ValueError('Broker order size differs from planned order')
        if order.get('order_type') == 'market' and (
                response.get('type') != 'market' or response.get('time_in_force') != 'opg'):
            raise ValueError('Broker order is not the planned MOO order')
        fills = fetch_order_fills(client, oid)
        filled_qty = shares(response.get('filled_qty', 0))
        if sum(shares(e['qty']) for e in fills) != filled_qty:
            raise ValueError('Broker filled quantity differs from FILL activities')
        if filled_qty > order['qty']:
            raise ValueError('Broker fill exceeds planned order quantity')
        allocated = _fair_cumulative(filled_qty, order['allocations'])
        order_outcomes.append({
            'symbol': order['symbol'], 'side': order['side'],
            'client_order_id': cid, 'broker_order_id': oid,
            'order_type': response.get('type'), 'time_in_force': response.get('time_in_force'),
            'status': response.get('status'),
            'requested_qty': order['qty'], 'filled_qty': filled_qty,
            'unfilled_qty': order['qty'] - filled_qty,
            'model_requested_qty': dict(order['allocations']),
            'model_filled_qty': allocated,
            'model_unfilled_qty': {s: q - allocated[s] for s, q in order['allocations'].items()},
            'submitted_at': response.get('submitted_at'),
            'filled_at': response.get('filled_at'),
            'expired_at': response.get('expired_at'),
            'canceled_at': response.get('canceled_at'),
            'failed_at': response.get('failed_at'),
            'rejected_at': response.get('rejected_at'),
            'fill_activity_ids': [e['id'] for e in fills],
        })
        activities.extend(fills)
        settled &= response.get('status') in terminal
    return {'plan': plan, 'order_ids': order_ids, 'activities': activities,
            'orders': order_outcomes, 'settled': settled}


def reconcile(books, broker_positions, broker_cash, marks=None, broker_equity=None,
              cash_tolerance=Decimal('0.02'), equity_tolerance=Decimal('1.00')):
    expected = defaultdict(int)
    for state in books['strategies'].values():
        for symbol, qty in state['positions'].items():
            expected[symbol] += shares(qty)
    actual = {row['symbol']: shares(row['qty']) for row in broker_positions
              if shares(row['qty']) != 0}
    expected = {s: q for s, q in expected.items() if q}
    virtual_cash = sum((dec(state['cash']) for state in books['strategies'].values()), Decimal(0))
    accounted_cash = virtual_cash + dec(books['unallocated_cash'])
    cash_difference = dec(broker_cash) - accounted_cash
    checks = {'positions_match': actual == expected,
              'cash_matches': abs(cash_difference) <= dec(cash_tolerance)}
    nav = {}
    if marks is not None:
        for strategy, state in books['strategies'].items():
            missing = set(state['positions']) - set(marks)
            if missing:
                raise ValueError('Missing strategy marks: ' + ','.join(sorted(missing)))
            nav[strategy] = dec(state['cash']) + sum(
                (shares(qty) * dec(marks[symbol]) for symbol, qty in state['positions'].items()), Decimal(0))
    if broker_equity is not None:
        if not nav:
            raise ValueError('NAV marks required for equity reconciliation')
        accounted_equity = sum(nav.values(), Decimal(0)) + dec(books['unallocated_cash'])
        checks['equity_matches'] = abs(dec(broker_equity) - accounted_equity) <= dec(equity_tolerance)
    return {'ok': all(checks.values()), 'checks': checks,
            'expected_positions': expected, 'actual_positions': actual,
            'cash_difference': str(cash_difference),
            'strategy_nav': {s: str(value) for s, value in nav.items()},
            'strategy_return': {s: str(value / STARTING_CASH - 1) for s, value in nav.items()}}
