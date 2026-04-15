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
        "MY_NUMBER": "MY_NUMBER",
        "DRIVER_LICENSE": "DRIVER_LICENSE",
        "PASSPORT_NUMBER": "PASSPORT",
        "BANK_ACCOUNT": "BANK_ACCOUNT",
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
        "MY_NUMBER",
        "DRIVER_LICENSE",
        "PASSPORT_NUMBER",
        "BANK_ACCOUNT",
    ]

    CONTEXTUAL_REGEXES: dict[str, list[re.Pattern[str]]] = {
        "MY_NUMBER": [
            re.compile(
                r"(?:\bmy number\b|\bindividual number\b|"
                r"\u30de\u30a4\u30ca\u30f3\u30d0\u30fc|\u500b\u4eba\u756a\u53f7)"
                r"\s*[:\uff1a#-]?\s*(?P<value>\d{4}[ -]?\d{4}[ -]?\d{4})",
                re.IGNORECASE,
            ),
        ],
        "DRIVER_LICENSE": [
            re.compile(
                r"(?:\bdriver'?s? license(?: number)?\b|"
                r"\bdriving license(?: number)?\b|"
                r"\u904b\u8ee2\u514d\u8a31(?:\u8a3c)?\u756a\u53f7|"
                r"\u514d\u8a31\u8a3c\u756a\u53f7)"
                r"\s*[:\uff1a#-]?\s*(?P<value>\d{12})",
                re.IGNORECASE,
            ),
        ],
        "PASSPORT_NUMBER": [
            re.compile(
                r"(?:\bpassport(?: number)?\b|"
                r"\btravel document(?: number)?\b|"
                r"\u30d1\u30b9\u30dd\u30fc\u30c8(?:\u756a\u53f7)?|"
                r"\u65c5\u5238\u756a\u53f7)"
                r"\s*[:\uff1a#-]?\s*(?P<value>[A-Z]{1,2}\d{6,8})",
                re.IGNORECASE,
            ),
        ],
        "BANK_ACCOUNT": [
            re.compile(
                r"(?:\bbank account(?: number)?\b|"
                r"\baccount number\b|"
                r"\u9280\u884c\u53e3\u5ea7(?:\u756a\u53f7)?|"
                r"\u53e3\u5ea7\u756a\u53f7|"
                r"\u666e\u901a\u9810\u91d1\u53e3\u5ea7(?:\u756a\u53f7)?|"
                r"\u5f53\u5ea7\u9810\u91d1\u53e3\u5ea7(?:\u756a\u53f7)?)"
                r"\s*[:\uff1a#-]?\s*(?P<value>\d{6,8})",
                re.IGNORECASE,
            ),
        ],
    }

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
        # Credit card: 13-19 digits, optionally separated by spaces or hyphens.
        # Presidio's built-in CreditCardRecognizer is en-only; register for ja too.
        credit_card_pattern = Pattern(
            name="credit_card_digits",
            regex=r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)",
            score=0.9,
        )
        # Japanese person name by honorific suffix (さん/様/氏/君/殿/先生 etc.)
        # spaCy NER often misses bare surnames like "鈴木" without context.
        jp_person_pattern = Pattern(
            name="jp_person_honorific",
            regex=r"[一-龥ァ-ヶー]{1,8}(?=さん|サン|様|さま|氏|君|くん|ちゃん|先生|殿)",
            score=0.85,
        )
        # Japanese address: 都道府県 + (郡)? + 市区町村 + 番地まで
        jp_address_pattern = Pattern(
            name="jp_address_full",
            regex=(
                r"(?:北海道|(?:京都|大阪)府|(?:東京)都|"
                r"[一-龥]{2,3}県)"
                r"(?:[一-龥]{1,8}郡)?"
                r"[一-龥ぁ-んァ-ヶa-zA-Z0-9]{1,15}?"
                r"(?:市|区|町|村)"
                r"[一-龥ぁ-んァ-ヶ]*"
                r"[0-9０-９\-ー―‐－]*"
            ),
            score=0.85,
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
            self._analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="CREDIT_CARD",
                    name=f"CreditCardRecognizer_{lang}",
                    patterns=[credit_card_pattern],
                    supported_language=lang,
                )
            )
            self._analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="LOCATION",
                    name=f"JpAddressRecognizer_{lang}",
                    patterns=[jp_address_pattern],
                    supported_language=lang,
                )
            )
            self._analyzer.registry.add_recognizer(
                PatternRecognizer(
                    supported_entity="PERSON",
                    name=f"JpPersonHonorificRecognizer_{lang}",
                    patterns=[jp_person_pattern],
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

    # Chars that make an entity match look "name-like": letters or CJK.
    _NAMELIKE_RE = re.compile(r"[A-Za-z\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]")

    def detect(
        self, text: str, language: str = "ja"
    ) -> list[RecognizerResult]:
        """Detect PII entities in the text."""
        results = self._analyzer.analyze(
            text=text,
            entities=self.TARGET_ENTITIES,
            language=language,
        )
        results.extend(self._detect_contextual_identifiers(text))
        # Drop PERSON/LOCATION matches that contain no letter/CJK character
        # (e.g., spaCy NER mislabeling "#" or other symbols as PERSON).
        filtered: list[RecognizerResult] = []
        for r in results:
            span = text[r.start:r.end]
            if r.entity_type in ("PERSON", "LOCATION") and not self._NAMELIKE_RE.search(span):
                continue
            filtered.append(r)
        return filtered

    @classmethod
    def _detect_contextual_identifiers(
        cls, text: str
    ) -> list[RecognizerResult]:
        """Detect Japan-specific identifiers when explicit surrounding context exists."""
        results: list[RecognizerResult] = []
        for entity_type, patterns in cls.CONTEXTUAL_REGEXES.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    value = match.group("value")
                    if not value:
                        continue
                    start = match.start("value")
                    end = match.end("value")
                    results.append(
                        RecognizerResult(
                            entity_type=entity_type,
                            start=start,
                            end=end,
                            score=0.95,
                        )
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
