"""
PII Service — wspólny pipeline redakcji używany przez Gradio (app.py) i FastAPI (server.py).

Mapuje wewnętrzne etykiety (private_person, iban, ...) na polskie z frontu (OSOBA, IBAN, ...),
numeruje placeholdery per label po merge/dedupe (kolejność określa numerację).
"""

from __future__ import annotations

import re

from opf_runtime import get_model
from pii_regex import (
    apply_redaction,
    filter_false_person_spans,
    find_pii,
    find_polish_inflected_persons,
    merge_with_opf_spans,
    reclassify_address_persons,
)

# Greetingi i zakończenia maila — token-level stopwordy używane TYLKO przy
# porównaniu aliasów PERSON. NIE modyfikujemy spanów, NIE zmieniamy
# redacted_text — wpływ tylko na decyzję dedupową w _assign_canonical_ids.
PERSON_ALIAS_STOPWORDS = frozenset({
    "cześć", "witaj", "witajcie", "witam", "hej", "hejka", "heja", "yo",
    "drogi", "droga", "drodzy", "kochany", "kochana", "kochani",
    "szanowny", "szanowna", "szanowni",
    "pozdrawiam", "pozdrawiamy", "pozdrowienia",
    "dzięki", "dziękuję", "dziękujemy",
    "serdecznie", "ps",
})

# Multi-token stopwordy — sprawdzane jako contiguous sequences PRZED singletonami.
PERSON_ALIAS_STOPWORD_PHRASES: tuple[tuple[str, ...], ...] = (
    ("dzień", "dobry"),
    ("dobry", "wieczór"),
    ("z", "poważaniem"),
    ("z", "wyrazami", "szacunku"),
    ("do", "zobaczenia"),
)

# Bogaty separator set: whitespace, NBSP, polska interpunkcja, cudzysłowy,
# myślniki (zwykły / en-dash / em-dash), wielokropek, nawiasy.
_TOKEN_SPLIT = re.compile(
    r"[\s ,.!?:;\-–—…\"'„”“‘’«»()\[\]{}/\\]+",
    re.UNICODE,
)

# Mapping: backend label → polski label frontu (matching window.LABEL_META in web/data.jsx)
LABEL_MAP: dict[str, str] = {
    "private_person": "OSOBA",
    "private_email": "EMAIL",
    "private_phone": "TELEFON",
    "private_address": "ADRES",
    "private_url": "URL",
    "private_date": "DATA",
    "secret": "SEKRET",
    "iban": "IBAN",
    "nip": "NIP",
    "pesel": "PESEL",
    "postal_code": "KOD",
}


def _normalize_source(raw: str) -> str:
    """
    Front oczekuje 'regex' | 'model'.
    Backend: pii_regex zwraca 'regex:iban_pl', OPF zwraca 'opf' (po dorzuceniu).
    """
    if not raw:
        return "model"
    return "regex" if raw.startswith("regex") else "model"


def _tokenize_for_alias(text: str) -> list[str]:
    """Casefold + split na bogatym separator set."""
    if not text:
        return []
    return [t for t in _TOKEN_SPLIT.split(text.casefold()) if t]


def _strip_edge_stopwords(tokens: list[str]) -> list[str]:
    """
    Iteratywnie ścina greeting/closing stopwordy z OBYDWU brzegów.
    Multi-token phrases ('dzień dobry') sprawdzane PRZED singletonami żeby nie
    konsumować kawałków phrase'a osobno.

    NIE modyfikuje spanów — operuje tylko na liście tokenów porównywanych
    w _is_alias_of i _normalize_for_match.
    """
    t = list(tokens)
    changed = True
    while changed and t:
        changed = False
        # Lewy brzeg: phrase first
        for phrase in PERSON_ALIAS_STOPWORD_PHRASES:
            n = len(phrase)
            if len(t) >= n and tuple(t[:n]) == phrase:
                t = t[n:]
                changed = True
                break
        if changed:
            continue
        # Lewy brzeg: singleton
        if t and t[0] in PERSON_ALIAS_STOPWORDS:
            t = t[1:]
            changed = True
            continue
        # Prawy brzeg: phrase first
        for phrase in PERSON_ALIAS_STOPWORD_PHRASES:
            n = len(phrase)
            if len(t) >= n and tuple(t[-n:]) == phrase:
                t = t[:-n]
                changed = True
                break
        if changed:
            continue
        # Prawy brzeg: singleton
        if t and t[-1] in PERSON_ALIAS_STOPWORDS:
            t = t[:-1]
            changed = True
    return t


def _normalize_for_match(text: str) -> str:
    """
    Tokenize → strip edge stopwords → join. Używane do exact-match porównania
    w _assign_canonical_ids. Bezpieczne — nie wpływa na spany ani redaction.
    """
    return " ".join(_strip_edge_stopwords(_tokenize_for_alias(text)))


def _is_alias_of(short: str, canonical: str) -> bool:
    """
    Czy `short` to alias `canonical`?

    Po stripie edge stopwordów: True gdy short jest CONTIGUOUS SUBSEQUENCE
    canonical tokens. Subset by przepuścił 'Robert Marek' alias 'Marek Robert
    Kowalski' (token kolejność dowolna) — subsequence wymaga kolejności.

    Identyczne (po normalizacji) → False (caller obsługuje exact-match osobno).

    Polska fleksja ('Tomkiem' vs 'Tomek') nie jest obsługiwana — Phase 2 ze
    spaCy / morfologicznym lemmatyzerem.
    """
    s = _strip_edge_stopwords(_tokenize_for_alias(short))
    c = _strip_edge_stopwords(_tokenize_for_alias(canonical))
    if not s or not c or s == c:
        return False
    n = len(s)
    if n > len(c):
        return False
    for i in range(len(c) - n + 1):
        if c[i : i + n] == s:
            return True
    return False


def _assign_canonical_ids(merged: list[dict]) -> list[int]:
    """
    Dla każdego spanu zwraca canonical_id (int), wspólny dla wszystkich spanów
    odnoszących się do tej samej encji w obrębie label.

    Algorytm: najdłuższy tekst per label = canonical, krótsze są aliasami gdy
    ich tokeny są podzbiorem tokenów canonical. Identyczne teksty (case-insensitive)
    dostają ten sam id.
    """
    canonical_ids: list[int] = [0] * len(merged)
    # Per label: lista (canonical_id, normalized_text) — najdłuższe pierwsze
    canonicals_by_label: dict[str, list[tuple[int, str, str]]] = {}
    next_id = 0

    # Sortuj spany malejąco po liczbie tokenów PO stripie greetingów —
    # NIE po surowej długości. Inaczej "Pozdrawiam, Marek" (17 chars) bije
    # "Marek Kowalski" (14 chars) i staje się canonical zamiast aliasem.
    def _sort_key(item):
        idx, span = item
        stripped = _strip_edge_stopwords(_tokenize_for_alias(span.get("text", "")))
        return (-len(stripped), -len(span.get("text", "")), span.get("start", 0))

    indexed = sorted(enumerate(merged), key=_sort_key)

    for orig_idx, span in indexed:
        label = span.get("label", "unknown")
        text = span.get("text", "")
        norm = _normalize_for_match(text)
        existing = canonicals_by_label.setdefault(label, [])

        # Codex 7 fix: uniqueness check — alias matchuje canonical TYLKO gdy
        # pasuje do dokładnie 1 z istniejących. Ambiguity ('Marek' pasujący
        # do 'Marek Kowalski' i 'Marek Nowak') → osobny canonical_id, nie
        # arbitralny merge.
        matches: list[int] = []
        for cid, c_norm, c_text in existing:
            if norm and norm == c_norm:
                matches.append(cid)
            elif _is_alias_of(text, c_text):
                matches.append(cid)
        unique_matches = list(set(matches))

        if len(unique_matches) == 1:
            matched_id = unique_matches[0]
        else:
            # 0 matchów (nowa encja) LUB >1 matchów (ambiguous) → nowy id
            next_id += 1
            existing.append((next_id, norm, text))
            matched_id = next_id

        canonical_ids[orig_idx] = matched_id

    return canonical_ids


def redact_text(text: str) -> dict:
    """
    Pełen pipeline redakcji: OPF + filter PERSON false positives + regex PL + merge + numeracja.

    Returns:
        {
            "detections": [
                {label, text, placeholder, source, start, end, confidence}, ...
            ],
            "redacted_text": "<OSOBA_1> ..."
        }
    """
    if not text or not text.strip():
        return {"detections": [], "redacted_text": ""}

    model = get_model()
    opf_result = model.redact(text).to_dict()

    opf_spans = filter_false_person_spans(opf_result["detected_spans"])
    # Reklasyfikator: 'Aleje Jerozolimskie' jako PERSON → ADRES
    opf_spans = reclassify_address_persons(opf_spans)

    # Phase 2.1a: dołożony detector polskich form odmienionych imion+nazwisk.
    # OPF nie łapie "Pawłem Górskim", "Anną Nowak" - whitelist+regex naprawia.
    # Filter PII keywords (np. "Konta Pawłem") + reclassify (np. "ul. Marka").
    pl_inflected = find_polish_inflected_persons(text)
    pl_inflected = filter_false_person_spans(pl_inflected)
    pl_inflected = reclassify_address_persons(pl_inflected)
    opf_spans = opf_spans + pl_inflected

    regex_spans = find_pii(text)
    merged = merge_with_opf_spans(opf_spans, regex_spans)
    merged.sort(key=lambda s: s["start"])

    # Pre-numeracja: dedup w obrębie kategorii. Spany odnoszące się do tej samej
    # encji (np. "Marek Kowalski" i "Marek") dostają ten sam placeholder.
    # Heurystyka: najdłuższy tekst danego label = canonical, krótsze = aliasy
    # gdy są substringiem canonical (case-insensitive, word-boundary).
    canonical_id_per_span: list[int] = _assign_canonical_ids(merged)

    # Numeracja: pierwszy raz canonical → nowy numer; kolejne wystąpienia tego
    # samego canonical → ten sam numer.
    label_counters: dict[str, int] = {}
    canonical_to_num: dict[tuple[str, int], int] = {}
    detections: list[dict] = []
    for span, canon_id in zip(merged, canonical_id_per_span):
        backend_label = span.get("label", "unknown")
        front_label = LABEL_MAP.get(backend_label, backend_label.upper())
        key = (front_label, canon_id)
        if key not in canonical_to_num:
            label_counters[front_label] = label_counters.get(front_label, 0) + 1
            canonical_to_num[key] = label_counters[front_label]
        num = canonical_to_num[key]
        detections.append(
            {
                "label": front_label,
                "text": span.get("text", ""),
                "placeholder": f"<{front_label}_{num}>",
                "source": _normalize_source(span.get("source", "opf")),
                "start": span["start"],
                "end": span["end"],
                "confidence": float(span.get("confidence", 1.0)),
            }
        )

    # Apply redaction z nowymi placeholderami
    redacted_text = apply_redaction(
        text,
        [
            {
                "start": d["start"],
                "end": d["end"],
                "placeholder": d["placeholder"],
            }
            for d in detections
        ],
    )

    return {"detections": detections, "redacted_text": redacted_text}
