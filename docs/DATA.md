# Data contract and publication boundary

Recommended real-data schema: symbol/security identifier, UTC bar start/end, session date, OHLCV, source, feed, adjustment mode and retrieval time. Unique keys include provider, security and timestamp. A price from a different feed is not a transparent replacement for a missing quote.

Financial features require a security-to-issuer mapping, period end, disclosure/availability time, taxonomy tag, unit, accession identifier and amendment/version policy. Store financial reports separately from market observations and perform an availability-aware join.

Corporate actions require source event identity, type, effective/ex-date, applicable security identity, ratios/cash terms and ingestion time. A symbol marked inactive is not evidence of a temporary exchange halt. Record the specific exclusion reason and effective date.

Raw minute history, private account events, model serialization and vendor caches are excluded from Git. The demo generates data in memory and writes only to ignored `artifacts/`. A future sample dataset must have an explicit redistribution license and provenance. Git LFS changes storage mechanics, not data rights.

Published evidence should use anonymized audit fixtures and summarized statistics, never API keys, DPAPI files, account identifiers, remote host details or unreviewed console dumps.
