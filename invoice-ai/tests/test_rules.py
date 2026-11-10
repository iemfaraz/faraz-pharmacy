"""Field extraction: every bug found during Milestone 5 stays fixed."""
from app.extraction.rules import (
    DATE_HINT_RE, TOTAL_KEYWORDS, _amounts_in, _has_kw, _parse_date,
    extract_fields,
)


def test_pinewood_real_ocr_rows(L):
    """The exact rows the debugger dumped: split total row, glued date."""
    r = extract_fields([
        L("Pinewood", 298), L("Pinewood Cafe+Kitchen", 360),
        L("Involce No:454370 - 30Jul202603:28PM", 540),
        L("Subtotal 937.00", 867), L("VAT 5% 45.85", 895),
        L("Total: 2.00", 938), L("BDT980.00", 960),
        L("PAID980BDT", 993), L("Cash Received BDT1000.00", 1029),
    ])
    assert r.total == 980.0
    assert r.date == "2026-07-30"
    assert r.subtotal == 937.0 and r.tax == 45.85
    assert r.currency == "BDT"


def test_beefaroo_with_damaged_total_keyword(L):
    r = extract_fields([
        L("Beef-a-Roo", 40), L("Order #130", 140),
        L("Subtotal", 320), L("12.37", 320, x=300),
        L("Tax", 340), L("1.02", 340, x=300),
        L("To Go Tota1", 370), L("13.39", 370, x=300),
        L("Cash", 400), L("20.00", 400, x=300),
    ])
    assert r.total == 13.39 and r.subtotal == 12.37 and r.tax == 1.02


def test_bfc_payable_and_glued_vendor_noise(L):
    r = extract_fields([
        L("BFC TOKEN #B272-TO", 40), L("TakeOut.Self0", 60),
        L("Best Fried Chicken (BFC)", 90),
        L("DATE : 19-07-26,", 200),
        L("Payable:", 350), L("325.00", 350, x=300),
        L("VAT", 420), L("15.48", 420, x=300),
    ])
    assert r.vendor == "Best Fried Chicken (BFC)"
    assert r.total == 325.0 and r.tax == 15.48
    assert r.date == "2026-07-19"


def test_speedmart_subtotal_total_conflict(L):
    r = extract_fields([
        L("99 SPEED MART S/B (519537-X)", 40),
        L("Total Sales (Inclusive GST) RM", 300), L("169.78", 300, x=300),
        L("Rounding RM", 340), L("169.80", 340, x=300),
        L("CASH RM", 360), L("200.00", 360, x=300),
    ])
    assert r.subtotal == 169.78 and r.total == 169.80


def test_juices_glued_year_time(L):
    r = extract_fields([
        L("JUICES N CHILLS", 40),
        L("Date29-Mar-2301:0734PM", 130),
        L("TOTAL:", 300), L("120.00", 300, x=300),
    ])
    assert r.date == "2023-03-29" and r.total == 120.0


def test_keyword_word_boundaries():
    assert _has_kw("Subtotal 12.37", TOTAL_KEYWORDS) is None
    assert _has_kw("To Go Total", TOTAL_KEYWORDS) == "total"
    assert _has_kw("T0TAL:", TOTAL_KEYWORDS) == "total"


def test_amount_parsing_guards():
    assert _amounts_in("Order #130") == []            # order numbers
    assert _amounts_in("5pc Chicken Strip") == []      # glued units
    assert _amounts_in("BDT980.00") == [980.0]         # glued currency
    assert _amounts_in("RM117.90") == [117.9]
    assert _amounts_in("TOTAL 1,234.50") == [1234.5]   # thousands


def test_date_variants():
    for raw, want in [("30Jul2026", "2026-07-30"), ("29-Mar-23", "2023-03-29"),
                      ("19-07-26", "2026-07-19"), ("02/20/2020", "2020-02-20"),
                      ("Date29-Mar-2301:0734PM", "2023-03-29")]:
        m = DATE_HINT_RE.search(raw)
        assert m, raw
        assert _parse_date(m.group(0)) == want, raw
