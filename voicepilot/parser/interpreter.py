"""
Command interpreter — maps raw transcription text to ParsedCommand.

Algorithm
---------
1. Normalise the transcription (lowercase, synonym expansion).
2. For each registered Intent, try each pattern template.
3. Score the match using rapidfuzz partial_ratio (handles word insertions
   and ASR errors gracefully).
4. If the best match exceeds the confidence threshold, extract slot values
   and return a ParsedCommand.
5. If no match is found, publish COMMAND_UNKNOWN and raise UnknownCommandError.

Slot extraction
---------------
Patterns like "open {app}" are compiled to a regex that captures everything
after the keyword.  For example:
    pattern = "open {app}"
    text    = "open firefox"
    → slots = {"app": "firefox"}

Multi-word slot values are captured greedily (e.g. "create folder my projects").
"""

from __future__ import annotations

import logging
import re
from typing import Any

from rapidfuzz import fuzz  # type: ignore[import]

from voicepilot.core.events import EventType, bus
from voicepilot.core.exceptions import UnknownCommandError
from voicepilot.parser.grammar import ALL_INTENTS
from voicepilot.parser.intent import Intent, ParsedCommand
from voicepilot.parser.synonyms import normalise_text

logger = logging.getLogger(__name__)

_SOURCE = "interpreter"

# Minimum rapidfuzz score (0–100) to accept a match
DEFAULT_CONFIDENCE_THRESHOLD = 72


class CommandInterpreter:
    """
    Converts a raw transcription string into a ParsedCommand.

    Parameters
    ----------
    intents:
        List of intents to match against. Defaults to ALL_INTENTS.
    confidence_threshold:
        Minimum match score (0–100) to accept a pattern match.
    """

    def __init__(
        self,
        intents: list[Intent] | None = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.intents = intents or list(ALL_INTENTS)
        self.confidence_threshold = confidence_threshold

        # Pre-compile pattern regex for each (intent, pattern) pair
        self._compiled: list[tuple[Intent, str, re.Pattern[str]]] = []
        for intent in self.intents:
            for pattern in intent.patterns:
                regex = _pattern_to_regex(pattern)
                self._compiled.append((intent, pattern, regex))

        logger.info(
            "CommandInterpreter ready — %d intents, %d patterns",
            len(self.intents),
            len(self._compiled),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, raw_text: str) -> ParsedCommand:
        """
        Parse *raw_text* into a ParsedCommand.

        Raises
        ------
        UnknownCommandError
            If no intent pattern matches above the confidence threshold.
        """
        normalised = normalise_text(raw_text)
        logger.debug("Parsing: %r → normalised: %r", raw_text, normalised)

        # Try both the raw (lowercase) text and the normalised text.
        # This prevents synonym expansion from breaking exact-phrase intents
        # (e.g. "start dictation" → synonym-expanded to "open dictation"
        # which would match 'open_application' instead of 'start_dictation').
        candidates: list[tuple[float, Intent, str, dict]] = []

        for candidate_text in dict.fromkeys([raw_text.lower().strip(), normalised]):
            for intent, pattern_str, regex in self._compiled:
                score, slots = self._match(candidate_text, pattern_str, regex)

                if score < self.confidence_threshold:
                    continue

                if not all(s in slots for s in intent.required_slots):
                    continue

                candidates.append((score, intent, pattern_str, slots))

        if not candidates:
            logger.info("No intent matched for: %r", raw_text)
            bus.publish_type(
                EventType.COMMAND_UNKNOWN,
                data={"text": raw_text, "normalised": normalised},
                source=_SOURCE,
            )
            raise UnknownCommandError(raw_text)

        # Pick the highest-scoring candidate; ties broken by list order (earlier = wins)
        best_score, best_intent, best_pattern, best_slots = max(
            candidates, key=lambda c: c[0]
        )

        cmd = ParsedCommand(
            intent=best_intent,
            slots=best_slots,
            raw_text=raw_text,
            confidence=best_score,
            pattern_matched=best_pattern,
        )

        logger.info("Matched: %r", cmd)

        bus.publish_type(
            EventType.COMMAND_PARSED,
            data={
                "intent": best_intent.name,
                "slots": best_slots,
                "risk": best_intent.risk.name,
                "confidence": best_score,
                "raw_text": raw_text,
            },
            source=_SOURCE,
        )

        return cmd

    # ------------------------------------------------------------------
    # Matching logic
    # ------------------------------------------------------------------

    def _match(
        self,
        text: str,
        pattern_str: str,
        regex: re.Pattern[str],
    ) -> tuple[float, dict[str, Any]]:
        """
        Try to match *text* against *pattern_str*.

        Strategy:
          1. Regex structural match — the primary path.
          2. Fuzzy fallback — only for patterns with slots, and only when
             every static keyword from the pattern appears in the text.

        Returns (score, slots).  Score is 0 if no match.
        """
        has_slots = bool(re.search(r"\{[^}]+\}", pattern_str))
        static = _static_portion(pattern_str)
        static_words = static.split() if static else []

        # --- 1. Regex structural match ---
        m = regex.match(text)
        if m:
            slots = {k: v.strip() for k, v in m.groupdict().items() if v is not None}

            # Specificity: reward patterns with more static keywords.
            # A bare "open {X}" (1 static word, 1 slot) scores lower than
            # "open {X} folder" (2 static words, 1 slot).
            slot_count = len(re.findall(r"\{[^}]+\}", pattern_str))
            n_static = len(static_words)
            if slot_count == 0:
                # Slot-less patterns are exact phrases: "kör" should mean
                # "kör" (or "kör" + a stray filler word), not "kör <anything>".
                # The regex still allows trailing content — via the optional
                # "(\s+.*)?" group — so ASR filler words ("stäng fönstret nu")
                # don't break the match. But every word swallowed by that
                # trailing group is a word the pattern did NOT account for,
                # so it must not keep full specificity: otherwise a bare
                # exact phrase like "kör" would out-score a more specific
                # slot pattern like "kör {app}" on input "kör firefox",
                # even though the slot pattern is the actually-correct match.
                # Penalise proportionally to how much of the utterance was
                # ignored, so a single filler word costs little but a
                # swallowed slot value (a large fraction of the utterance)
                # costs a lot.
                trailing = m.groups()[-1] if m.groups() else None
                if trailing:
                    trailing_words = len(trailing.split())
                    total_words = len(text.split())
                    ignored_fraction = trailing_words / max(total_words, 1)
                    specificity = max(1.0 - ignored_fraction, 0.0)
                else:
                    specificity = 1.0
            else:
                specificity = 0.7 + 0.3 * (n_static / max(n_static + slot_count, 1))

            base = fuzz.ratio(text, pattern_str)
            score = (90.0 + base * 0.1) * specificity
            return min(score, 100.0), slots

        # --- 2. Fuzzy fallback (slot patterns only) ---
        if not has_slots or not static_words:
            return 0.0, {}

        # Require all static keywords to appear verbatim in the text
        text_lower = text.lower()
        if not all(w.lower() in text_lower for w in static_words):
            return 0.0, {}

        score = float(fuzz.partial_ratio(static, text))
        if score < self.confidence_threshold:
            return score, {}

        slots = _extract_slots_fuzzy(text, pattern_str)
        # Penalise fuzzy matches vs structural matches
        score *= 0.75
        return score, slots


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """
    Convert a pattern template to a compiled regex.

    "{slot}" → named capture group "(?P<slot>.+)"
    The pattern is anchored at the start; trailing content is allowed.
    """
    escaped = re.escape(pattern)
    # Replace escaped slot placeholders with named capture groups
    slot_re = re.compile(r"\\{(\w+)\\}")
    regex_str = slot_re.sub(r"(?P<\1>.+?)", escaped)
    regex_str = "^" + regex_str + r"(\s+.*)?$"
    return re.compile(regex_str, re.IGNORECASE)


def _static_portion(pattern: str) -> str:
    """Extract the non-slot words from a pattern for fuzzy matching."""
    return re.sub(r"\{[^}]+\}", "", pattern).strip()


def _extract_slots_fuzzy(text: str, pattern: str) -> dict[str, Any]:
    """
    Attempt to extract slot values from text using the pattern's structure.

    Strategy: identify where the static keywords appear in text,
    then treat the surrounding text as the slot value.
    """
    slot_names = re.findall(r"\{(\w+)\}", pattern)
    if not slot_names:
        return {}

    static_part = _static_portion(pattern)
    if not static_part:
        return {}

    # Remove the static keywords from text to get candidate slot value
    cleaned = text
    for word in static_part.split():
        cleaned = re.sub(r"\b" + re.escape(word) + r"\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    if not cleaned:
        return {}

    # If single slot, assign all remaining text to it
    if len(slot_names) == 1:
        return {slot_names[0]: cleaned}

    # Multiple slots — best-effort: split remaining text equally
    words = cleaned.split()
    chunk = max(1, len(words) // len(slot_names))
    result: dict[str, Any] = {}
    for i, name in enumerate(slot_names):
        start = i * chunk
        end = start + chunk if i < len(slot_names) - 1 else len(words)
        result[name] = " ".join(words[start:end])
    return result
