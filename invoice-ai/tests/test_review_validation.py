"""Review-screen validation and upload validation logic."""
from app.review.screen import conf_icon, validate_amounts
from app.utils.files import validate_upload


def test_clean_receipt_no_warnings():
    assert validate_amounts(12.37, 1.02, 13.39, 12.37) == []


def test_discount_gap_warns():
    w = validate_amounts(937.0, 45.85, 980.0, 937.0)
    assert len(w) == 1 and "gap" in w[0]


def test_tiny_rounding_tolerated():
    assert validate_amounts(169.78, 0.0, 169.80, 169.78) == []


def test_items_mismatch_warns():
    w = validate_amounts(937.0, 45.85, 982.85, 1545.0)
    assert len(w) == 1 and "items" in w[0].lower()


def test_missing_values_silent():
    assert validate_amounts(None, None, 120.0, None) == []
    assert validate_amounts(None, None, None, 50.0) == []


def test_conf_icons():
    assert conf_icon(0.95) == "🟢"
    assert conf_icon(0.6) == "🟡"
    assert conf_icon(0.2) == "🔴"


def test_upload_validation():
    assert validate_upload("a.jpg", 1024).ok
    assert not validate_upload("a.exe", 1024).ok
    assert not validate_upload("a.png", 0).ok
    assert not validate_upload("a.pdf", 11 * 1024 * 1024).ok
