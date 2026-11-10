"""LLM layer: validation, merge, degradation — with mocked API."""
import os

import pytest

from app.extraction import llm
from app.extraction.rules import ExtractedFields
from app.ocr.engine import OcrLine


def _line():
    return OcrLine(text="x", confidence=0.9,
                   bbox=[[0, 0], [10, 0], [10, 10], [0, 10]])


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield


def test_no_key_returns_rules_untouched():
    rules = ExtractedFields(vendor="X", total=10.0,
                            confidence={"vendor": 0.9, "total": 0.9})
    assert llm.extract_with_llm([_line()], rules) is rules


def test_json_parsing_tolerance():
    assert llm._parse_json('{"vendor": "A"}') == {"vendor": "A"}
    assert llm._parse_json('```json\n{"vendor": "A"}\n```') == {"vendor": "A"}
    assert llm._parse_json('junk {"vendor": "A"} junk') == {"vendor": "A"}
    assert llm._parse_json('no json') is None
    assert llm._parse_json('[1,2]') is None


def test_validation_drops_garbage():
    ok = llm._validate({"vendor": "OJC MARKETING", "date": "2018-01-25",
                        "subtotal": 100.0, "tax": 6.0, "total": 106.0,
                        "currency": "myr"})
    assert ok["currency"] == "MYR" and ok["total"] == 106.0
    assert llm._validate({"vendor": "", "date": "25/01/2018",
                          "total": "lots", "tax": -5, "currency": "ringgit"}) == {}
    assert llm._validate({"subtotal": 5.0, "tax": 1.0, "total": 500.0}) \
        == {"total": 500.0}


def test_merge_and_disagreement(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    rules = ExtractedFields(vendor="tan chay yee", date="2018-01-25",
                            total=1169.8,
                            confidence={"vendor": 0.7, "date": 0.9, "total": 0.38})
    monkeypatch.setattr(llm, "_call_api",
                        lambda t: {"vendor": "OJC MARKETING SDN BHD",
                                   "date": "2018-01-25", "total": 169.80})
    out = llm.extract_with_llm([_line()], rules)
    assert out.vendor == "OJC MARKETING SDN BHD"
    assert out.confidence["date"] == llm.AGREE_CONF
    assert out.total == 169.80

    rules = ExtractedFields(total=980.0, confidence={"total": 0.95})
    monkeypatch.setattr(llm, "_call_api", lambda t: {"total": 982.85})
    out = llm.extract_with_llm([_line()], rules)
    assert out.total == 980.0 and out.confidence["total"] == 0.75


def test_api_failure_degrades(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    monkeypatch.setattr(llm, "_call_api", lambda t: None)
    rules = ExtractedFields(total=1.0, confidence={"total": 0.5})
    assert llm.extract_with_llm([_line()], rules).total == 1.0
