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
# Przykłady które matchują:
#   PL12 1140 2004 0000 3502 1234 5678
#   12 1140 2004 0000 3502 1234 5678
#   12114020040000350212345678
IBAN_PL = re.compile(
    r"\b(?:PL\s?)?(\d{2}(?:[\s-]?\d{4}){5}[\s-]?\d{4})\b",
    re.IGNORECASE,
)

# NIP — 10 cyfr, wymaga kontekstu (słowo "NIP" do 5 znaków przed).
# Format: 1234567890 lub 123-456-78-90 lub 123-45-67-890.
NIP_WITH_CONTEXT = re.compile(
    r"\bNIP[:\s]{1,5}((?:PL\s?)?\d{3}[-\s]?\d{2,3}[-\s]?\d{2,3}[-\s]?\d{2,3})\b",
    re.IGNORECASE,
)

# PESEL — 11 cyfr, wymaga kontekstu "PESEL" (do 30 znaków przed, żeby objąć
# typowe polskie frazy: "PESEL do faktury:", "PESEL klienta to:", etc).
# Standalone 11-cyfrowy match jest niebezpieczny (false positives: telefony,
# identyfikatory), więc bez kontekstu nie łapiemy.
PESEL_WITH_CONTEXT = re.compile(
    r"\bPESEL[\w\s:.,/-]{1,30}?(\d{11})\b",
    re.IGNORECASE,
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
                label="private_account_number",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<PRIVATE_ACCOUNT_NUMBER>",
                source="regex:iban_pl",
            )
        )

    for match in NIP_WITH_CONTEXT.finditer(text):
        digits_only = re.sub(r"\D", "", match.group(1).replace("PL", ""))
        if len(digits_only) != 10:
            continue
        spans.append(
            RegexSpan(
                label="private_account_number",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<PRIVATE_ACCOUNT_NUMBER>",
                source="regex:nip_pl",
            )
        )

    for match in PESEL_WITH_CONTEXT.finditer(text):
        spans.append(
            RegexSpan(
                label="private_account_number",
                start=match.start(1),
                end=match.end(1),
                text=match.group(1),
                placeholder="<PRIVATE_ACCOUNT_NUMBER>",
                source="regex:pesel_pl",
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
    Konto: 12 1140 2004 0000 3502 1234 5678
    PESEL do faktury: 90123456789
    Inny IBAN: PL61 1090 1014 0000 0712 1981 2874
    """
    found = find_pii(sample)
    print(f"Found {len(found)} regex matches:")
    for span in found:
        print(f"  [{span.label}] {span.text!r} (source={span.source})")
