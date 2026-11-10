"""Line-item extraction: the five real-receipt layouts."""
from app.extraction.tables import extract_table


def test_pinewood_split_names_and_rows(L):
    t = extract_table([
        L("Pinewood Cafe+Kitchen", 360),
        L("Item Description Qty Price T.Price", 641),
        L("SMOKED CHICKEN", 673), L("SANDWICH 339 339", 694),
        L("CHICKEN CHEESE T 309", 727), L("BURGER 309", 748),
        L("MILK SHAKE 1 269 269", 783),
        L("BOTTLE OF WATER", 811), L("20 20", 832),
        L("Subtotal 937.00", 867),
    ])
    assert len(t.items) == 4
    assert abs(sum(i.line_total for i in t.items) - 937.0) < 0.01
    assert not t.flags
    descs = [i.description for i in t.items]
    assert "SMOKED CHICKEN" in descs[0] and "SANDWICH" in descs[0]
    assert "BURGER" in descs[1]


def test_beefaroo_modifiers(L):
    t = extract_table([
        L("Beef-a-Roo", 40),
        L("5pc Chicken Strip", 240), L("6.29", 240, x=300),
        L("Ranch", 255), L("Buffalo Sauce", 268),
        L("Onion Rings", 285), L("3.09", 285, x=300),
        L("Large Fry", 300), L("2.99", 300, x=300),
        L("Subtotal", 320), L("12.37", 320, x=300),
    ])
    assert [i.description for i in t.items][0] == \
        "5pc Chicken Strip (Ranch) (Buffalo Sauce)"
    assert len(t.items) == 3 and not t.flags


def test_bfc_integer_amounts(L):
    t = extract_table([
        L("Best Fried Chicken (BFC)", 90),
        L("Description", 230), L("Qty", 230, x=250), L("Amount", 230, x=300),
        L("Garlic Wrap", 260), L("1", 260, x=250), L("220", 260, x=300),
        L("Coleslaw", 300), L("1", 300, x=250), L("75", 300, x=300),
        L("Payable:", 350), L("295.00", 350, x=300),
    ])
    assert len(t.items) == 2
    assert sum(i.line_total for i in t.items) == 295.0


def test_juices_values_below_name(L):
    t = extract_table([
        L("JUICES N CHILLS", 40),
        L("Item", 210), L("Qty", 210, x=150), L("Amt.", 210, x=300),
        L("Fruit Chat", 240),
        L("1", 260, x=150), L("120.00", 260, x=300),
        L("TOTAL:", 300), L("120.00", 300, x=300),
    ])
    assert len(t.items) == 1
    assert t.items[0].description == "Fruit Chat"
    assert t.items[0].line_total == 120.0


def test_speedmart_codes_and_sum_flag(L):
    t = extract_table([
        L("99 SPEED MART S/B (519537-X)", 40),
        L("2973 PLDIASURE COMPLETE 53S", 210), L("RM117.90 s", 210, x=300),
        L("069 WILD 2KG", 230), L("RM34.90 s", 230, x=300),
        L("Total Sales (Inclusive GST) RM", 300), L("169.78", 300, x=300),
    ])
    assert t.items[0].line_total == 117.9
    assert t.flags  # partial items vs printed total must flag
