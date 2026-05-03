"""
Local TongDaXin data reader.

This reads standard TDX .day files from vipdoc directly. It does not depend on
network APIs or the optional TDX TQ SDK plugin.
"""

import os
import struct
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


_env_path = Path(__file__).parent.parent / ".env"
if load_dotenv:
    load_dotenv(_env_path)


class TdxClient:
    """Read local TongDaXin daily K-line files."""

    RECORD_SIZE = 32

    def __init__(self, tdx_path: Optional[str] = None):
        self.tdx_path = Path(tdx_path or os.environ.get("TDX_PATH", r"D:\TongDaXin"))

    def check_connection(self) -> bool:
        return (self.tdx_path / "vipdoc").exists()

    @staticmethod
    def _market_prefix(ts_code: str) -> str:
        code = ts_code.split(".")[0].lower()
        suffix = ts_code.split(".")[-1].lower() if "." in ts_code else ""
        if suffix == "sh" or code.startswith(("5", "6", "9")):
            return "sh"
        if suffix == "bj" or code.startswith(("4", "8")):
            return "bj"
        return "sz"

    def _day_file(self, ts_code: str) -> Path:
        code = ts_code.split(".")[0].lower()
        market = self._market_prefix(ts_code)
        return self.tdx_path / "vipdoc" / market / "lday" / f"{market}{code}.day"

    def list_local_stocks(self) -> List[str]:
        """Return stock codes discovered from local vipdoc .day files."""
        stocks: List[str] = []
        for market, suffix in (("sh", "SH"), ("sz", "SZ"), ("bj", "BJ")):
            lday_dir = self.tdx_path / "vipdoc" / market / "lday"
            if not lday_dir.exists():
                continue
            for path in lday_dir.glob(f"{market}*.day"):
                code = path.stem[len(market):]
                if len(code) == 6 and code.isdigit():
                    stocks.append(f"{code}.{suffix}")
        return sorted(set(stocks))

    def get_daily(self, ts_code: str, count: int = 120, period: str = "1d") -> Dict[str, List[Dict[str, Any]]]:
        if period != "1d":
            raise ValueError("Local TDX reader currently supports daily period only.")

        path = self._day_file(ts_code)
        if not path.exists():
            raise FileNotFoundError(f"TDX day file not found: {path}")

        records: List[Dict[str, Any]] = []
        with path.open("rb") as f:
            data = f.read()

        for offset in range(0, len(data) - self.RECORD_SIZE + 1, self.RECORD_SIZE):
            trade_date, open_i, high_i, low_i, close_i, amount, vol, _reserved = struct.unpack(
                "<iiiiifii",
                data[offset:offset + self.RECORD_SIZE],
            )
            records.append({
                "trade_date": str(trade_date),
                "open": open_i / 100.0,
                "high": high_i / 100.0,
                "low": low_i / 100.0,
                "close": close_i / 100.0,
                "amount": float(amount),
                "vol": float(vol),
            })

        if count and count > 0:
            records = records[-count:]
        return {ts_code: records}

    def get_realtime_quote(self, ts_code: str) -> Dict[str, Any]:
        rows = self.get_daily(ts_code, count=2).get(ts_code, [])
        if not rows:
            return {}
        latest = dict(rows[-1])
        latest["ts_code"] = ts_code
        if len(rows) > 1 and rows[-2].get("close"):
            latest["pct_chg"] = (latest["close"] - rows[-2]["close"]) / rows[-2]["close"] * 100
        return latest

    def get_stock_info(self, ts_code: str) -> Dict[str, Any]:
        return {
            "ts_code": ts_code,
            "market": self._market_prefix(ts_code).upper(),
            "source": "local_tdx",
            "path": str(self._day_file(ts_code)),
        }
