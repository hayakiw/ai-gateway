"""Tests for PII detection and masking."""

import pytest

from app.services.pii_detector import PiiDetector


@pytest.fixture(scope="module")
def detector():
    return PiiDetector()


class TestPiiDetection:
    def test_detect_email(self, detector: PiiDetector):
        text = "メールアドレスは test@example.com です"
        results = detector.detect(text, language="ja")
        entity_types = [r.entity_type for r in results]
        assert "EMAIL_ADDRESS" in entity_types

    def test_detect_person_japanese(self, detector: PiiDetector):
        text = "田中太郎さんに連絡してください"
        results = detector.detect(text, language="ja")
        entity_types = [r.entity_type for r in results]
        assert "PERSON" in entity_types

    def test_no_pii(self, detector: PiiDetector):
        text = "今日はいい天気です"
        result = detector.mask(text, language="ja")
        assert result.masked_text == text
        assert result.mapping == {}


class TestPiiMasking:
    def test_mask_email(self, detector: PiiDetector):
        text = "メールは test@example.com です"
        result = detector.mask(text, language="ja")
        assert "test@example.com" not in result.masked_text
        assert "[EMAIL_1]" in result.masked_text
        assert result.mapping["[EMAIL_1]"] == "test@example.com"

    def test_mask_multiple_entities(self, detector: PiiDetector):
        text = "田中さんのメールは tanaka@example.com で、佐藤さんは sato@example.com です"
        result = detector.mask(text, language="ja")
        assert "tanaka@example.com" not in result.masked_text
        assert "sato@example.com" not in result.masked_text
        assert len(result.mapping) >= 2

    def test_mask_preserves_non_pii(self, detector: PiiDetector):
        text = "メールは test@example.com です。よろしくお願いします。"
        result = detector.mask(text, language="ja")
        assert "よろしくお願いします" in result.masked_text


class TestUnmasking:
    def test_unmask_restores_original(self, detector: PiiDetector):
        text = "田中さんのメールは test@example.com です"
        result = detector.mask(text, language="ja")
        unmasked = detector.unmask(result.masked_text, result.mapping)
        # All original PII values should be restored
        assert "test@example.com" in unmasked

    def test_unmask_empty_mapping(self, detector: PiiDetector):
        text = "今日はいい天気です"
        unmasked = detector.unmask(text, {})
        assert unmasked == text

    def test_roundtrip(self, detector: PiiDetector):
        original = "連絡先: user@test.com"
        masked_result = detector.mask(original, language="ja")
        restored = detector.unmask(masked_result.masked_text, masked_result.mapping)
        assert "user@test.com" in restored


class TestStreamUnmasker:
    def test_single_chunk(self, detector: PiiDetector):
        mapping = {"[PERSON_1]": "田中", "[EMAIL_1]": "test@example.com"}
        unmasker = detector.create_stream_unmasker(mapping)
        result = unmasker.feed("[PERSON_1]さんのメールは[EMAIL_1]です")
        result += unmasker.flush()
        assert "田中" in result
        assert "test@example.com" in result

    def test_split_placeholder(self, detector: PiiDetector):
        """Placeholder split across two chunks."""
        mapping = {"[PERSON_1]": "田中"}
        unmasker = detector.create_stream_unmasker(mapping)

        part1 = unmasker.feed("こんにちは[PERS")
        part2 = unmasker.feed("ON_1]さん")
        part3 = unmasker.flush()
        full = part1 + part2 + part3

        assert "田中" in full
        assert "[PERSON_1]" not in full

    def test_no_mapping(self, detector: PiiDetector):
        unmasker = detector.create_stream_unmasker({})
        result = unmasker.feed("普通のテキスト")
        result += unmasker.flush()
        assert result == "普通のテキスト"

    def test_bracket_not_placeholder(self, detector: PiiDetector):
        """Text with [ that is not a placeholder should eventually flush."""
        mapping = {"[PERSON_1]": "田中"}
        unmasker = detector.create_stream_unmasker(mapping)

        part1 = unmasker.feed("配列は[0]です")
        part2 = unmasker.flush()
        full = part1 + part2

        assert "配列は[0]です" == full
