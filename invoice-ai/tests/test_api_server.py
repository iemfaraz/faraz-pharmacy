"""API tests with a stubbed OCR engine (no PaddleOCR needed)."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api import server
from app.ocr.engine import OcrLine


def _line(text, x, y, conf=0.95):
    return OcrLine(text=text, confidence=conf,
                   bbox=[[x, y], [x + 200, y], [x + 200, y + 20], [x, y + 20]])


BILL = [
    _line("MEDI DISTRIBUTORS", 50, 10),
    _line("Invoice No: INV-2291", 50, 50),
    _line("Date: 12/10/2026", 50, 80),
    _line("Panadol 500mg Tablets", 50, 150), _line("10", 300, 150), _line("120.00", 400, 150), _line("1200.00", 500, 150),
    _line("Augmentin 625mg", 50, 190), _line("5", 300, 190), _line("450.00", 400, 190), _line("2250.00", 500, 190),
    _line("Total 3450.00", 50, 300),
]


class FakeEngine:
    def extract(self, image):
        return list(BILL)


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (600, 400), "white").save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "_get_engine", lambda: FakeEngine())
    monkeypatch.setattr(server, "_verify_owner_token", lambda t: None)
    return TestClient(server.app)


def post(client, data, headers=None, name="bill.png", ctype="image/png"):
    return client.post("/api/extract", files={"file": (name, data, ctype)},
                       headers={"Authorization": "Bearer tok"} if headers is None else headers)


def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_extract_png(client):
    r = post(client, _png())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vendor"]
    assert body["total"] == 3450.0
    assert body["invoice_number"] == "INV-2291"
    assert len(body["items"]) >= 1


def test_requires_bearer(client):
    assert post(client, _png(), headers={}).status_code == 401


def test_bad_token_rejected(monkeypatch):
    class R:
        status_code = 401
    monkeypatch.setattr(server.requests, "get", lambda *a, **k: R())
    server._token_cache.clear()
    c = TestClient(server.app)
    assert post(c, _png()).status_code == 401


def test_backend_unreachable_fails_closed(monkeypatch):
    def boom(*a, **k):
        raise server.requests.ConnectionError()
    monkeypatch.setattr(server.requests, "get", boom)
    server._token_cache.clear()
    c = TestClient(server.app)
    assert post(c, _png()).status_code == 503


def test_rejects_non_image(client):
    assert post(client, b"hello world not an image").status_code == 400


def test_rejects_oversize(client):
    assert post(client, b"\xff\xd8\xff" + b"0" * (server.MAX_BYTES + 10)).status_code == 413


def test_pdf_page_limit(client):
    import pymupdf
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page()
    assert post(client, doc.tobytes(), name="b.pdf", ctype="application/pdf").status_code == 400


def test_pdf_ok(client):
    import pymupdf
    doc = pymupdf.open()
    doc.new_page().insert_text((50, 50), "hello")
    r = post(client, doc.tobytes(), name="b.pdf", ctype="application/pdf")
    assert r.status_code == 200, r.text


def test_cors_origin_limited(client):
    ok = client.options("/api/extract", headers={
        "Origin": "https://iemfaraz.github.io",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization"})
    assert ok.headers.get("access-control-allow-origin") == "https://iemfaraz.github.io"
    bad = client.options("/api/extract", headers={
        "Origin": "https://evil.example",
        "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers
