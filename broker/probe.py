"""Read-only account/feed probe; never logs credentials or account identifiers."""
from __future__ import annotations
import argparse
from datetime import datetime, timedelta, timezone
import json
import re
from pathlib import Path
from time import sleep

from client import AlpacaClient, BridgeError

ROOT = Path(__file__).resolve().parent


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    # On Windows an external reader can briefly block replacing a status file.
    # Preserve the atomic-write contract while tolerating that transient lock.
    for attempt in range(20):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 19:
                raise
            sleep(0.05 * (attempt + 1))


def run_probe(output, client=None):
    client = client or AlpacaClient()
    account = client.get("/v2/account")
    clock = client.get("/v2/clock")
    stamp = re.sub(r"(\.\d{6})\d+", r"\1", clock["timestamp"])
    now = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    result = {"checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "endpoint": "paper", "clock": clock,
              "account": {k: account.get(k) for k in (
                  "status", "currency", "cash", "equity", "buying_power",
                  "trading_blocked", "account_blocked", "pattern_day_trader")},
              "permissions": {}, "orders_submitted": 0}
    tests = {
        "historical_sip_minute": ("sip", "2024-01-03T14:30:00Z", "2024-01-03T15:00:00Z", "1Min"),
        "historical_sip_daily": ("sip", "2024-01-01T00:00:00Z", "2024-01-10T00:00:00Z", "1Day"),
        "historical_iex_minute": ("iex", "2024-01-03T14:30:00Z", "2024-01-03T15:00:00Z", "1Min"),
        "recent_sip_minute": ("sip", (now-timedelta(minutes=10)).isoformat(), now.isoformat(), "1Min"),
    }
    for name, (feed, start, end, timeframe) in tests.items():
        try:
            counts = {}
            for page in client.bars(["AAPL", "JPM", "SPY"], start, end, timeframe, feed):
                for symbol, rows in page.items():
                    counts[symbol] = counts.get(symbol, 0) + len(rows)
            result["permissions"][name] = {"request_ok": True, "rows": counts,
                "has_data": any(counts.values()), "feed": feed}
        except BridgeError as exc:
            result["permissions"][name] = {"request_ok": False, "error": str(exc)}
    assets = client.get("/v2/assets", {"status": "active", "asset_class": "us_equity"})
    pool_path = ROOT.parent / "us_tech500_symbols.txt"
    pool = [s.strip() for s in pool_path.read_text(encoding="utf-8").splitlines()
            if s.strip() and not s.startswith("#")]
    active = {item["symbol"]: item for item in assets}
    result["universe"] = {"size": len(pool),
        "active_tradable": sum(bool(active.get(s, {}).get("tradable")) for s in pool),
        "unavailable_symbols": [s for s in pool if not active.get(s, {}).get("tradable")],
        "note": "Current tradability is not historical universe membership"}
    result["open_orders"] = len(client.get("/v2/orders", {"status": "open"}))
    result["positions"] = len(client.get("/v2/positions"))
    write_json(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT / "outputs" / "permission_probe.json"))
    args = parser.parse_args()
    try:
        run_probe(args.output)
    except (BridgeError, OSError) as exc:
        print("PROBE_FAILED " + type(exc).__name__ + ": " + str(exc), flush=True)
        raise SystemExit(1)
