import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hybrid_quant.data_audit import audit_dataset


class DataAuditTests(unittest.TestCase):
    def test_reports_missing_and_zero_symbols(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "interval=M" / "symbol=AAPL").mkdir(parents=True)
            (root / "interval=M" / "symbol=AAPL" / "part.parquet").touch()
            marker = root / "_cloud_export_completed" / "M"
            marker.mkdir(parents=True)
            (marker / "AAPL.json").write_text(json.dumps({"rows": 10}), encoding="utf-8")
            report = audit_dataset(root, ["AAPL", "MSFT"])
            self.assertFalse(report["complete"])
            self.assertEqual(report["missing_partitions"], ["MSFT"])
            self.assertEqual(report["marker_rows"], 10)


if __name__ == "__main__":
    unittest.main()
