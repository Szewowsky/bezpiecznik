"""
Tests for FastAPI server contract — Codex 3.1 fix.

Verifies API shape without loading OPF (mocking get_model for speed).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _mock_opf_redact(text: str) -> MagicMock:
    """Mock OPF that returns no detections — testy regex layer + shape."""
    result = MagicMock()
    result.to_dict.return_value = {"detected_spans": []}
    return result


@pytest.fixture
def client():
    """TestClient z mocked OPF (żeby nie ładować modelu 3GB w testach)."""
    with patch("opf_runtime.get_model") as mock_get:
        mock_model = MagicMock()
        mock_model.redact.side_effect = _mock_opf_redact
        mock_get.return_value = mock_model
        from server import app

        yield TestClient(app)


def test_redact_shape_with_regex_pii(client):
    """API zwraca poprawny shape z regex-owym IBAN/NIP."""
    text = "Konto: 12 1140 2004 0000 3502 1234 5678. NIP 5252839110."
    r = client.post("/api/redact", json={"text": text})
    assert r.status_code == 200
    data = r.json()
    assert "detections" in data
    assert "redacted_text" in data
    assert len(data["detections"]) >= 2  # IBAN + NIP

    for d in data["detections"]:
        assert {"label", "text", "placeholder", "source", "start", "end"} <= d.keys()
        assert d["source"] in ("model", "regex")
        assert d["label"] in {"OSOBA", "EMAIL", "TELEFON", "ADRES", "URL", "DATA",
                              "SEKRET", "IBAN", "NIP", "PESEL", "KOD"}


def test_placeholders_numbered_sequentially(client):
    """Placeholdery są numerowane per label w kolejności występowania."""
    text = "NIP 5252839110, drugi NIP: 9512345670"
    r = client.post("/api/redact", json={"text": text})
    assert r.status_code == 200
    nips = [d for d in r.json()["detections"] if d["label"] == "NIP"]
    assert len(nips) == 2
    assert nips[0]["placeholder"] == "<NIP_1>"
    assert nips[1]["placeholder"] == "<NIP_2>"


def test_empty_text_returns_400(client):
    assert client.post("/api/redact", json={"text": ""}).status_code == 400
    assert client.post("/api/redact", json={"text": "   "}).status_code == 400


def test_static_root_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Bezpiecznik" in r.text


def test_static_css_accessible(client):
    r = client.get("/styles.css")
    assert r.status_code == 200


def test_redacted_text_uses_new_placeholders(client):
    """redacted_text ma <NIP_1>, nie generyczne <NIP>."""
    text = "NIP 5252839110"
    r = client.post("/api/redact", json={"text": text})
    assert r.status_code == 200
    assert "<NIP_1>" in r.json()["redacted_text"]


def test_canonical_dedup_substring(monkeypatch):
    """Marek Kowalski + Marek = ten sam <OSOBA_1> (substring dedup)."""
    from unittest.mock import MagicMock

    import pii_service

    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 20, "end": 35, "text": "Robert Szewczyk", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 40, "end": 46, "text": "Robert", "placeholder": "<P>", "confidence": 0.8},
        {"label": "private_person", "start": 50, "end": 55, "text": "Marek", "placeholder": "<P>", "confidence": 0.8},
    ]
    fake_opf = MagicMock()
    fake_opf.redact.return_value.to_dict.return_value = {"detected_spans": fake_spans}
    monkeypatch.setattr(pii_service, "get_model", lambda: fake_opf)
    # filter_false_person_spans nic nie odfiltruje (brak słów-kluczy PII w testowych imionach)

    # Tekst musi mieć dokładnie te pozycje 0..55 — sztuczny ale spójny
    text = "Marek Kowalski xxxxx Robert Szewczyk xxx Robert xxx Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # 4 wystąpienia, ale tylko 2 unique placeholders: Marek Kowalski/Marek = OSOBA_1, Robert Szewczyk/Robert = OSOBA_2
    assert osoby[0] == "<OSOBA_1>"  # Marek Kowalski
    assert osoby[1] == "<OSOBA_2>"  # Robert Szewczyk
    assert osoby[2] == "<OSOBA_2>"  # Robert (alias Szewczyka)
    assert osoby[3] == "<OSOBA_1>"  # Marek (alias Kowalskiego)
    assert len(set(osoby)) == 2


# ── Helpers dla nowych testów aliasing-uniqueness/edge cases ────────────────

def _mock_opf_with_spans(monkeypatch, fake_spans):
    """Helper: monkeypatch get_model żeby zwracał OPF z fake spanami."""
    from unittest.mock import MagicMock

    import pii_service

    fake_opf = MagicMock()
    fake_opf.redact.return_value.to_dict.return_value = {"detected_spans": fake_spans}
    monkeypatch.setattr(pii_service, "get_model", lambda: fake_opf)
    return pii_service


def test_alias_strip_cześć_prefix(monkeypatch):
    """'Cześć Robert' alias 'Robert Szewczyk' (single match po stripie greetingu)."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 15, "text": "Robert Szewczyk", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 42, "text": "Cześć Robert", "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Robert Szewczyk xxxxxxxxxxxxxx Cześć Robert"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # Oba <OSOBA_1> — 'Cześć Robert' jest aliasem Robert Szewczyk
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_uniqueness_two_marek(monkeypatch):
    """Codex 7 fix: 'Marek' nie aliasem żadnego z 'Marek Kowalski' i 'Marek Nowak'.
    Powinien dostać osobny <OSOBA_3> (ambiguous match → nowy canonical)."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 20, "end": 31, "text": "Marek Nowak", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 40, "end": 45, "text": "Marek", "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxxxx Marek Nowak xxxxxxx Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # 3 unique placeholders! Marek nie wie do którego z 2 należy → osobny
    assert len(set(osoby)) == 3, f"Got: {osoby}"
    assert osoby[0] == "<OSOBA_1>"
    assert osoby[1] == "<OSOBA_2>"
    assert osoby[2] == "<OSOBA_3>"


def test_alias_single_marek_still_dedups(monkeypatch):
    """Sanity: jeśli jest 1 'Marek X', alias 'Marek' powinien się spiąć."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 20, "end": 25, "text": "Marek", "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxxxx Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_subsequence_not_subset(monkeypatch):
    """Subset by przepuścił wymieszane tokeny. Subsequence wymaga kolejności."""
    # 'Robert Marek' NIE jest subsequence 'Marek Kowalski Robert' (tokeny w innej kolejności)
    # Stary subset by spiął bo {robert,marek} ⊆ {marek,kowalski,robert}
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 22, "text": "Marek Kowalski Robert", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 42, "text": "Robert Marek", "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski Robert xxxxxxx Robert Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # Powinny być 2 różne placeholders
    assert len(set(osoby)) == 2, f"Got: {osoby}"


def test_alias_pozdrawiam_suffix(monkeypatch):
    """'Pozdrawiam, Marek' (OPF łapie razem) alias 'Marek Kowalski'."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 47, "text": "Pozdrawiam, Marek", "placeholder": "<P>", "confidence": 0.8},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxxxxxxxxxxxxx Pozdrawiam, Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_em_dash_separator(monkeypatch):
    """Em-dash w stripie: 'Pozdrawiam — Marek' → alias 'Marek Kowalski'."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 46, "text": "Pozdrawiam — Marek", "placeholder": "<P>", "confidence": 0.8},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxxxxxxxxxxxxx Pozdrawiam — Marek"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_polish_quotes(monkeypatch):
    """Polskie cudzysłowy U+201E (otwierający) i U+201D (zamykający) w stripie."""
    quoted = '„Cześć, Robert”'  # „Cześć, Robert"
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Robert Szewczyk", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 30 + len(quoted), "text": quoted, "placeholder": "<P>", "confidence": 0.8},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = f"Robert Szewczyk xxxxxxxxxxxxxx {quoted}"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_does_not_modify_spans(monkeypatch):
    """Codex 2.2: span 'Cześć Robert' zostaje w detections z text='Cześć Robert',
    start/end nietknięte. apply_redaction działa na oryginalnych pozycjach."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 12, "text": "Cześć Robert", "placeholder": "<P>", "confidence": 0.9},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Cześć Robert xxx"
    result = pii_service.redact_text(text)
    # Span ma OYGINALNY text, nie pociętą wersję
    d = result["detections"][0]
    assert d["text"] == "Cześć Robert"
    assert d["start"] == 0
    assert d["end"] == 12
    # redacted_text zastępuje oryginalny zakres jednym placeholderem
    assert result["redacted_text"] == "<OSOBA_1> xxx"


def test_alias_multi_strip_iteration(monkeypatch):
    """'Cześć, Drogi Robert' → strip 'cześć' + 'drogi' → 'robert' → alias 'Robert Szewczyk'."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 15, "text": "Robert Szewczyk", "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 30, "end": 49, "text": "Cześć, Drogi Robert", "placeholder": "<P>", "confidence": 0.8},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Robert Szewczyk xxxxxxxxxxxxxx Cześć, Drogi Robert"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_address_regex_pl_street(client):
    """Polski adres 'ul. Słoneczna 12/4' → ADRES przez regex layer."""
    text = "Mój adres: ul. Słoneczna 12/4, 00-001 Warszawa."
    r = client.post("/api/redact", json={"text": text})
    assert r.status_code == 200
    labels = [d["label"] for d in r.json()["detections"]]
    assert "ADRES" in labels


def test_address_regex_pl_aleje(client):
    """'Aleje Jerozolimskie 100' → ADRES (regex łapie nawet bez OPF)."""
    text = "Biuro: Aleje Jerozolimskie 100, 00-807 Warszawa."
    r = client.post("/api/redact", json={"text": text})
    assert r.status_code == 200
    addresses = [d["text"] for d in r.json()["detections"] if d["label"] == "ADRES"]
    assert any("Jerozolimskie" in a for a in addresses)


def test_reclassify_aleje_from_person(monkeypatch):
    """OPF zwraca 'Aleje Jerozolimskie' jako PERSON → reklasyfikujemy na ADRES."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 19, "text": "Aleje Jerozolimskie", "placeholder": "<P>", "confidence": 0.7},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Aleje Jerozolimskie xxx"
    result = pii_service.redact_text(text)
    labels = [d["label"] for d in result["detections"]]
    # Po reklasyfikacji + regex layer: ADRES powinien się pojawić, OSOBA znika
    assert "ADRES" in labels
    assert "OSOBA" not in labels


def test_reclassify_does_not_touch_real_persons(monkeypatch):
    """Sanity: 'Marek Kowalski' zostaje OSOBA, nie ADRES."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski", "placeholder": "<P>", "confidence": 0.9},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxx"
    result = pii_service.redact_text(text)
    labels = [d["label"] for d in result["detections"]]
    assert "OSOBA" in labels
    assert "ADRES" not in labels


def test_alias_helpers_unit():
    """Unit test dla _strip_edge_stopwords i _is_alias_of (bez OPF mocka)."""
    import pii_service as ps

    # Strip greetingów
    assert ps._strip_edge_stopwords(["cześć", "robert"]) == ["robert"]
    assert ps._strip_edge_stopwords(["pozdrawiam", "marek"]) == ["marek"]
    assert ps._strip_edge_stopwords(["cześć", "drogi", "robert"]) == ["robert"]
    assert ps._strip_edge_stopwords(["dzień", "dobry", "robert"]) == ["robert"]
    # Sam greeting → pusta lista
    assert ps._strip_edge_stopwords(["cześć"]) == []
    # Nic do strippowania
    assert ps._strip_edge_stopwords(["marek", "kowalski"]) == ["marek", "kowalski"]

    # Alias check
    assert ps._is_alias_of("Marek", "Marek Kowalski") is True
    assert ps._is_alias_of("Cześć Robert", "Robert Szewczyk") is True
    assert ps._is_alias_of("Pozdrawiam, Marek", "Marek Kowalski") is True
    # NIE alias — różne tokeny
    assert ps._is_alias_of("Tomek", "Marek Kowalski") is False
    # Identyczne — False (caller obsługuje exact match osobno)
    assert ps._is_alias_of("Marek Kowalski", "Marek Kowalski") is False
    # Kolejność tokenów ma znaczenie (subsequence != subset)
    assert ps._is_alias_of("Kowalski Marek", "Marek Kowalski") is False
