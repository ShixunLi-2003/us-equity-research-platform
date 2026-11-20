from __future__ import annotations

import argparse
import json
from pathlib import Path

from .data_audit import audit_from_files


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hybrid-quant")
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit = subparsers.add_parser("audit-data", help="audit local minute-data coverage")
    audit.add_argument("--equity-root", type=Path, required=True)
    audit.add_argument("--symbols-file", type=Path, required=True)
    audit.add_argument("--context-root", type=Path)
    audit.add_argument("--context-symbols-file", type=Path)
    audit.add_argument("--output", type=Path)
    return parser


def main(argv=None) -> int:
    args = _parser().parse_args(argv)
    if bool(args.context_root) != bool(args.context_symbols_file):
        raise SystemExit("--context-root and --context-symbols-file must be used together")
    report = audit_from_files(args.equity_root, args.symbols_file,
                              args.context_root, args.context_symbols_file)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
