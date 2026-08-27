"""
SQLite-backed audit log for executed commands.

Every command that passes through the ConfirmationManager is logged
here regardless of whether it was executed or cancelled.
This provides a complete, queryable history of everything VoicePilot
has done on behalf of the user.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class CommandLog(Base):
    """ORM model for a single command execution record."""

    __tablename__ = "command_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    intent_name = Column(String(64), nullable=False, index=True)
    slots = Column(Text, nullable=False, default="{}")
    raw_text = Column(Text, nullable=False)
    risk_level = Column(String(16), nullable=False)
    confidence = Column(Float, nullable=False)
    outcome = Column(String(16), nullable=False)   # "executed" | "cancelled" | "timeout" | "failed"
    error_message = Column(Text, nullable=True)


class AuditLog:
    """
    Manages the SQLite command audit log.

    Parameters
    ----------
    db_path:
        Path to the SQLite database file.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)

        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(engine)
        self._Session = sessionmaker(bind=engine)

        logger.info("AuditLog initialised at %s", db_path)

    def record(
        self,
        intent_name: str,
        slots: dict,
        raw_text: str,
        risk_level: str,
        confidence: float,
        outcome: str,
        error_message: str | None = None,
    ) -> None:
        """Insert a new log entry."""
        import json

        entry = CommandLog(
            intent_name=intent_name,
            slots=json.dumps(slots),
            raw_text=raw_text,
            risk_level=risk_level,
            confidence=confidence,
            outcome=outcome,
            error_message=error_message,
        )
        with self._Session() as session:
            session.add(entry)
            session.commit()

        logger.debug(
            "Audit: %s [%s] → %s", intent_name, risk_level, outcome
        )

    def recent(self, limit: int = 50) -> list[dict]:
        """Return the most recent log entries as dicts."""
        import json

        with self._Session() as session:
            rows = (
                session.query(CommandLog)
                .order_by(CommandLog.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": r.id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "intent_name": r.intent_name,
                    "slots": json.loads(r.slots),
                    "raw_text": r.raw_text,
                    "risk_level": r.risk_level,
                    "confidence": r.confidence,
                    "outcome": r.outcome,
                    "error_message": r.error_message,
                }
                for r in rows
            ]
