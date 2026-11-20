from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional


def _symbols(path: Path) -> List[str]:
    return [line.strip().upper() for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _partition_symbols(root: Path) -> set:
    interval = root / "interval=M"
    if not interval.exists():
        return set()
    return {item.name.split("=", 1)[1].upper()
            for item in interval.iterdir()
            if item.is_dir() and item.name.startswith("symbol=")}


def _marker_rows(root: Path) -> Dict[str, int]:
    marker_dir = root / "_cloud_export_completed" / "M"
    rows: Dict[str, int] = {}
    if not marker_dir.exists():
        return rows
    for marker in marker_dir.glob("*.json"):
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
            rows[marker.stem.upper()] = int(payload.get("rows", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
    return rows


def _has_parquet(root: Path, symbol: str) -> bool:
    directory = root / "interval=M" / ("symbol=" + symbol)
    return directory.exists() and next(directory.rglob("*.parquet"), None) is not None


def audit_dataset(root: Path, expected: Iterable[str]) -> dict:
    root = root.resolve()
    expected_list = list(dict.fromkeys(symbol.upper() for symbol in expected))
    partitions = _partition_symbols(root)
    rows = _marker_rows(root)
    missing_partitions = [symbol for symbol in expected_list if symbol not in partitions]
    missing_parquet = [symbol for symbol in expected_list
                       if symbol in partitions and not _has_parquet(root, symbol)]
    zero_markers = [symbol for symbol in expected_list if symbol in rows and rows[symbol] <= 0]
    positive_rows = sum(rows.get(symbol, 0) for symbol in expected_list)
    complete = not missing_partitions and not missing_parquet and not zero_markers
    return {
        "root": str(root),
        "expected_symbols": len(expected_list),
        "partition_symbols": len(partitions),
        "symbols_with_positive_markers": sum(rows.get(symbol, 0) > 0
                                             for symbol in expected_list),
        "marker_rows": positive_rows,
        "missing_partitions": missing_partitions,
        "missing_parquet": missing_parquet,
        "zero_or_invalid_markers": zero_markers,
        "complete": complete,
    }


def audit_from_files(equity_root: Path, symbols_file: Path,
                     context_root: Optional[Path] = None,
                     context_symbols_file: Optional[Path] = None) -> dict:
    result = {"equities": audit_dataset(equity_root, _symbols(symbols_file))}
    if context_root is not None and context_symbols_file is not None:
        result["market_context"] = audit_dataset(
            context_root, _symbols(context_symbols_file))
    result["complete"] = all(section.get("complete", False)
                             for key, section in result.items()
                             if key != "complete")
    return result
