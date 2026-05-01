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

    # Phase 2.1b: PL fleksja w aliasingu
    # Identyczne po normalize — False (caller exact-match path)
    assert ps._is_alias_of("Pawłem Górskim", "Paweł Górski") is False
    # Single-token alias single→multi po normalize
    assert ps._is_alias_of("Paweł", "Pawłem Górskim") is True
    # Różne formy fleksyjne tego samego imienia
    assert ps._is_alias_of("Pawła", "Pawłem Górskim") is True
    # Negative: różne osoby - "Anna" alias "Marek Kowalski"
    assert ps._is_alias_of("Anna", "Marek Kowalski") is False
    # Surname-only single token nie jest alias (pos 0 - bez surname rules)
    # 'Górskim' jako pos 0 token zostaje 'górskim', więc subsequence
    # ['górskim'] in ['paweł', 'górski'] → False (różne stringi)
    assert ps._is_alias_of("Górskim", "Paweł Górski") is False

    # Normalize sanity przez _normalize_for_match
    assert ps._normalize_for_match("Pawłem Górskim") == "paweł górski"
    assert ps._normalize_for_match("Paweł Górski") == "paweł górski"
    assert ps._normalize_for_match("Marii Skłodowskiej") == "maria skłodowska"
    assert ps._normalize_for_match("Anna Nowak") == "anna nowak"


# ── Phase 2.1a integration tests — Polish flexion detection ─────────────


def test_livestream_pawel_gorski_detection(monkeypatch):
    """Bug z livestreamu 2026-05-01: 'Pawłem Górskim' miss przez OPF.

    Phase 2.1a: regex_pl_inflected detector łapie. Mock OPF zwraca tylko
    'Anna Nowak' (mianownik) - OPF nie wykrywa form odmienionych. Po fixie
    'Pawłem Górskim' powinno być w detections.
    """
    # Tekst dokładnie z livestream screena (skrócony do 1 fragmentu)
    text = (
        "Cześć, tu Anna Nowak z kanału Marketing Garage. "
        "Rozmawiam z Pawłem Górskim, founderem startupu Brandbox."
    )

    # Pre-compute pozycji "Anna Nowak" w tekście dla mock spanu
    anna_start = text.index("Anna Nowak")
    anna_end = anna_start + len("Anna Nowak")
    fake_opf_spans = [
        {
            "label": "private_person",
            "start": anna_start,
            "end": anna_end,
            "text": "Anna Nowak",
            "placeholder": "<P>",
            "confidence": 0.9,
        },
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_opf_spans)
    result = pii_service.redact_text(text)

    osoba_texts = [d["text"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert "Anna Nowak" in osoba_texts, f"Anna Nowak miss. Got: {osoba_texts}"
    assert "Pawłem Górskim" in osoba_texts, (
        f"Pawłem Górskim NOT detected (Phase 2.1a regex_pl bug). Got: {osoba_texts}"
    )

    # Marketing Garage NIE jako OSOBA (blocklist)
    all_texts = [d["text"] for d in result["detections"]]
    assert "Marketing Garage" not in all_texts, (
        "Marketing Garage łapane jako PII (blocklist failure)"
    )

    # Brandbox NIE jako OSOBA (blocklist + context trigger 'startupu')
    assert "Brandbox" not in osoba_texts


def test_livestream_no_false_positives_brands(monkeypatch):
    """Phase 2.1a blocklist: brand tokens ('Sheriff Octopus', 'Marketing Garage',
    'Open Source') NIE łapane jako PERSON nawet gdy OPF nic nie zwraca."""
    pii_service = _mock_opf_with_spans(monkeypatch, [])
    text = (
        "Sheriff Octopus to nasza maskotka. "
        "Marketing Garage to nazwa kanału. "
        "Open Source software jest super."
    )
    result = pii_service.redact_text(text)
    osoba_texts = [d["text"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoba_texts == [], f"Brands łapane jako OSOBA: {osoba_texts}"


def test_phase2_1a_priority_opf_wins_overlap(monkeypatch):
    """OPF ma wyższy priority niż regex_pl_inflected. Gdy oba łapią tę samą
    osobę (np. 'Marek Kowalski' mianownik), OPF wygrywa - regex_pl
    duplikat odrzucany przez merge_with_opf_spans."""
    text = "Marek Kowalski przyszedł"
    fake_opf_spans = [
        {
            "label": "private_person",
            "start": 0,
            "end": 14,
            "text": "Marek Kowalski",
            "placeholder": "<P>",
            "confidence": 0.95,
        },
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_opf_spans)
    result = pii_service.redact_text(text)
    osoby = [d for d in result["detections"] if d["label"] == "OSOBA"]
    # Tylko 1 detection (OPF), nie 2 (OPF + regex_pl duplikat)
    assert len(osoby) == 1, f"Duplicate detection. Got: {osoby}"
    assert osoby[0]["source"] == "model"  # OPF wygrał, nie regex


# ── Phase 2.1b integration tests — Polish flexion ALIASING ──────────────


def test_alias_phase2_1b_pawlem_pawel_gorski(monkeypatch):
    """Phase 2.1b: 'Pawłem Górskim' (regex_pl) i 'Paweł Górski' (OPF mianownik)
    → ten sam <OSOBA_1>. Po normalize oba dają 'paweł górski'."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 12, "text": "Paweł Górski",
         "placeholder": "<P>", "confidence": 0.9},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Paweł Górski przyszedł. Wczoraj rozmawiałem z Pawłem Górskim."
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_phase2_1b_pawel_alone_alias(monkeypatch):
    """Phase 2.1b livestream case: sam 'Paweł' (OPF) alias 'Pawłem Górskim'
    (regex_pl) → ten sam <OSOBA_1>. Z [00:32] 'Paweł, opowiedz...'

    Single-token alias single→multi po normalize:
    'paweł' jest subsequence ['paweł', 'górski'] → True.
    """
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 5, "text": "Paweł",
         "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Paweł xxx Pawłem Górskim"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # OPF łapie sam "Paweł", regex_pl łapie "Pawłem Górskim", alias = ten sam id
    assert len(set(osoby)) == 1, f"Expected single placeholder, got: {osoby}"


def test_alias_phase2_1b_skłodowska_genitive(monkeypatch):
    """Phase 2.1b: 'Marii Skłodowskiej' (dopełniacz) alias 'Maria Skłodowska'
    (mianownik). Po normalize obie dają 'maria skłodowska'."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 16, "text": "Maria Skłodowska",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 22, "end": 40, "text": "Marii Skłodowskiej",
         "placeholder": "<P>", "confidence": 0.9},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Maria Skłodowska xxxxx Marii Skłodowskiej"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"


def test_alias_phase2_1b_no_collision_anna_ann(monkeypatch):
    """Phase 2.1b sanity (Codex P0): 'Ann' (nie w whitelist) NIE alias 'Anna'
    (whitelist). Stripping by dał 'Ann' i 'Ann' → fałszywie alias.
    Whitelist normalize zachowuje 'ann' bez zmian, 'anna' zostaje 'anna'.
    """
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 10, "text": "Anna Nowak",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 16, "end": 25, "text": "Ann Smith",
         "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Anna Nowak xxxx Ann Smith"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert len(set(osoby)) == 2, f"Anna i Ann to różni ludzie. Got: {osoby}"


def test_alias_phase2_1b_kowalski_brothers(monkeypatch):
    """Phase 2.1b sanity: 'Marek Kowalski' i 'Anna Kowalska' to różne osoby
    (różne rodzaje), pomimo że nazwiska są podobne. Po normalize
    'kowalski' vs 'kowalska' są różne tokeny."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Marek Kowalski",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 20, "end": 33, "text": "Anna Kowalska",
         "placeholder": "<P>", "confidence": 0.9},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Marek Kowalski xxxxx Anna Kowalska"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert len(set(osoby)) == 2, f"Got: {osoby}"


def test_alias_phase2_1b_pawel_homonym_ambiguous(monkeypatch):
    """Phase 2.1b sanity (Codex P0 #4): 'Paweł Kowalski' + 'Paweł Nowak' +
    sam 'Paweł'. Samotny 'Paweł' matchuje OBIE Pawły (ambiguous match),
    więc dostaje osobny <OSOBA_3> przez uniqueness check (Codex 7 fix).

    Phase 2.1b NIE zmienia tego kontraktu - PL fleksja respektuje uniqueness."""
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 14, "text": "Paweł Kowalski",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 20, "end": 31, "text": "Paweł Nowak",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 37, "end": 42, "text": "Paweł",
         "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Paweł Kowalski xxxxx Paweł Nowak xxxxx Paweł"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    # 3 unique placeholders! Sam "Paweł" nie wie do którego należy → osobny
    assert len(set(osoby)) == 3, f"Got: {osoby}"


def test_alias_phase2_1b_hyphenated_inflected(monkeypatch):
    """Phase 2.1b: hyphenated surname po odmianie. 'Górskim-Kowalskim'
    (narzędnik dwuczłonowego) alias 'Górski-Kowalski' (mianownik).

    Tokenizacja na separatorze '-' daje ['górskim', 'kowalskim'] vs
    ['górski', 'kowalski']. Per-position normalize: pos 0 ('górskim' nie
    w whitelist) zostaje, pos 1 ('kowalskim'→'kowalski') normalized.
    Hmm to nie zadziała perfectly bo pos 0 nazwiska po hyphen w drugiej
    pozycji multi-tokenowego tekstu...

    Faktycznie tekst 'Pan Jan Górskim-Kowalskim' tokenizuje na
    ['pan','jan','górskim','kowalskim']. Po stripie greetingu 'pan' →
    ['jan','górskim','kowalskim']. Pos 0='jan' (lookup), pos 1='górskim'
    (regex 'skim$'→'ski'), pos 2='kowalskim' (regex). Wynik:
    ['jan','górski','kowalski']. Match z 'Jan Górski-Kowalski' →
    ['jan','górski','kowalski']. ✅
    """
    fake_spans = [
        {"label": "private_person", "start": 0, "end": 19, "text": "Jan Górski-Kowalski",
         "placeholder": "<P>", "confidence": 0.9},
        {"label": "private_person", "start": 25, "end": 47, "text": "Janem Górskim-Kowalskim",
         "placeholder": "<P>", "confidence": 0.85},
    ]
    pii_service = _mock_opf_with_spans(monkeypatch, fake_spans)
    text = "Jan Górski-Kowalski xxxxx Janem Górskim-Kowalskim"
    result = pii_service.redact_text(text)
    osoby = [d["placeholder"] for d in result["detections"] if d["label"] == "OSOBA"]
    assert osoby == ["<OSOBA_1>", "<OSOBA_1>"], f"Got: {osoby}"
