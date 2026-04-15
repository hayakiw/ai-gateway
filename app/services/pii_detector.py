"""PII Detection and Masking using Microsoft Presidio."""

import re
from dataclasses import dataclass, field

from presidio_analyzer import (
    AnalyzerEngine,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpEngineProvider


@dataclass
class MaskingResult:
    """Result of PII masking operation."""

    masked_text: str
    mapping: dict[str, str] = field(default_factory=dict)
    # mapping: {"[PERSON_1]": "田中", "[EMAIL_1]": "test@example.com", ...}


class PiiDetector:
    """Detects and masks PII using Presidio with Japanese language support."""

    # Presidio entity type -> human-readable prefix
    ENTITY_PREFIX_MAP: dict[str, str] = {
        "PERSON": "PERSON",
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "CREDIT_CARD": "CREDIT_CARD",
        "IP_ADDRESS": "IP",
        "LOCATION": "LOCATION",
        "DATE_TIME": "DATE",
        "NRP": "NRP",
        "MEDICAL_LICENSE": "MEDICAL_LICENSE",
        "URL": "URL",
        "IBAN_CODE": "IBAN",
    }

    # Entities to detect
    TARGET_ENTITIES: list[str] = [
        "PERSON",
        "EMAIL_ADDRESS",
        "PHONE_NUMBER",
        "CREDIT_CARD",
        "IP_ADDRESS",
        "LOCATION",
        "URL",
    ]

    def __init__(self, languages: list[str] | None = None):
        self._languages = languages or ["ja", "en"]

        # Configure NLP engine with spaCy models
        nlp_config = {
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": "ja", "model_name": "ja_core_news_lg"},
                {"lang_code": "en", "model_name": "en_core_web_lg"},
            ],
        }
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()

        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=self._languages,
        )

        email_pattern = Pattern(
            name="email_strong",
            regex=r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
            score=1.0,
        )
        for lang in self._languages:
            self._analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="EMAIL_ADDRESS",
                    name=f"StrongEmailRecognizer_{lang}",
                    patterns=[email_pattern],
                    supported_language=lang,
                )
            )

    @staticmethod
    def _next_placeholder(
        entity_type: str, counters: dict[str, int]
    ) -> str:
        """Generate the next placeholder for a given entity type.

        e.g., PERSON -> [PERSON_1], [PERSON_2], ...
        Uses a per-call counters dict (not shared state).
        """
        prefix = PiiDetector.ENTITY_PREFIX_MAP.get(entity_type, entity_type)
        count = counters.get(prefix, 0) + 1
        counters[prefix] = count
        return f"[{prefix}_{count}]"

    def detect(
        self, text: str, language: str = "ja"
    ) -> list[RecognizerResult]:
        """Detect PII entities in the text."""
        results = self._analyzer.analyze(
            text=text,
            entities=self.TARGET_ENTITIES,
            language=language,
        )
        return results

    def mask(self, text: str, language: str = "ja") -> MaskingResult:
        """Detect PII and replace with placeholders. Returns masked text and mapping.

        Thread-safe: all mutable state is local to this call.
        """
        counters: dict[str, int] = {}

        results = self.detect(text, language)
        if not results:
            return MaskingResult(masked_text=text, mapping={})

        # Sort by score desc, then span length desc so longer, higher-confidence entities win
        results_sorted = sorted(
            results,
            key=lambda r: (r.score, r.end - r.start),
            reverse=True,
        )

        # Deduplicate overlapping entities (keep highest score)
        filtered: list[RecognizerResult] = []
        for result in results_sorted:
            overlaps = False
            for existing in filtered:
                if result.start < existing.end and result.end > existing.start:
                    overlaps = True
                    break
            if not overlaps:
                filtered.append(result)

        # Sort ascending by start position for consistent counter numbering
        filtered.sort(key=lambda r: r.start)

        mapping: dict[str, str] = {}
        # Track already-seen original values to reuse the same placeholder
        value_to_placeholder: dict[str, str] = {}

        masked_text = text
        offset = 0

        for result in filtered:
            start = result.start + offset
            end = result.end + offset
            original_value = masked_text[start:end]

            placeholder = value_to_placeholder.get(original_value)

            # Coreference heuristic for PERSON: if one name contains another
            # (e.g., "田中太郎" and "田中"), reuse the same placeholder and
            # keep the longer original as the canonical mapping value.
            if placeholder is None and result.entity_type == "PERSON":
                for seen_value, seen_placeholder in value_to_placeholder.items():
                    if not seen_placeholder.startswith("[PERSON_"):
                        continue
                    if original_value in seen_value or seen_value in original_value:
                        placeholder = seen_placeholder
                        # Prefer the longer form as the canonical value
                        if len(original_value) > len(seen_value):
                            mapping[placeholder] = original_value
                            value_to_placeholder[original_value] = placeholder
                        break

            if placeholder is None:
                placeholder = self._next_placeholder(
                    result.entity_type, counters
                )
                value_to_placeholder[original_value] = placeholder
                mapping[placeholder] = original_value

            masked_text = masked_text[:start] + placeholder + masked_text[end:]
            offset += len(placeholder) - (result.end - result.start)

        return MaskingResult(masked_text=masked_text, mapping=mapping)

    def unmask(self, text: str, mapping: dict[str, str]) -> str:
        """Replace placeholders back with original values.

        Uses regex to replace all placeholders simultaneously,
        avoiding double-replacement issues from sequential str.replace().
        """
        if not mapping:
            return text

        # Build pattern that matches any placeholder (longest first to avoid partial matches)
        sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
        pattern = "|".join(re.escape(k) for k in sorted_keys)
        return re.sub(pattern, lambda m: mapping[m.group(0)], text)

    def create_stream_unmasker(
        self, mapping: dict[str, str]
    ) -> "StreamUnmasker":
        """Create a StreamUnmasker for incremental chunk-by-chunk unmasking."""
        return StreamUnmasker(mapping)


class StreamUnmasker:
    """Buffers streaming chunks and unmasks placeholders as they complete.

    Handles the case where a placeholder like [PERSON_1] is split across
    multiple chunks (e.g., "[PERS" + "ON_1]").
    """

    def __init__(self, mapping: dict[str, str]) -> None:
        self._mapping = mapping
        self._buffer = ""

        if mapping:
            sorted_keys = sorted(mapping.keys(), key=len, reverse=True)
            self._pattern = re.compile(
                "|".join(re.escape(k) for k in sorted_keys)
            )
            # The longest placeholder determines max buffer size needed
            self._max_placeholder_len = max(len(k) for k in mapping)
        else:
            self._pattern = None
            self._max_placeholder_len = 0

    def feed(self, chunk: str) -> str:
        """Feed a new chunk and return text that can be safely emitted.

        Buffers trailing text that might be a partial placeholder.
        """
        if not self._mapping:
            return chunk

        self._buffer += chunk

        # Replace all complete placeholders in the buffer
        self._buffer = self._pattern.sub(
            lambda m: self._mapping[m.group(0)], self._buffer
        )

        # Check if the buffer ends with a potential partial placeholder.
        # A partial placeholder starts with '[' and hasn't been closed with ']'.
        last_open = self._buffer.rfind("[")
        if last_open != -1 and "]" not in self._buffer[last_open:]:
            tail_len = len(self._buffer) - last_open
            if tail_len < self._max_placeholder_len:
                # Could still be a partial placeholder — keep buffered
                emit = self._buffer[:last_open]
                self._buffer = self._buffer[last_open:]
            else:
                # Exceeds max placeholder length — not a placeholder, flush
                emit = self._buffer
                self._buffer = ""
        else:
            # No partial placeholder, emit everything
            emit = self._buffer
            self._buffer = ""

        return emit

    def flush(self) -> str:
        """Flush any remaining buffered text. Call when the stream ends."""
        remaining = self._buffer
        self._buffer = ""
        return remaining
