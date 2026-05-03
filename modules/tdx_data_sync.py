"""
TDX-backed data sync.

This writes TongDaXin CLI data into the existing SQLite schema so indicator
calculation can continue to use daily_kline and indicator_cache unchanged.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from .database import get_connection, get_db_path, init_database
    from .tdx_client import TdxClient
except ImportError:
    from database import get_connection, get_db_path, init_database
    from tdx_client import TdxClient


logger = logging.getLogger(__name__)


def _first(row: Dict[str, Any], names: List[str], default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 8 and text[:8].isdigit():
        return text[:8]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y%m%d")
        except ValueError:
            pass
    return text.replace("-", "").replace("/", "")[:8]


def _extract_rows(payload: Any, ts_code: str) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get(ts_code),
        payload.get(ts_code.upper()),
        payload.get(ts_code.lower()),
        payload.get("data"),
        payload.get("records"),
        payload.get("rows"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]

    for value in payload.values():
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


class TdxDataSyncer:
    """Syncer compatible with the existing DataSyncer command surface."""

    def __init__(self, client: Optional[TdxClient] = None):
        self.client = client or TdxClient()

    def _log_sync(self, data_type: str, ts_code: Optional[str], last_date: str,
                  status: str, message: str = ""):
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sync_log (data_type, ts_code, last_date, status, message)
                VALUES (?, ?, ?, ?, ?)
            """, (data_type, ts_code, last_date, status, message))

    def sync_stock_basic(self, ts_codes: Optional[List[str]] = None) -> int:
        if not ts_codes:
            ts_codes = self.client.list_local_stocks()

        count = 0
        with get_connection() as conn:
            cursor = conn.cursor()
            for ts_code in ts_codes:
                info = self.client.get_stock_info(ts_code)
                name = _first(info, ["name", "stock_name", "sec_name", "short_name"], "")
                industry = _first(info, ["industry"], "")
                market = "SH" if ts_code.endswith(".SH") else "SZ" if ts_code.endswith(".SZ") else ""
                cursor.execute("""
                    INSERT OR REPLACE INTO stock_basic
                    (ts_code, name, area, industry, market, list_date, is_hs)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ts_code, name, "", industry, market, "", ""))
                count += 1

        self._log_sync("stock_basic", None, datetime.now().strftime("%Y%m%d"), "success")
        return count

    def sync_daily_kline(self, ts_code: str, start_date: Optional[str] = None,
                         end_date: Optional[str] = None, count: int = 730) -> int:
        payload = self.client.get_daily(ts_code, count=count)
        rows = _extract_rows(payload, ts_code)
        if not rows:
            self._log_sync("daily_kline", ts_code, "", "failed", "TDX returned no rows")
            return 0

        normalized = []
        previous_close = 0.0
        for row in rows:
            trade_date = _normalize_date(_first(row, ["trade_date", "date", "datetime", "time", "index"]))
            if not trade_date:
                continue

            close = _as_float(_first(row, ["close"]))
            open_price = _as_float(_first(row, ["open"]))
            high = _as_float(_first(row, ["high"]))
            low = _as_float(_first(row, ["low"]))
            vol = _as_float(_first(row, ["vol", "volume"]))
            amount = _as_float(_first(row, ["amount"]))
            pct_chg = _first(row, ["pct_chg", "change_pct"], None)
            pct_chg = _as_float(pct_chg, 0.0)
            if pct_chg == 0.0 and previous_close:
                pct_chg = (close - previous_close) / previous_close * 100

            normalized.append({
                "ts_code": ts_code,
                "trade_date": trade_date,
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "vol": vol,
                "amount": amount,
                "pct_chg": pct_chg,
            })
            previous_close = close

        if start_date:
            normalized = [row for row in normalized if row["trade_date"] >= start_date]
        if end_date:
            normalized = [row for row in normalized if row["trade_date"] <= end_date]
        if not normalized:
            return 0

        normalized.sort(key=lambda row: row["trade_date"])

        with get_connection() as conn:
            cursor = conn.cursor()
            market = "SH" if ts_code.endswith(".SH") else "SZ" if ts_code.endswith(".SZ") else ""
            cursor.execute("""
                INSERT OR IGNORE INTO stock_basic
                (ts_code, name, area, industry, market, list_date, is_hs)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts_code, "", "", "", market, "", ""))
            for row in normalized:
                pct_chg = row["pct_chg"]
                cursor.execute("""
                    INSERT OR REPLACE INTO daily_kline
                    (ts_code, trade_date, open, high, low, close, vol, amount,
                     pct_chg, vol_ratio, is_limit_up, is_limit_down)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["ts_code"], row["trade_date"], row["open"], row["high"],
                    row["low"], row["close"], row["vol"], row["amount"],
                    pct_chg, None, int(pct_chg >= 9.9), int(pct_chg <= -9.9),
                ))

        latest_date = normalized[-1]["trade_date"]
        self._log_sync("daily_kline", ts_code, latest_date, "success")
        logger.info("TDX daily kline sync complete: %s, %s rows", ts_code, len(normalized))
        return len(normalized)

    def sync_all_daily_kline(self, ts_codes: Optional[List[str]] = None,
                              days: int = 730) -> Dict[str, int]:
        if ts_codes is None:
            ts_codes = self.client.list_local_stocks()

        results: Dict[str, int] = {}
        for index, ts_code in enumerate(ts_codes, start=1):
            try:
                results[ts_code] = self.sync_daily_kline(ts_code, count=days)
            except Exception as exc:
                logger.warning("TDX daily kline sync failed: %s, %s", ts_code, exc)
                self._log_sync("daily_kline", ts_code, "", "failed", str(exc))
                results[ts_code] = 0
            if index % 100 == 0:
                logger.info("TDX sync progress: %s/%s", index, len(ts_codes))

        success_count = sum(1 for count in results.values() if count > 0)
        self._log_sync(
            "daily_kline_all",
            None,
            datetime.now().strftime("%Y%m%d"),
            "success",
            f"{success_count}/{len(ts_codes)} stocks synced",
        )
        return results

    def sync_all_local(self, days: int = 730) -> Dict[str, int]:
        ts_codes = self.client.list_local_stocks()
        self.sync_stock_basic(ts_codes)
        return self.sync_all_daily_kline(ts_codes=ts_codes, days=days)

    def sync_indicator_cache(self, ts_code: str, days: int = 120) -> int:
        try:
            from .indicators import analyze_stock, get_kline_data
        except ImportError:
            from indicators import analyze_stock, get_kline_data

        klines = get_kline_data(ts_code, days)
        if not klines:
            return 0

        latest = klines[-1]
        result = analyze_stock(ts_code, days)
        signal = result.signal.value if hasattr(result.signal, "value") else str(result.signal)
        sell_reason = ""
        if getattr(result, "sell_items", None):
            sell_reason = ",".join([k for k, v in result.sell_items.items() if not v])

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO indicator_cache
                (ts_code, trade_date, close, open, high, low, vol, pct_chg,
                 k, d, j, dif, dea, macd_hist, bbi,
                 ma5, ma10, ma20, ma60,
                 rsi6, rsi12, rsi24, wr5, wr10,
                 boll_mid, boll_upper, boll_lower, boll_width, boll_position,
                 vol_ratio, zg_white, dg_yellow,
                 is_gold_cross, is_dead_cross,
                 rsl_short, rsl_long, is_needle_20,
                 brick_value, brick_trend, brick_count, brick_trend_up, is_fanbao,
                 is_beidou, is_suoliang, is_jiayin_zhenyang, is_jiayang_zhenyin, is_fangliang_yinxian,
                 sell_score, sell_reason, signal, signal_desc,
                 prev_high, prev_low, dmi_plus, dmi_minus, adx,
                 net_lg_mf, net_elg_mf, last_b1_date, last_b1_price,
                 last_yidong_date, market_pct_chg, market_dir, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_code, latest.trade_date, latest.close, latest.open, latest.high, latest.low, latest.vol, latest.pct_chg,
                result.k, result.d, result.j, result.dif, result.dea, result.macd_hist, result.bbi,
                result.ma5, result.ma10, result.ma20, result.ma60,
                result.rsi6, result.rsi12, result.rsi24, result.wr5, result.wr10,
                result.boll_mid, result.boll_upper, result.boll_lower, result.boll_width, result.boll_position,
                result.vol_ratio, result.zg_white, result.dg_yellow,
                int(result.is_gold_cross), int(result.is_dead_cross),
                result.rsl_short, result.rsl_long, int(result.is_needle_20),
                result.brick_value, result.brick_trend, result.brick_count, int(result.brick_trend_up), int(result.is_fanbao),
                int(result.is_beidou), int(result.is_suoliang), int(result.is_jiayin_zhenyang),
                int(result.is_jiayang_zhenyin), int(result.is_fangliang_yinxian),
                result.sell_score, sell_reason, signal, signal,
                result.prev_high, result.prev_low, result.dmi_plus, result.dmi_minus, result.adx,
                0, 0, None, 0, None, 0, "NEUTRAL", None,
            ))

        self._log_sync("indicator_cache", ts_code, latest.trade_date, "success")
        return 1

    def sync_all_indicators(self, ts_codes: Optional[List[str]] = None) -> Dict[str, int]:
        if ts_codes is None:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT ts_code FROM daily_kline")
                ts_codes = [row["ts_code"] for row in cursor.fetchall()]
        return {ts_code: self.sync_indicator_cache(ts_code) for ts_code in ts_codes}

    def get_sync_status(self) -> Dict[str, Any]:
        init_database()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM stock_basic")
            stock_count = cursor.fetchone()["cnt"]
            cursor.execute("SELECT COUNT(*) as cnt FROM daily_kline")
            kline_count = cursor.fetchone()["cnt"]
            cursor.execute("""
                SELECT data_type, last_date, status, created_at
                FROM sync_log
                WHERE id IN (
                    SELECT MAX(id) FROM sync_log GROUP BY data_type
                )
            """)
            sync_status = [dict(row) for row in cursor.fetchall()]

        return {
            "stock_count": stock_count,
            "kline_count": kline_count,
            "db_path": str(get_db_path()),
            "sync_status": sync_status,
            "source": "tdx",
            "tdx_path": str(self.client.tdx_path),
            "local_stock_files": len(self.client.list_local_stocks()),
        }
