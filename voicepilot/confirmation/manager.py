"""
Confirmation Manager — state machine for command safety.

Flow
----
1. Receive a ParsedCommand from the interpreter.
2. Classify its risk level.
3. LOW  → execute immediately.
4. MEDIUM → speak prompt, wait for "confirm" or "cancel".
5. HIGH   → speak warning, wait for full phrase "confirm delete" or "cancel".
6. Timeout → auto-cancel and notify user.

Thread model
------------
Confirmation waits happen on a daemon timer thread.  The _pending state
is protected by a lock.  Incoming transcriptions are routed here while
a confirmation is pending.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from voicepilot.confirmation.audit import AuditLog
from voicepilot.confirmation.risk import classify, risk_message
from voicepilot.core.config import ConfirmationSection
from voicepilot.core.events import EventType, bus
from voicepilot.parser.intent import ParsedCommand, RiskLevel

logger = logging.getLogger(__name__)

_SOURCE = "confirmation"


@dataclass
class PendingConfirmation:
    command: ParsedCommand
    risk: RiskLevel
    on_confirmed: Callable[[ParsedCommand], None]
    timer: threading.Timer = field(repr=False, default=None)  # type: ignore[assignment]


class ConfirmationManager:
    """
    Manages the confirmation flow for medium- and high-risk commands.

    Parameters
    ----------
    config:
        ConfirmationSection from AppConfig.
    on_execute:
        Callback invoked when a command is cleared for execution.
    on_speak:
        Callback invoked when the manager needs to say something to the user.
    audit_log:
        Optional AuditLog instance for recording outcomes.
    """

    def __init__(
        self,
        config: ConfirmationSection,
        on_execute: Callable[[ParsedCommand], None],
        on_speak: Callable[[str], None] | None = None,
        audit_log: AuditLog | None = None,
    ) -> None:
        self.config = config
        self.on_execute = on_execute
        self.on_speak = on_speak or (lambda msg: None)
        self.audit_log = audit_log

        self._pending: PendingConfirmation | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, command: ParsedCommand) -> None:
        """
        Process a ParsedCommand.

        If risk is LOW, execute immediately.
        If MEDIUM or HIGH, initiate confirmation flow.
        """
        risk = classify(command)
        logger.info("Handling command %r (risk=%s)", command.intent_name, risk.name)

        if risk == RiskLevel.LOW:
            self._execute(command, risk)
            return

        # A previously pending command is superseded by this one. Cancel it
        # before taking the lock — _cancel_pending acquires the lock itself.
        if self.has_pending:
            logger.warning("Overriding existing pending confirmation")
            self._cancel_pending(reason="superseded")

        # Begin confirmation flow. The pending state is registered first so
        # that a response arriving during the prompt is not dropped; the lock
        # is released before speaking or publishing so subscribers are free to
        # call back into this manager.
        timer = threading.Timer(
            self.config.timeout_seconds,
            self._on_timeout,
        )
        timer.daemon = True

        with self._lock:
            self._pending = PendingConfirmation(
                command=command,
                risk=risk,
                on_confirmed=self.on_execute,
                timer=timer,
            )
        timer.start()

        prompt = risk_message(command, risk, self.config)
        self.on_speak(prompt)

        bus.publish_type(
            EventType.CONFIRMATION_REQUIRED,
            data={
                "intent": command.intent_name,
                "risk": risk.name,
                "prompt": prompt,
            },
            source=_SOURCE,
        )

    def receive_response(self, text: str) -> bool:
        """
        Check if *text* is a confirmation or cancellation response.

        Returns True if the text was consumed as a confirmation response,
        False if there is no pending confirmation (text goes to parser).
        """
        with self._lock:
            if self._pending is None:
                return False

            normalised = text.strip().lower()
            pending = self._pending

        # Check for cancel first
        if self.config.cancel_phrase in normalised:
            self._cancel_pending(reason="user_cancelled")
            return True

        # Check for correct confirmation phrase
        required_phrase = (
            self.config.high_risk_phrase
            if pending.risk == RiskLevel.HIGH
            else self.config.medium_risk_phrase
        )

        if required_phrase in normalised:
            self._confirm_pending()
            return True

        # Unrecognised response — remind the user
        self.on_speak(
            f"Säg '{required_phrase}' för att bekräfta eller "
            f"'{self.config.cancel_phrase}' för att avbryta."
        )
        return True   # consumed — don't route to parser

    @property
    def has_pending(self) -> bool:
        with self._lock:
            return self._pending is not None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _confirm_pending(self) -> None:
        with self._lock:
            if self._pending is None:
                return
            pending = self._pending
            self._pending = None
            pending.timer.cancel()

        logger.info("Confirmation received for %r", pending.command.intent_name)

        bus.publish_type(
            EventType.CONFIRMATION_RECEIVED,
            data={"intent": pending.command.intent_name},
            source=_SOURCE,
        )

        self._execute(pending.command, pending.risk, confirmed=True)

    def _cancel_pending(self, reason: str = "unknown") -> None:
        """Cancel the pending confirmation. Must NOT be called holding _lock."""
        with self._lock:
            if self._pending is None:
                return
            pending = self._pending
            self._pending = None

        pending.timer.cancel()

        logger.info(
            "Command %r cancelled (reason=%s)", pending.command.intent_name, reason
        )

        self.on_speak("Avbrutet.")

        bus.publish_type(
            EventType.CONFIRMATION_CANCELLED,
            data={"intent": pending.command.intent_name, "reason": reason},
            source=_SOURCE,
        )

        if self.audit_log:
            self.audit_log.record(
                intent_name=pending.command.intent_name,
                slots=pending.command.slots,
                raw_text=pending.command.raw_text,
                risk_level=pending.risk.name,
                confidence=pending.command.confidence,
                outcome="cancelled",
            )

    def _on_timeout(self) -> None:
        with self._lock:
            if self._pending is None:
                return
            pending = self._pending
            self._pending = None

        logger.info("Confirmation timed out for %r", pending.command.intent_name)

        self.on_speak("Bekräftelsen tog för lång tid. Kommandot avbröts.")

        bus.publish_type(EventType.CONFIRMATION_TIMEOUT, source=_SOURCE)

        if self.audit_log:
            self.audit_log.record(
                intent_name=pending.command.intent_name,
                slots=pending.command.slots,
                raw_text=pending.command.raw_text,
                risk_level=pending.risk.name,
                confidence=pending.command.confidence,
                outcome="timeout",
            )

    def _execute(
        self,
        command: ParsedCommand,
        risk: RiskLevel,
        confirmed: bool = False,
    ) -> None:
        bus.publish_type(
            EventType.ACTION_STARTED,
            data={"intent": command.intent_name, "confirmed": confirmed},
            source=_SOURCE,
        )

        try:
            self.on_execute(command)
            outcome = "executed"
        except Exception as exc:
            logger.exception("Action execution failed: %s", exc)
            self.on_speak(f"Förlåt, det misslyckades: {exc}")
            outcome = "failed"
            bus.publish_type(
                EventType.ACTION_FAILED,
                data={"intent": command.intent_name, "error": str(exc)},
                source=_SOURCE,
            )

        if self.audit_log:
            self.audit_log.record(
                intent_name=command.intent_name,
                slots=command.slots,
                raw_text=command.raw_text,
                risk_level=risk.name,
                confidence=command.confidence,
                outcome=outcome,
            )

        if outcome == "executed":
            bus.publish_type(
                EventType.ACTION_COMPLETED,
                data={"intent": command.intent_name},
                source=_SOURCE,
            )
