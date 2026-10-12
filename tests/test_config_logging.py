import json
import logging
import time

import pytest

from app.config import ConfigError, LoggingConfig, load_config
from app.logging_setup import setup_logging


def test_load_config_missing_file(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "nope.json")


def test_load_config_missing_key(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"secret_key": "x"}))
    with pytest.raises(ConfigError):
        load_config(path)


def test_load_project_config():
    config = load_config()
    assert config.database.name == "texxem"
    assert config.database.url().drivername == "mysql+pymysql"


def test_logging_keeps_five_files(tmp_path):
    for i in range(7):
        (tmp_path / f"app_20260101_00000{i}.log").write_text("")
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        new_file = setup_logging(LoggingConfig(directory=tmp_path, level="INFO", retention_count=5))
        time.sleep(0.01)
        files = sorted(p.name for p in tmp_path.glob("app_*.log"))
        assert len(files) == 5
        assert new_file.name in files
        assert "app_20260101_000000.log" not in files
        assert "app_20260101_000002.log" not in files
        assert "app_20260101_000003.log" in files
    finally:
        for handler in list(root.handlers):
            if handler not in before:
                root.removeHandler(handler)
                handler.close()
