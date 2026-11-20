"""Fail-closed paper order boundary with persistent intent IDs and reconciliation.

An approved, dated order plan is required. This module does not silently turn a
historical model into a live model or infer current features from stale caches.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request

from client import AlpacaClient, APIError, BridgeError, PAPER_URL
from probe import write_json


def plan_id(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_plan(plan, gate, now):
    if gate.get("paper_enabled") is not True or not gate.get("checks") or not all(gate["checks"].values()):
        raise BridgeError("Paper activation gate has not passed")
    if gate.get("plan_sha256") != plan_id(plan):
        raise BridgeError("Activation gate is not bound to this order plan")
    if plan.get("endpoint") != PAPER_URL or plan.get("initial_capital_usd") != 10000:
        raise BridgeError("Paper-only USD 10,000 mandate required")
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    if not parse(plan["signal_at_utc"]) < parse(plan["submit_after_utc"]) <= now <= parse(plan["submit_before_utc"]):
        raise BridgeError("Signal is future-dated or order plan is outside its submission window")
    orders = plan.get("orders", [])
    if not orders or len(orders) > 30:
        raise BridgeError("Order count outside allowed range")
    ids = set()
    symbols = set()
    buy_total = 0.0
    expected = plan.get("expected_positions", {})
    for order in orders:
        if order.get("side") not in {"buy", "sell"} or order.get("type") != "limit" or order.get("time_in_force") != "opg":
            raise BridgeError("Only long-only opening limit orders supported")
        if order.get("extended_hours", False):
            raise BridgeError("Extended-hours execution refused")
        if not re.fullmatch(r"[A-Z0-9.-]+", str(order.get("symbol", ""))):
            raise BridgeError("Invalid order symbol")
        if order["symbol"] in symbols:
            raise BridgeError("Orders must be netted to one intent per symbol")
        symbols.add(order["symbol"])
        quantity = str(order.get("qty", ""))
        if not quantity.isdigit() or int(quantity) <= 0:
            raise BridgeError("Positive whole-share quantities required")
        limit = float(order["limit_price"])
        if not 0 < limit < 1e7:
            raise BridgeError("Invalid limit price")
        cid = order.get("client_order_id", "")
        if not re.fullmatch(r"us500-[a-f0-9]{24}", cid) or cid in ids:
            raise BridgeError("Missing or duplicated deterministic order ID")
        ids.add(cid)
        if order["side"] == "buy":
            buy_total += int(quantity)*limit
        elif int(quantity) > int(expected.get(order["symbol"], 0)):
            raise BridgeError("Order would short a stock")
    # Do not borrow against expected sells or the broker's default $100,000 paper balance.
    if buy_total > min(10000, float(plan["available_strategy_cash"])):
        raise BridgeError("Buy limits exceed independently tracked strategy cash")
    return orders


def find_order(client, cid):
    try:
        return client.get("/v2/orders:by_client_order_id", {"client_order_id": cid})
    except APIError as exc:
        if exc.status == 404:
            return None
        raise


def submit_once(client, order):
    """On ambiguous POST, reconcile by deterministic ID; never blindly retry an order."""
    existing = find_order(client, order["client_order_id"])
    if existing is not None:
        return existing
    request = Request(PAPER_URL + "/v2/orders", data=json.dumps(order).encode(),
                      headers=dict(client.headers, **{"Content-Type": "application/json"}), method="POST")
    client.limiter.wait()
    try:
        with client.opener.open(request, timeout=30) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, OSError):
        existing = find_order(client, order["client_order_id"])
        if existing is not None:
            return existing
        raise BridgeError("Order submission uncertain or rejected; reconciliation required, no automatic resend") from None


def execute(plan_path, gate_path, journal_path, submit=False, client=None):
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    gate = json.loads(Path(gate_path).read_text(encoding="utf-8"))
    orders = validate_plan(plan, gate, datetime.now(timezone.utc))
    client = client or AlpacaClient()
    account = client.get("/v2/account")
    if account.get("status") != "ACTIVE" or account.get("trading_blocked") or account.get("account_blocked"):
        raise BridgeError("Paper account cannot trade")
    actual = {p["symbol"]: float(p["qty"]) for p in client.get("/v2/positions")}
    expected = {s: float(q) for s, q in plan.get("expected_positions", {}).items() if float(q)}
    if actual != expected:
        raise BridgeError("Broker positions disagree with strategy ledger")
    ids = {o["client_order_id"] for o in orders}
    if any(o.get("client_order_id") not in ids for o in client.get("/v2/orders", {"status": "open"})):
        raise BridgeError("Unrelated open orders require reconciliation")
    clock = client.get("/v2/clock")
    if clock["is_open"]:
        raise BridgeError("Opening plan must be submitted before the trading session")
    opening = datetime.fromisoformat(clock["next_open"].replace("Z", "+00:00"))
    if opening.date().isoformat() != plan["execution_session"] or datetime.now(timezone.utc) >= opening - timedelta(minutes=2):
        raise BridgeError("Plan session does not match the next opening auction or its cutoff")
    if sum(float(o["qty"])*float(o["limit_price"]) for o in orders if o["side"] == "buy") > float(account["cash"]):
        raise BridgeError("Broker cash insufficient")
    journal_path = Path(journal_path)
    if journal_path.exists():
        journal = json.loads(journal_path.read_text())
        if journal["plan_sha256"] != plan_id(plan):
            raise BridgeError("Existing journal belongs to a different plan")
    else:
        journal = {"plan_sha256": plan_id(plan), "endpoint": PAPER_URL, "orders": {}, "state": "checked"}
    if not submit:
        journal["state"] = "dry_run_passed"
        write_json(journal_path, journal)
        return journal
    # Persist full intent before any network mutation. Replay uses the same order IDs.
    journal["state"] = "submitting"
    journal["intents"] = orders
    write_json(journal_path, journal)
    for order in orders:
        response = submit_once(client, order)
        journal["orders"][order["client_order_id"]] = {k: response.get(k) for k in (
            "id", "client_order_id", "symbol", "side", "qty", "status", "filled_qty", "filled_avg_price")}
        write_json(journal_path, journal)
        if response.get("status") in {"rejected", "canceled", "expired"}:
            raise BridgeError("Paper order not active; stop and reconcile remaining plan")
    journal["state"] = "submitted_pending_fills"
    write_json(journal_path, journal)
    return journal


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True)
    p.add_argument("--gate", required=True)
    p.add_argument("--journal", required=True)
    p.add_argument("--submit", action="store_true")
    a = p.parse_args()
    try:
        result = execute(a.plan, a.gate, a.journal, a.submit)
        print(result["state"])
    except BridgeError as exc:
        print("PAPER_BLOCKED " + str(exc))
        raise SystemExit(1)
