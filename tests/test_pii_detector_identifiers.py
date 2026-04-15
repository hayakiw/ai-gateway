"""Tests for additional Japan-specific identifier masking."""

from app.services.pii_detector import PiiDetector


def test_mask_my_number():
    detector = PiiDetector()
    text = "\u30de\u30a4\u30ca\u30f3\u30d0\u30fc: 1234 5678 9012"

    result = detector.mask(text, language="ja")

    assert "1234 5678 9012" not in result.masked_text
    assert "[MY_NUMBER_1]" in result.masked_text
    assert result.mapping["[MY_NUMBER_1]"] == "1234 5678 9012"


def test_mask_driver_license_number():
    detector = PiiDetector()
    text = "\u904b\u8ee2\u514d\u8a31\u8a3c\u756a\u53f7: 123456789012"

    result = detector.mask(text, language="ja")

    assert "123456789012" not in result.masked_text
    assert "[DRIVER_LICENSE_1]" in result.masked_text
    assert result.mapping["[DRIVER_LICENSE_1]"] == "123456789012"


def test_mask_passport_number():
    detector = PiiDetector()
    text = "\u30d1\u30b9\u30dd\u30fc\u30c8\u756a\u53f7: TK1234567"

    result = detector.mask(text, language="ja")

    assert "TK1234567" not in result.masked_text
    assert "[PASSPORT_1]" in result.masked_text
    assert result.mapping["[PASSPORT_1]"] == "TK1234567"


def test_mask_bank_account_number():
    detector = PiiDetector()
    text = "\u53e3\u5ea7\u756a\u53f7: 1234567"

    result = detector.mask(text, language="ja")

    assert "1234567" not in result.masked_text
    assert "[BANK_ACCOUNT_1]" in result.masked_text
    assert result.mapping["[BANK_ACCOUNT_1]"] == "1234567"


def test_do_not_mask_unlabeled_12_digit_number():
    detector = PiiDetector()
    text = "Order code 123456789012 should stay as-is."

    result = detector.mask(text, language="ja")

    assert result.masked_text == text
    assert result.mapping == {}
