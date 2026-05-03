"""
Data source setup helpers.

The skill uses local TongDaXin files by default. Network market-data providers
are intentionally not required.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


_env_path = Path(__file__).parent.parent / ".env"
if load_dotenv:
    load_dotenv(_env_path)


MODE_TDX = "tdx"
MODE_NORMAL = "websearch"
MODE_NAMES = {
    MODE_TDX: "TDX",
    MODE_NORMAL: "普通小万",
}


def check_env_exists() -> bool:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return False
    data_mode = os.environ.get("DATA_MODE", "")
    if data_mode == MODE_TDX:
        return bool(os.environ.get("TDX_PATH", ""))
    return data_mode == MODE_NORMAL


def check_data_mode() -> Optional[str]:
    return os.environ.get("DATA_MODE", None)


def get_mode_display_name(mode: str) -> str:
    return MODE_NAMES.get(mode, mode)


def write_env_file(mode: str = MODE_TDX, tdx_path: Optional[str] = None) -> str:
    env_path = Path(__file__).parent.parent / ".env"
    tdx_path = tdx_path or os.environ.get("TDX_PATH", r"D:\TongDaXin")

    lines = [
        "# 数据模式: tdx(本地通达信数据) 或 websearch(网络搜索)",
        f"DATA_MODE={mode}",
        "",
    ]
    if mode == MODE_TDX:
        lines.extend([
            "# TongDaXin local data path",
            f"TDX_PATH={tdx_path}",
            "",
        ])
    lines.extend([
        "# 数据库路径（相对于项目根目录）",
        "DATA_DIR=data",
        "DB_PATH=data/stock_data.db",
        "",
    ])

    env_path.write_text("\n".join(lines), encoding="utf-8")
    os.environ["DATA_MODE"] = mode
    if mode == MODE_TDX:
        os.environ["TDX_PATH"] = tdx_path
    return str(env_path)


def test_tdx_connection(tdx_path: Optional[str] = None) -> bool:
    try:
        from .tdx_client import TdxClient
    except ImportError:
        from tdx_client import TdxClient
    return TdxClient(tdx_path=tdx_path).check_connection()


def run_wizard():
    if check_env_exists():
        mode = check_data_mode()
        print(f"[已配置] 当前模式: {get_mode_display_name(mode)}")
        return mode

    path = input(r"通达信安装目录 [D:\TongDaXin]: ").strip() or r"D:\TongDaXin"
    if test_tdx_connection(path):
        env_path = write_env_file(mode=MODE_TDX, tdx_path=path)
        print(f"配置已写入: {env_path}")
        print("TDX 模式已启用")
        return MODE_TDX

    print("未找到通达信 vipdoc 目录，已切换为普通小万模式")
    write_env_file(mode=MODE_NORMAL)
    return MODE_NORMAL


if __name__ == "__main__":
    print(f"最终模式: {get_mode_display_name(run_wizard())}")
