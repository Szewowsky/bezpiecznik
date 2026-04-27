"""
Polski regex layer — deterministic detection dla strukturalnych PII które
Privacy Filter (baseline) może przegapić.

Filozofia:
- Wymagaj **kontekstu** (NIP, PESEL) gdzie to możliwe — minimalizuje false positives
- IBAN jest bezpieczny standalone (26 cyfr to bardzo rzadki przypadek false-match)
- Każdy match ma label kompatybilny z OPF naming (`private_account_number`)
- Zwracamy spany w identycznym formacie jak `OPF.redact().detected_spans`
"""

from __future__ import annotations

import re
from dataclasses import dataclass


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

# NIP — wymaga kontekstu (słowo "NIP" do 20 znaków przed liczbą, żeby objąć
# polskie frazy: "NIP: X", "NIP X", "Mój nip to X", "NIP firmy wynosi X").
# Liberalnie łapie ciąg cyfr/separatorów po słowie kluczowym (8-15 znaków),
# potem walidacja digit-count (8-11 cyfr — poprawny NIP = 10, tolerancja typos).
NIP_WITH_CONTEXT = re.compile(
    r"\bNIP[\w\s:.,/-]{1,20}?((?:PL\s?)?[\d][\d\s-]{6,14}[\d])\b",
    re.IGNORECASE,
)

# PESEL — wymaga kontekstu "PESEL" (do 30 znaków przed, np. "PESEL do faktury:").
# Tolerancja typos: 8-12 cyfr (poprawny PESEL ma 11).
PESEL_WITH_CONTEXT = re.compile(
    r"\bPESEL[\w\s:.,/-]{1,30}?(\d{8,12})\b",
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


def merge_with_opf_spans(opf_spans: list[dict], regex_spans: list[RegexSpan]) -> list[dict]:
    """
    Połącz spany z OPF z regex'em. Deduplikuje overlap (regex wygrywa
    dla strukturalnych PII bo jest deterministic).

    Args:
        opf_spans: lista span dict'ów z RedactionResult.detected_spans
        regex_spans: lista RegexSpan z find_pii()

    Returns:
        Połączona lista, sortowana po pozycji.
    """
    merged = []

    # Najpierw dodaj wszystkie regex spany (priority)
    for r in regex_spans:
        merged.append({
            "label": r.label,
            "start": r.start,
            "end": r.end,
            "text": r.text,
            "placeholder": r.placeholder,
            "source": r.source,
        })

    # Dodaj OPF spany które NIE overlapują z regex
    for opf in opf_spans:
        overlap = False
        for r in regex_spans:
            if not (opf["end"] <= r.start or opf["start"] >= r.end):
                overlap = True
                break
        if not overlap:
            merged.append({**opf, "source": "opf"})

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
