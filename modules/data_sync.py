"""
Data sync entrypoint.

The project uses local TongDaXin files as its market data source.
"""

import argparse
import logging
from typing import List, Optional

try:
    from .database import init_database
    from .tdx_data_sync import TdxDataSyncer
except ImportError:
    from database import init_database
    from tdx_data_sync import TdxDataSyncer


DataSyncer = TdxDataSyncer


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="TongDaXin local data sync tool")
    parser.add_argument("action", choices=["init", "sync", "sync-all-local", "indicators", "status"])
    parser.add_argument("--ts_code", help="Stock code, e.g. 600519.SH")
    parser.add_argument("--days", type=int, default=730, help="Number of daily bars to sync")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.action == "init":
        init_database()
        print("Database initialized")
        return

    syncer = TdxDataSyncer()

    if args.action == "sync":
        if args.ts_code:
            syncer.sync_daily_kline(args.ts_code, count=args.days)
        else:
            syncer.sync_all_local(days=args.days)
        print("Sync complete")
        print(syncer.get_sync_status())

    elif args.action == "sync-all-local":
        syncer.sync_all_local(days=args.days)
        print("Local TongDaXin full daily sync complete")
        print(syncer.get_sync_status())

    elif args.action == "indicators":
        if args.ts_code:
            syncer.sync_indicator_cache(args.ts_code)
        else:
            syncer.sync_all_indicators()
        print("Indicator sync complete")
        print(syncer.get_sync_status())

    elif args.action == "status":
        status = syncer.get_sync_status()
        print("=" * 50)
        print(f"Database: {status['db_path']}")
        print(f"Source: {status.get('source', 'tdx')}")
        print(f"TDX path: {status.get('tdx_path', '')}")
        print(f"Local .day files: {status.get('local_stock_files', 0)}")
        print(f"Stocks: {status['stock_count']}")
        print(f"K-lines: {status['kline_count']}")
        print("-" * 50)
        print("Sync status:")
        for item in status["sync_status"]:
            print(f"  {item['data_type']}: {item['last_date']} ({item['status']})")


if __name__ == "__main__":
    main()
