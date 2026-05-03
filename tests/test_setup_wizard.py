import os
from pathlib import Path

from modules.setup_wizard import (
    MODE_NORMAL,
    MODE_TDX,
    check_data_mode,
    check_env_exists,
    get_mode_display_name,
    write_env_file,
)


class TestCheckEnvExists:
    def test_no_env_not_configured(self):
        for key in ("TDX_PATH", "DATA_MODE"):
            os.environ.pop(key, None)
        assert check_env_exists() is False


class TestWriteEnvFile:
    def test_write_websearch_mode(self):
        os.environ.pop("DATA_MODE", None)
        path = write_env_file(mode=MODE_NORMAL)
        assert Path(path).exists()
        assert os.environ.get("DATA_MODE") == MODE_NORMAL
        assert "DATA_MODE=websearch" in Path(path).read_text(encoding="utf-8")

    def test_write_tdx_mode(self):
        os.environ.pop("DATA_MODE", None)
        os.environ.pop("TDX_PATH", None)
        path = write_env_file(mode=MODE_TDX, tdx_path=r"D:\TongDaXin")
        assert Path(path).exists()
        assert os.environ.get("DATA_MODE") == MODE_TDX
        assert os.environ.get("TDX_PATH") == r"D:\TongDaXin"
        content = Path(path).read_text(encoding="utf-8")
        assert "DATA_MODE=tdx" in content
        assert r"TDX_PATH=D:\TongDaXin" in content


class TestCheckDataMode:
    def test_returns_mode(self):
        os.environ["DATA_MODE"] = "websearch"
        assert check_data_mode() == "websearch"

    def test_returns_none_if_not_set(self):
        os.environ.pop("DATA_MODE", None)
        mode = check_data_mode()
        assert mode is None or mode in ("websearch", "tdx")


class TestGetModeDisplayName:
    def test_tdx(self):
        assert get_mode_display_name(MODE_TDX) == "TDX"

    def test_normal(self):
        assert get_mode_display_name(MODE_NORMAL) == "普通小万"

    def test_unknown(self):
        assert get_mode_display_name("unknown") == "unknown"
