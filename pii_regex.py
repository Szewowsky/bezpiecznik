"""
Polski regex layer — deterministic detection dla strukturalnych PII które
Privacy Filter (baseline) może przegapić.

Filozofia:
- Wymagaj **kontekstu** (NIP, PESEL) gdzie to możliwe — minimalizuje false positives
- IBAN jest bezpieczny standalone (26 cyfr to bardzo rzadki przypadek false-match)
- Każdy match ma label kompatybilny z OPF naming (`private_account_number`)
- Zwracamy spany w identycznym formacie jak `OPF.redact().detected_spans`

Phase 2.1a (2026-05-01): dołożony detector polskich imion+nazwisk w formach
odmienionych (`find_polish_inflected_persons`). Whitelist-gated z `pii_pl_names`,
dwa warianty (imię odmienione + nazwisko mianownik LUB imię + nazwisko z końcówką).
Łapie "Pawłem Górskim", "Anną Nowak", "Markiem Kowalskim" - przypadki które
OPF model całkowicie pomija.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pii_pl_names import (
    LAST_NAME_NOMINATIVE_PATTERN,
    ORG_BRAND_TOKENS,
    ORG_CONTEXT_TRIGGERS_BEFORE,
    PL_ALL_FIRST_NAMES,
    PL_LAST_NAME_SUFFIXES_INFLECTED,
)


@dataclass
class RegexSpan:
    label: str
    start: int
    end: int
    text: str
    placeholder: str
    source: str = "regex"


# IBAN PL — opcjonalnie z prefix "PL", 2 cyfry kontrolne + 24 cyfry numeru konta,
# często grupowane w bloki po 4 ze spacjami.
IBAN_PL = re.compile(
    r"\b(?:PL\s?)?(\d{2}(?:[\s-]?\d{4}){5}[\s-]?\d{4})\b",
    re.IGNORECASE,
)

# NIP — wymaga kontekstu (słowo "NIP" do 60 znaków przed liczbą, żeby objąć
# polskie frazy: "NIP: X", "NIP X", "Mój nip to X", "NIP firmy XYZ sp. z o.o.: X").
# Liberalnie łapie ciąg cyfr/separatorów po słowie kluczowym (8-15 znaków),
# potem walidacja digit-count (8-11 cyfr — poprawny NIP = 10, tolerancja typos).
# Włączono nawiasy/parens () w klasie znaków, by łapać "NIP firmy (Brandbox sp. z o.o.):".
NIP_WITH_CONTEXT = re.compile(
    r"\bNIP[\w\s:.,/()\-]{1,60}?((?:PL\s?)?[\d][\d\s-]{6,14}[\d])\b",
    re.IGNORECASE,
)

# PESEL — wymaga kontekstu "PESEL" (do 60 znaków przed, np. "PESEL klienta (potrzebny do umowy):").
# Tolerancja typos: 8-12 cyfr (poprawny PESEL ma 11).
# Włączono nawiasy/parens () w klasie znaków, by łapać polskie frazy z dopiskami.
PESEL_WITH_CONTEXT = re.compile(
    r"\bPESEL[\w\s:.,/()\-]{1,60}?(\d{8,12})\b",
    re.IGNORECASE,
)

# Polski kod pocztowy — XX-XXX. Powszechnie występuje w adresach.
# Bezpieczny bez kontekstu (rare false-match w innych liczbach).
POSTAL_CODE_PL = re.compile(r"\b(\d{2}-\d{3})\b")

# Polski adres z prefixem — uzupełnia OPF który nie rozumie polskich adresów.
# Łapie: "ul. Słoneczna 12/4", "al. Jerozolimskie 100", "Aleje Jerozolimskie 100"
# Stop chars: koniec linii, kropka kończąca zdanie, przecinek, średnik (typowe
# separatory między elementami adresu).
ADDRESS_PREFIX_PL = re.compile(
    r"\b(?:ul\.|al\.|Aleje|aleja|plac|pl\.|osiedle|os\.|rondo|skwer|bulwar|"
    r"Ul\.|Al\.|Plac|Pl\.|Osiedle|Os\.|Rondo|Skwer|Bulwar)\s+"
    r"([A-ZŻŹĆĄŚĘŁÓŃ][\wŻŹĆĄŚĘŁÓŃżźćąśęłóń\s\-/.]{2,80}?)"
    r"(?=,|;|\.\s|\n|$)",
    re.UNICODE,
)

# Słowa-klucze adresu — gdy OPF złapał PERSON span z którymś z tych prefiksów,
# to nie osoba tylko ulica. Reklasyfikujemy na private_address.
ADDRESS_KEYWORDS_PREFIX = (
    "ul.", "al.", "aleje", "aleja", "plac", "pl.",
    "osiedle", "os.", "rondo", "skwer", "bulwar",
)


# ── Polish PERSON detector (Phase 2.1a) ─────────────────────────────────
# Dwa warianty regex dla polskich imion+nazwisk w formach odmienionych:
#   Wariant A: IMIĘ_DOWOLNE + NAZWISKO_MIANOWNIK (np. "Anną Nowak")
#   Wariant B: IMIĘ_DOWOLNE + NAZWISKO_Z_KOŃCÓWKĄ (np. "Pawłem Górskim")
#
# Oba wymagają że pierwszy token jest w `PL_ALL_FIRST_NAMES` (whitelist gating
# w funkcji, nie w regex). Drugi token to capital word z opcjonalną fleksyjną
# końcówką (B) lub wymóg min 2 lowercase letters (A żeby uniknąć "Anna A").
#
# Hyphenated surnames ("Górski-Kowalski") obsługiwane od razu w obu wariantach.

_FIRST_NAME_CANDIDATE = r"[A-ZŁŚŻŹĆŃĄĘÓ][a-ząęółśżźćń]+"

# Sortuj suffixy longest-first żeby greedy regex łapał dłuższe końcówki najpierw.
# `PL_LAST_NAME_SUFFIXES_INFLECTED` z pii_pl_names jest już posortowany ale
# robimy explicit dla bezpieczeństwa.
_LAST_INFLECTED_SUFFIXES_SORTED = sorted(
    set(PL_LAST_NAME_SUFFIXES_INFLECTED), key=len, reverse=True
)
_LAST_INFLECTED_ALT = "|".join(re.escape(s) for s in _LAST_INFLECTED_SUFFIXES_SORTED)

_LAST_NAME_INFLECTED_PATTERN = (
    rf"[A-ZŁŚŻŹĆŃĄĘÓ][a-ząęółśżźćń]+(?:{_LAST_INFLECTED_ALT})"
    rf"(?:-[A-ZŁŚŻŹĆŃĄĘÓ][a-ząęółśżźćń]+(?:{_LAST_INFLECTED_ALT}))?"
)

# Lookahead-based wzorce - finditer może znaleźć overlapping matches, więc
# nawet jeśli pierwsza para tokenów (np. "Pan Jan") jest skipowana przez
# whitelist gating, druga para ("Jan Górski-Kowalski") wciąż może być znaleziona.
PL_PERSON_VARIANT_A = re.compile(
    rf"(?<!\w)(?=({_FIRST_NAME_CANDIDATE})\s+({LAST_NAME_NOMINATIVE_PATTERN})(?!\w))",
    re.UNICODE,
)
PL_PERSON_VARIANT_B = re.compile(
    rf"(?<!\w)(?=({_FIRST_NAME_CANDIDATE})\s+({_LAST_NAME_INFLECTED_PATTERN})(?!\w))",
    re.UNICODE,
)


def find_polish_inflected_persons(text: str) -> list[dict]:
    """
    Detector polskich imion+nazwisk z whitelist gatingiem + blocklist brandów.

    Łapie (positive):
      - "Pawłem Górskim" (variant B: imię odmienione + nazwisko z końcówką)
      - "Anną Nowak" (variant A: imię odmienione + nazwisko mianownik)
      - "Marek Kowalski" (variant A i B - dedup w merge z OPF)
      - "Jan Górski-Kowalski" (hyphenated)

    NIE łapie (negative):
      - "Marketing Garage" (oba w ORG_BRAND_TOKENS, plus pierwszy nie w whitelist)
      - "Sheriff Octopus" (oba w ORG_BRAND_TOKENS)
      - "Open Source" (Open w ORG_BRAND_TOKENS)
      - "Xavier Martínez" (Xavier nie w PL_ALL_FIRST_NAMES whitelist)
      - "kanał Marketing Garage" (kontekst trigger "kanał" przed)

    Returns:
        Lista span dictów w formacie kompatybilnym z OPF detected_spans.
        Każdy span ma source="regex_pl_inflected" + variant ("A"/"B").
    """
    spans: list[dict] = []
    seen_ranges: set[tuple[int, int]] = set()

    # B preferowany - nazwisko z końcówką = pewniejsze. Iteruj A po B żeby
    # przy tym samym rangu zostawać przy variant B (większa pewność).
    for pattern, variant_label in [
        (PL_PERSON_VARIANT_B, "B"),
        (PL_PERSON_VARIANT_A, "A"),
    ]:
        for m in pattern.finditer(text):
            first, last = m.group(1), m.group(2)
            # Lookahead pattern - m.start()=m.end()=position startu pierwszego
            # capture. Realne pozycje przez group indices.
            start, end = m.start(1), m.end(2)

            # Dedup A/B na tym samym rangu
            if (start, end) in seen_ranges:
                continue

            # Whitelist gating: pierwszy token musi być rozpoznawalnym imieniem
            # (mianownik LUB jedna z odmian).
            if first not in PL_ALL_FIRST_NAMES:
                continue

            # Blocklist: jeśli pierwszy LUB drugi token to brand → skip.
            # Dla hyphenated surname sprawdzamy tylko pierwszą część.
            last_first_part = last.split("-")[0]
            if first in ORG_BRAND_TOKENS or last_first_part in ORG_BRAND_TOKENS:
                continue

            # Context trigger: czy bezpośrednio przed (30 znaków) jest słowo
            # z ORG_CONTEXT_TRIGGERS_BEFORE jak "kanał", "firma", "startup".
            prefix_window = text[max(0, start - 30):start].lower()
            # Sprawdź jako word boundary żeby uniknąć false trigger w środku słowa.
            has_org_trigger = any(
                re.search(rf"\b{re.escape(t)}\b", prefix_window)
                for t in ORG_CONTEXT_TRIGGERS_BEFORE
            )
            if has_org_trigger:
                continue

            seen_ranges.add((start, end))
            spans.append({
                "label": "private_person",
                "start": start,
                "end": end,
                "text": text[start:end],  # lookahead pattern - m.group(0) = ""
                "placeholder": "<OSOBA>",  # będzie zrenumerowany w pii_service
                "source": "regex_pl_inflected",
                "variant": variant_label,
                "confidence": 0.75 if variant_label == "B" else 0.65,
            })

    spans.sort(key=lambda s: s["start"])
    return spans


def find_pii(text: str) -> list[RegexSpan]:
    """
    Znajdź strukturalne PII w tekście używając regex'ów.

    Returns:
        Lista RegexSpan w kolejności występowania w tekście.
    """
    spans: list[RegexSpan] = []

    for match in IBAN_PL.finditer(text):
        # Heurystyka — odrzuć match gdy total cyfr != 26
        digits_only = re.sub(r"\D", "", match.group(1))
        if len(digits_only) != 26:
            continue
        spans.append(
            RegexSpan(
                label="iban",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<IBAN>",
                source="regex:iban_pl",
            )
        )

    for match in NIP_WITH_CONTEXT.finditer(text):
        digits_only = re.sub(r"\D", "", match.group(1).replace("PL", ""))
        # Tolerancja typos: 8-11 cyfr (poprawny NIP = 10)
        if not (8 <= len(digits_only) <= 11):
            continue
        spans.append(
            RegexSpan(
                label="nip",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<NIP>",
                source="regex:nip_pl",
            )
        )

    for match in PESEL_WITH_CONTEXT.finditer(text):
        # Pattern już ogranicza do 8-12 cyfr; dodatkowo waliduj
        digits_only = match.group(1)
        if not (8 <= len(digits_only) <= 12):
            continue
        spans.append(
            RegexSpan(
                label="pesel",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<PESEL>",
                source="regex:pesel_pl",
            )
        )

    for match in POSTAL_CODE_PL.finditer(text):
        spans.append(
            RegexSpan(
                label="postal_code",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<KOD_POCZTOWY>",
                source="regex:postal_pl",
            )
        )

    # Polskie adresy z prefixem (ul./al./Aleje/Plac itd.) — OPF tego nie łapie
    # albo myli z OSOBA. Patternem łapiemy CAŁY span od prefiksu do separatora.
    for match in ADDRESS_PREFIX_PL.finditer(text):
        spans.append(
            RegexSpan(
                label="private_address",
                start=match.start(),
                end=match.end(),
                text=match.group(0),
                placeholder="<ADRES>",
                source="regex:address_pl",
            )
        )

    spans.sort(key=lambda s: s.start)
    return spans


def reclassify_address_persons(opf_spans: list[dict]) -> list[dict]:
    """
    Reklasyfikator: OPF często myli polskie ulice ('Aleje Jerozolimskie') z osobami.
    Gdy private_person span zaczyna się od address keyword (Aleje, ul., Plac, ...) —
    zmieniamy label na private_address.

    Bezpieczne: nie zmieniamy spanów które OPF już dał jako address ani niczego
    poza PERSON. Pozycje (start/end) zostają nietknięte.
    """
    out = []
    for span in opf_spans:
        if span.get("label") != "private_person":
            out.append(span)
            continue
        text_lower = span.get("text", "").lower().strip()
        if any(text_lower.startswith(kw) for kw in ADDRESS_KEYWORDS_PREFIX):
            out.append({**span, "label": "private_address"})
        else:
            out.append(span)
    return out


# Słowa-klucze PII które OPF błędnie klasyfikuje jako PERSON
# (np. "Mój nip" → PRIVATE_PERSON). Gdy span PERSON zawiera któreś
# z tych słów, span jest filtrowany — to nie imię, to kontekst PII.
PII_KEYWORDS_IN_PERSON = ("nip", "pesel", "iban", "konto", "regon", "krs")


def filter_false_person_spans(opf_spans: list[dict]) -> list[dict]:
    """
    Usuwa OPF spany typu `private_person` które zawierają słowa-klucze
    PII (NIP, PESEL, etc) — to nie imiona, to kontekst PII.

    Comparison case-insensitive na word boundaries (żeby "iban" w "Iban Kowalski"
    było traktowane różnie niż "iban" w "Mój iban to ...").

    Bezpieczeństwo: po filtrze regex layer wciąż łapie cyfry —
    PII nie wycieka, tracimy tylko nadmiarową redakcję kontekstu.
    """
    filtered = []
    for span in opf_spans:
        if span.get("label") == "private_person":
            text_lower = span.get("text", "").lower()
            # Sprawdź czy słowo-klucz pojawia się jako pełne słowo (word boundary)
            has_keyword = any(
                re.search(rf"\b{kw}\b", text_lower) for kw in PII_KEYWORDS_IN_PERSON
            )
            if has_keyword:
                continue  # skip — to nie osoba
        filtered.append(span)
    return filtered


# ── Source priority dla overlap resolution (Phase 2.1a) ─────────────────
# Wyższa wartość = wygrywa overlap. Jawnie zamiast polegać na kolejności listy
# (Codex P0/6: hidden dependency).
#
# Logika:
# - regex (NIP/IBAN/PESEL/postal/address) - deterministic, wysokie zaufanie
# - opf - model NER, dobry recall ale czasem mismatch
# - regex_pl_inflected - heurystyka, niższe zaufanie niż OPF dla PERSON
SOURCE_PRIORITY = {
    "regex:iban_pl": 100,
    "regex:nip_pl": 100,
    "regex:pesel_pl": 100,
    "regex:postal_pl": 95,
    "regex:address_pl": 95,
    "opf": 90,
    "regex_pl_inflected": 50,  # heurystyka - OPF wygrywa overlap
}


def _source_priority(source: str) -> int:
    """Lookup priority dla danego source string. Default 0 dla nieznanych."""
    return SOURCE_PRIORITY.get(source, 0)


def merge_with_opf_spans(opf_spans: list[dict], regex_spans: list[RegexSpan]) -> list[dict]:
    """
    Połącz spany z OPF + regex_pl_inflected (oba w opf_spans) z regex strukturalnym.

    Overlap resolution po explicit SOURCE_PRIORITY zamiast kolejności listy.
    Regex strukturalny (NIP/IBAN/PESEL/address) wygrywa nad OPF i regex_pl,
    OPF wygrywa nad regex_pl_inflected dla PERSON.

    Args:
        opf_spans: lista span dict'ów z OPF (po filter_false_person_spans
                   i reclassify_address_persons), MOŻE też zawierać
                   regex_pl_inflected spany (zmergowane wcześniej w pii_service).
        regex_spans: lista RegexSpan z find_pii() (NIP, IBAN, PESEL, postal, address).

    Returns:
        Połączona lista dictów, sortowana po pozycji. Overlap resolved po priority.
    """
    # Konwertuj regex_spans na dict format
    all_candidates: list[dict] = []
    for r in regex_spans:
        all_candidates.append({
            "label": r.label,
            "start": r.start,
            "end": r.end,
            "text": r.text,
            "placeholder": r.placeholder,
            "source": r.source,
        })
    # OPF spans (które mogą zawierać regex_pl_inflected zmergowane wcześniej)
    for opf in opf_spans:
        all_candidates.append({**opf, "source": opf.get("source", "opf")})

    # Sortuj po (start, -priority) - przy tym samym start, wyższy priority pierwszy.
    all_candidates.sort(key=lambda s: (s["start"], -_source_priority(s.get("source", ""))))

    # Greedy dedup: dla każdego kandydata sprawdź czy overlapuje z którymś już
    # przyjętym. Jeśli tak, przyjmij tylko jeśli ma wyższy priority niż konfliktujący.
    merged: list[dict] = []
    for cand in all_candidates:
        overlapping = [
            (i, m) for i, m in enumerate(merged)
            if not (cand["end"] <= m["start"] or cand["start"] >= m["end"])
        ]
        if not overlapping:
            merged.append(cand)
            continue

        cand_pri = _source_priority(cand.get("source", ""))
        # Jeśli jakikolwiek overlapping ma >= priority, skip cand
        if any(_source_priority(m.get("source", "")) >= cand_pri for _, m in overlapping):
            continue

        # cand wygrywa - usuń wszystkie konfliktujące i dodaj cand
        keep_idx = {i for i, _ in overlapping}
        merged = [m for i, m in enumerate(merged) if i not in keep_idx]
        merged.append(cand)

    merged.sort(key=lambda s: s["start"])
    return merged


def apply_redaction(text: str, spans: list[dict]) -> str:
    """
    Apply redaction by replacing detected spans with their placeholders.
    Iteruje od końca żeby pozycje pozostały valid przy zamianach.
    """
    result = text
    for span in sorted(spans, key=lambda s: s["start"], reverse=True):
        result = result[: span["start"]] + span["placeholder"] + result[span["end"] :]
    return result


if __name__ == "__main__":
    # Quick self-test
    sample = """
    NIP 5252839110, drugi: NIP: 952-345-67-90.
    NIP z typo: 883951111
    Konto: 12 1140 2004 0000 3502 1234 5678
    PESEL do faktury: 90123456789
    PESEL z typo: 11111111
    Inny IBAN: PL61 1090 1014 0000 0712 1981 2874
    Adres: Chichy 79, 67-320 Chichy
    """
    found = find_pii(sample)
    print(f"Found {len(found)} regex matches:")
    for span in found:
        print(f"  [{span.label:14}] {span.text!r:50} → {span.placeholder} (source={span.source})")
