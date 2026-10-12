"""Central configuration loader. The only module that reads config.json."""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"
TEST_DB_SUFFIX = "_test"


class ConfigError(Exception):
    """Raised when config.json is missing or invalid."""


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    def url(self) -> URL:
        return URL.create(
            "mysql+pymysql",
            username=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.name,
            query={"charset": "utf8mb4"},
        )


@dataclass(frozen=True)
class LoggingConfig:
    directory: Path
    level: str
    retention_count: int


@dataclass(frozen=True)
class UploadsConfig:
    directory: Path


@dataclass(frozen=True)
class Config:
    secret_key: str
    database: DatabaseConfig
    logging: LoggingConfig
    uploads: UploadsConfig

    def with_database_name(self, name: str) -> "Config":
        return replace(self, database=replace(self.database, name=name))

    def for_test_mode(self) -> "Config":
        """Config for test mode: `<name>_test` database and a separate uploads directory."""
        name = self.database.name
        if not name.endswith(TEST_DB_SUFFIX):
            name += TEST_DB_SUFFIX
        return replace(
            self,
            database=replace(self.database, name=name),
            uploads=UploadsConfig(directory=self.uploads.directory / "_test"),
        )


def _require(data: dict, key: str, where: str):
    if key not in data:
        raise ConfigError(f"Missing key '{key}' in {where}")
    return data[key]


def _resolve_dir(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {path}: {exc}") from exc

    db = _require(raw, "database", "config.json")
    log = _require(raw, "logging", "config.json")
    uploads = _require(raw, "uploads", "config.json")

    retention = int(_require(log, "retention_count", "logging"))
    if retention < 1:
        raise ConfigError("logging.retention_count must be >= 1")
    level = str(_require(log, "level", "logging")).upper()
    if level not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
        raise ConfigError(f"Invalid logging.level: {level}")

    return Config(
        secret_key=str(_require(raw, "secret_key", "config.json")),
        database=DatabaseConfig(
            host=str(_require(db, "host", "database")),
            port=int(_require(db, "port", "database")),
            name=str(_require(db, "name", "database")),
            user=str(_require(db, "user", "database")),
            password=str(_require(db, "password", "database")),
        ),
        logging=LoggingConfig(
            directory=_resolve_dir(_require(log, "directory", "logging")),
            level=level,
            retention_count=retention,
        ),
        uploads=UploadsConfig(
            directory=_resolve_dir(_require(uploads, "directory", "uploads")),
        ),
    )
