# US Equity Research & Execution Platform

A Python/C++ portfolio project distilled from a US-equity research and paper-trading system. The source project studied a nominal 500-stock universe using minute bars, daily prices, corporate actions and SEC financial disclosures. This repository packages a reproducible offline research-to-execution example and the native account engine.

**Status:** offline engineering demonstrator. Historical research and broker operations are documented separately; this release does not claim a profitable strategy or production readiness.

## Quick start

Python 3.9+ and a C++14 compiler are required. Windows builds prefer Visual Studio C++ x64 tools, discovered through vswhere; otherwise GCC/Clang must be on PATH and match Python's architecture. Create a virtual environment first.

```bash
python -m pip install -e '.[example,dev]'
python scripts/build_native.py
python -m unittest discover -s tests -v
python -m hybrid_quant.research_demo --output artifacts/demo
```

On Windows PowerShell, replace the single-quoted extras argument with `".[example,dev]"` if needed. Build locally; native binaries are intentionally not distributed. The CI workflow defines Linux verification; consult its run status before assuming that platform has passed.

The demo generates eight synthetic securities, computes close-known features, retrains a Random Forest in rolling windows, ranks securities, and executes next-session orders through the C++ account. It exports predictions, training-window metadata, fills, equity and a cost-aware summary. Synthetic performance is not an estimate of real investment performance.

## Engineering scope

| Layer | Implemented here | Evidence |
|---|---|---|
| Research | Rolling training; explicit label-end cutoff; deterministic ranking | `research_demo.py`, temporal tests |
| Execution | Stateful long-only cash account; positions, fees, slippage, limits, halts, partial fills | Native engine tests |
| Corporate actions | Split/share adjustment and dividend primitives; feature adjustment utilities | Native tests; source provenance |
| Boundary | Python `ctypes` wrapper over a C ABI; native resource lifetime management | Account context-manager tests |
| Strategy accounting | Broker-net plans, deterministic partial-fill allocation, isolated cash and share reconciliation | `ledger.py`, ledger tests |
| Reproducibility | Generated data; fixed seed; exported experiment artifacts; source build; CI | Quick-start commands |

This is a bar-based simulator, not an exchange order book or an HFT matching engine. It does not represent queue priority, market impact, borrow availability or short-account margin.

## Reading paths

- Quantitative development: [architecture](docs/ARCHITECTURE.md), C++ account implementation, native wrapper and tests.
- Quantitative research: [methodology](docs/RESEARCH.md), label isolation tests and [research record](docs/RESEARCH_RECORD.md).
- Operational engineering: [failure analysis](docs/OPERATIONS.md), [data contract](docs/DATA.md).
- 中文说明与求职使用：[中文指南](docs/README_CN.md).

The original machine-specific broker launchers, encrypted credentials, account activity, raw vendor data and serialized model weights are not part of this public package. See [scope and provenance](docs/PROVENANCE.md) for what was extracted and what still needs an independent migration.

## Limitations and next work

The example uses no SEC joins, ETF overlay or realistic point-in-time universe. Those are requirements for a real research reproduction, not hidden assumptions of the synthetic demo. The historical project has survivor-selection risk, already-viewed evaluation periods and incomplete company-action handling. No historical return leaderboard is presented as fresh out-of-sample evidence.

Future extensions: portable point-in-time financial adapter; full execution-aware model comparison; robust account/position snapshot reconciliation; independent validation of corporate-action chains; broker adapter with durable idempotency and recovery tests. Each should land with fixtures and documented acceptance criteria.

## Data and licensing

No proprietary market data or credentials are included. Obtain your own data and verify its redistribution permissions. No blanket open-source license is assigned in this staging release: confirm authorship and third-party rights before selecting a license. Public hosting alone does not grant reuse rights.
