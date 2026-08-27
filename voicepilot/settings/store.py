"""
Settings store — persistent user preferences backed by SQLite.

Stores arbitrary key-value settings that don't belong in the TOML
config file (e.g. window geometry, recent commands, usage stats).
The TOML config is for structural config; this store is for runtime prefs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, String, Text, create_engine, func
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


class _Base(DeclarativeBase):
    pass


class _Setting(_Base):
    __tablename__ = "settings"

    key = Column(String(128), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class SettingsStore:
    """
    Simple SQLite-backed key-value store for runtime user preferences.

    Values are JSON-serialised, so any JSON-compatible type is supported.

    Usage
    -----
        store = SettingsStore(Path("~/.local/share/voicepilot/settings.db"))
        store.set("last_model", "base.en")
        model = store.get("last_model", default="base.en")
    """

    def __init__(self, db_path: Path) -> None:
        db_path = Path(db_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        _Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)

        logger.info("SettingsStore at %s", db_path)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve the value for *key*, or *default* if not set."""
        with self._Session() as session:
            row = session.get(_Setting, key)
            if row is None:
                return default
            try:
                return json.loads(row.value)
            except (json.JSONDecodeError, TypeError):
                return row.value

    def set(self, key: str, value: Any) -> None:
        """Persist *value* for *key*."""
        serialised = json.dumps(value)
        with self._Session() as session:
            row = session.get(_Setting, key)
            if row is None:
                session.add(_Setting(key=key, value=serialised))
            else:
                row.value = serialised
            session.commit()

    def delete(self, key: str) -> None:
        """Remove *key* from the store."""
        with self._Session() as session:
            row = session.get(_Setting, key)
            if row:
                session.delete(row)
                session.commit()

    def all(self) -> dict[str, Any]:
        """Return all settings as a dict."""
        with self._Session() as session:
            rows = session.query(_Setting).all()
            result: dict[str, Any] = {}
            for row in rows:
                try:
                    result[row.key] = json.loads(row.value)
                except (json.JSONDecodeError, TypeError):
                    result[row.key] = row.value
            return result
