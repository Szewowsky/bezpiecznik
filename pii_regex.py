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

    spans.sort(key=lambda s: s.start)
    return spans


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
