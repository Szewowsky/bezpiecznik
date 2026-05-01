"""
Pytest suite for pii_regex.py — deterministic regex layer for Polish structural PII.

Covers:
- Positive (recall) cases: IBAN PL, NIP PL, PESEL PL
- Negative (precision) cases: false positives that must NOT match
- merge_with_opf_spans() logic
- apply_redaction() correctness
"""

import pytest
from pii_regex import find_pii, merge_with_opf_spans, apply_redaction, filter_false_person_spans, RegexSpan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sources_in(spans):
    return [s.source for s in spans]


def texts_in(spans):
    return [s.text for s in spans]


# ---------------------------------------------------------------------------
# IBAN PL — positive cases
# ---------------------------------------------------------------------------

class TestIbanPositive:
    def test_iban_with_pl_prefix_and_spaces(self):
        text = "Przelej na konto PL61 1090 1014 0000 0712 1981 2874"
        spans = find_pii(text)
        iban_spans = [s for s in spans if s.source == "regex:iban_pl"]
        assert len(iban_spans) == 1, f"Expected 1 IBAN span, got {len(iban_spans)}"
        assert "61 1090 1014 0000 0712 1981 2874" in iban_spans[0].text

    def test_iban_without_pl_prefix_with_spaces(self):
        text = "Konto: 12 1140 2004 0000 3502 1234 5678"
        spans = find_pii(text)
        iban_spans = [s for s in spans if s.source == "regex:iban_pl"]
        assert len(iban_spans) == 1
        assert "1140" in iban_spans[0].text

    def test_iban_no_spaces(self):
        text = "Nr konta: 12114020040000350212345678"
        spans = find_pii(text)
        iban_spans = [s for s in spans if s.source == "regex:iban_pl"]
        assert len(iban_spans) == 1
        assert "12114020040000350212345678" in iban_spans[0].text

    def test_iban_label_and_placeholder(self):
        text = "Konto: 12 1140 2004 0000 3502 1234 5678"
        spans = find_pii(text)
        iban = next(s for s in spans if s.source == "regex:iban_pl")
        assert iban.label == "iban"
        assert iban.placeholder == "<IBAN>"

    def test_iban_digit_count_heuristic_rejects_25_digit_match(self):
        # 25 digits total — should be rejected by the len != 26 guard
        text = "Konto: 1211402004000035021234567"
        spans = find_pii(text)
        iban_spans = [s for s in spans if s.source == "regex:iban_pl"]
        assert len(iban_spans) == 0


# ---------------------------------------------------------------------------
# NIP PL — positive cases
# ---------------------------------------------------------------------------

class TestNipPositive:
    def test_nip_dash_format_123_456_78_90(self):
        text = "NIP: 123-456-78-90"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1

    def test_nip_dash_format_123_45_67_890(self):
        text = "NIP 123-45-67-890"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1

    def test_nip_no_separators_with_context_word(self):
        text = "NIP 5252839110"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1
        assert "5252839110" in nip_spans[0].text

    def test_nip_label_and_placeholder(self):
        text = "NIP 5252839110"
        spans = find_pii(text)
        nip = next(s for s in spans if s.source == "regex:nip_pl")
        assert nip.label == "nip"
        assert nip.placeholder == "<NIP>"

    def test_nip_colon_separator(self):
        text = "Numer NIP: 952-345-67-90"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1

    def test_nip_typo_9_digits(self):
        # Typo case: 9 digits after "NIP" keyword — within 8-11 tolerance
        text = "NIP 883951111"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1, f"Expected 1 NIP span for 9-digit typo, got {len(nip_spans)}"
        assert nip_spans[0].label == "nip"
        assert nip_spans[0].placeholder == "<NIP>"


# ---------------------------------------------------------------------------
# PESEL PL — positive cases
# ---------------------------------------------------------------------------

class TestPeselPositive:
    def test_pesel_immediately_after_keyword(self):
        text = "PESEL 90123456789"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 1
        assert pesel_spans[0].text == "90123456789"

    def test_pesel_with_phrase_do_faktury(self):
        text = "PESEL do faktury: 90123456789"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 1
        assert pesel_spans[0].text == "90123456789"

    def test_pesel_with_phrase_klienta(self):
        text = "PESEL klienta: 12345678901"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 1
        assert pesel_spans[0].text == "12345678901"

    def test_pesel_label_and_placeholder(self):
        text = "PESEL 90123456789"
        spans = find_pii(text)
        pesel = next(s for s in spans if s.source == "regex:pesel_pl")
        assert pesel.label == "pesel"
        assert pesel.placeholder == "<PESEL>"

    def test_pesel_typo_8_digits(self):
        # Typo case: 8 digits after "PESEL" keyword — within 8-12 tolerance
        text = "PESEL z typo: 11111111"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 1, f"Expected 1 PESEL span for 8-digit typo, got {len(pesel_spans)}"
        assert pesel_spans[0].label == "pesel"
        assert pesel_spans[0].placeholder == "<PESEL>"


# ---------------------------------------------------------------------------
# Negative cases — false positives that must NOT match
# ---------------------------------------------------------------------------

class TestNegativeCases:
    def test_phone_number_9_digits_no_nip_context(self):
        # 9-digit Polish mobile number without "NIP" context — should NOT be NIP
        text = "Zadzwon pod 512345678"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 0, "9-digit phone without NIP context matched as NIP"

    def test_phone_number_10_digits_no_nip_context(self):
        # 10-digit number that could look like NIP digits, but no "NIP" keyword
        text = "Kontakt: 48512345678"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 0, "10-digit number without NIP context matched as NIP"

    def test_foreign_phone_11_digits_no_pesel_context(self):
        # 11-digit foreign phone number without "PESEL" context — should NOT be PESEL
        text = "International: 48512345678901"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 0, "11-digit phone without PESEL context matched as PESEL"

    def test_partial_number_embedded_in_longer_string(self):
        # 10 digits embedded inside a longer identifier — word-boundary should prevent match
        text = "ORDER-52528391100-ABC"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 0, "Embedded 10-digit sequence in longer identifier matched as NIP"

    def test_nip_keyword_without_number_does_not_crash(self):
        # "NIP" with nothing numeric after — must not raise or spuriously match
        text = "Podaj NIP firmowy"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 0

    def test_pesel_keyword_without_number_does_not_crash(self):
        text = "Uzupelnij pole PESEL na formularzu"
        spans = find_pii(text)
        pesel_spans = [s for s in spans if s.source == "regex:pesel_pl"]
        assert len(pesel_spans) == 0


# ---------------------------------------------------------------------------
# Postal code PL — positive cases
# ---------------------------------------------------------------------------

class TestPostalCodePositive:
    def test_postal_code_67_320(self):
        text = "Chichy 79, 67-320 Chichy"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 1, f"Expected 1 postal span, got {len(postal_spans)}"
        assert postal_spans[0].text == "67-320"
        assert postal_spans[0].label == "postal_code"
        assert postal_spans[0].placeholder == "<KOD_POCZTOWY>"

    def test_postal_code_00_001(self):
        text = "Adres: ul. Warszawska 1, 00-001 Warszawa"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 1
        assert postal_spans[0].text == "00-001"

    def test_postal_code_02_987(self):
        text = "Kod pocztowy to 02-987"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 1
        assert postal_spans[0].text == "02-987"
        assert postal_spans[0].label == "postal_code"
        assert postal_spans[0].placeholder == "<KOD_POCZTOWY>"

    def test_postal_code_standalone_without_context(self):
        # No context word required — postal code regex is context-free
        text = "67-320"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 1
        assert postal_spans[0].text == "67-320"


# ---------------------------------------------------------------------------
# Postal code PL — negative cases (must NOT match)
# ---------------------------------------------------------------------------

class TestPostalCodeNegative:
    def test_too_long_first_group_1234_567(self):
        # 4 digits before hyphen — does not match \d{2}-\d{3}
        text = "Numer 1234-567 w systemie"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 0, "1234-567 must NOT match postal code (first group too long)"

    def test_too_short_first_group_1_234(self):
        # 1 digit before hyphen — does not match \d{2}-\d{3}
        text = "Wartosc 1-234 w tekscie"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 0, "1-234 must NOT match postal code (first group too short)"

    def test_too_short_second_group_12_34(self):
        # 2 digits after hyphen — does not match \d{2}-\d{3}
        text = "Kod 12-34 nieprawidlowy"
        spans = find_pii(text)
        postal_spans = [s for s in spans if s.source == "regex:postal_pl"]
        assert len(postal_spans) == 0, "12-34 must NOT match postal code (second group too short)"


# ---------------------------------------------------------------------------
# merge_with_opf_spans() — logic tests
# ---------------------------------------------------------------------------

class TestMergeWithOpfSpans:
    """
    RegexSpan uses start/end of the captured group (group 1), which can differ
    from the full match start/end. For merge testing we work with dict-based OPF
    spans and manually constructed spans aligned to a simple string.
    """

    def _make_regex_span(self, label, start, end, text, source="regex:iban_pl"):
        return RegexSpan(
            label=label,
            start=start,
            end=end,
            text=text,
            placeholder="<PRIVATE_ACCOUNT_NUMBER>",
            source=source,
        )

    def test_overlap_regex_wins_opf_removed(self):
        # Both regex and OPF cover the same span — only regex should survive.
        regex_spans = [self._make_regex_span("private_account_number", 10, 36, "12 1140 2004 0000 3502")]
        opf_spans = [{"label": "private_account_number", "start": 10, "end": 36,
                      "text": "12 1140 2004 0000 3502", "placeholder": "<PRIVATE_ACCOUNT_NUMBER>"}]
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        # Exactly one entry and it must come from regex
        assert len(merged) == 1
        assert merged[0]["source"].startswith("regex")

    def test_opf_only_span_is_kept(self):
        # OPF detects something regex doesn't — it must be kept.
        regex_spans = []
        opf_spans = [{"label": "person", "start": 5, "end": 15,
                      "text": "Jan Kowalski", "placeholder": "<PERSON>"}]
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        assert len(merged) == 1
        assert merged[0]["source"] == "opf"

    def test_no_overlap_both_kept(self):
        # No overlap — regex and OPF spans must both appear in result.
        regex_spans = [self._make_regex_span("private_account_number", 0, 26, "12114020040000350212345678")]
        opf_spans = [{"label": "email", "start": 50, "end": 70,
                      "text": "jan@example.com", "placeholder": "<EMAIL>"}]
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        assert len(merged) == 2
        sources = {m["source"] for m in merged}
        assert "opf" in sources
        assert any(s.startswith("regex") for s in sources)

    def test_merged_result_sorted_by_start(self):
        # Result must be sorted ascending by start position.
        regex_spans = [self._make_regex_span("private_account_number", 60, 86, "some_iban")]
        opf_spans = [{"label": "person", "start": 10, "end": 25,
                      "text": "Anna Nowak", "placeholder": "<PERSON>"}]
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        starts = [m["start"] for m in merged]
        assert starts == sorted(starts)

    def test_partial_overlap_opf_excluded(self):
        # OPF span partially overlaps regex span — OPF should be excluded.
        regex_spans = [self._make_regex_span("private_account_number", 10, 30, "some_iban")]
        opf_spans = [{"label": "private_account_number", "start": 20, "end": 40,
                      "text": "overlap_part", "placeholder": "<PRIVATE_ACCOUNT_NUMBER>"}]
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        # Only regex span survives
        assert len(merged) == 1
        assert merged[0]["source"].startswith("regex")


# ---------------------------------------------------------------------------
# apply_redaction() — correctness tests
# ---------------------------------------------------------------------------

class TestApplyRedaction:
    def test_single_span_replaced(self):
        text = "Konto: 12114020040000350212345678 dzieki"
        spans = [{"start": 7, "end": 33, "placeholder": "<PRIVATE_ACCOUNT_NUMBER>"}]
        result = apply_redaction(text, spans)
        assert "<PRIVATE_ACCOUNT_NUMBER>" in result
        assert "12114020040000350212345678" not in result

    def test_multiple_non_overlapping_spans_all_replaced(self):
        text = "NIP: 5252839110 i PESEL: 90123456789 w dokumencie"
        # Simulate two spans at known positions
        nip_start = text.index("5252839110")
        nip_end = nip_start + len("5252839110")
        pesel_start = text.index("90123456789")
        pesel_end = pesel_start + len("90123456789")
        spans = [
            {"start": nip_start, "end": nip_end, "placeholder": "<NIP>"},
            {"start": pesel_start, "end": pesel_end, "placeholder": "<PESEL>"},
        ]
        result = apply_redaction(text, spans)
        assert "<NIP>" in result
        assert "<PESEL>" in result
        assert "5252839110" not in result
        assert "90123456789" not in result

    def test_spans_applied_back_to_front_preserves_positions(self):
        # If applied front-to-back, positions shift and second replacement breaks.
        # apply_redaction must work correctly regardless of input order.
        text = "A: 111 B: 222 C: 333"
        spans = [
            {"start": 3, "end": 6, "placeholder": "<X>"},   # "111"
            {"start": 10, "end": 13, "placeholder": "<Y>"},  # "222"
            {"start": 17, "end": 20, "placeholder": "<Z>"},  # "333"
        ]
        result = apply_redaction(text, spans)
        assert result == "A: <X> B: <Y> C: <Z>"

    def test_empty_spans_returns_text_unchanged(self):
        text = "Brak danych do redakcji"
        result = apply_redaction(text, [])
        assert result == text

    def test_redaction_via_find_pii_roundtrip(self):
        # Integration: find_pii -> apply_redaction removes the original values.
        text = "NIP 5252839110 oraz konto 12 1140 2004 0000 3502 1234 5678"
        spans = find_pii(text)
        span_dicts = [
            {"start": s.start, "end": s.end, "placeholder": s.placeholder}
            for s in spans
        ]
        result = apply_redaction(text, span_dicts)
        assert "5252839110" not in result
        assert "1140 2004 0000 3502 1234 5678" not in result
        assert "<NIP>" in result
        assert "<IBAN>" in result


# ---------------------------------------------------------------------------
# filter_false_person_spans() — removes PERSON spans that contain PII keywords
# ---------------------------------------------------------------------------

def _person_span(text):
    """Helper: build a minimal OPF-style private_person span dict."""
    return {"label": "private_person", "start": 0, "end": len(text), "text": text, "placeholder": "<PRIVATE_PERSON>"}


def _other_span(label, text):
    """Helper: build a span with a non-person label."""
    return {"label": label, "start": 0, "end": len(text), "text": text, "placeholder": f"<{label.upper()}>"}


class TestFilterFalsePersonSpans:
    # --- Positive cases: filter REMOVES the span ---

    def test_person_span_with_nip_is_filtered(self):
        spans = [_person_span("Mój nip")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span containing 'nip' must be filtered"

    def test_person_span_with_pesel_is_filtered(self):
        spans = [_person_span("PESEL klient")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span containing 'pesel' must be filtered"

    def test_person_span_with_pesel_mid_phrase_is_filtered(self):
        spans = [_person_span("Pisał Adam, PESEL ...")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span with 'pesel' as a word must be filtered"

    def test_person_span_with_iban_is_filtered(self):
        spans = [_person_span("iban firmy")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span containing 'iban' must be filtered"

    def test_person_span_with_konto_is_filtered(self):
        spans = [_person_span("Konto klienta")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span containing 'konto' must be filtered"

    def test_person_span_with_regon_is_filtered(self):
        spans = [_person_span("REGON spółki")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "PERSON span containing 'regon' must be filtered"

    def test_person_span_case_insensitive_nip_upper(self):
        # NIP fully uppercased — must still be caught
        spans = [_person_span("MÓJ NIP TO")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "Filter must work case-insensitively (NIP uppercase)"

    # --- Negative cases: filter KEEPS the span ---

    def test_person_span_without_keyword_is_kept(self):
        spans = [_person_span("Robert Szewczyk")]
        result = filter_false_person_spans(spans)
        assert len(result) == 1, "PERSON span 'Robert Szewczyk' must NOT be filtered"

    def test_person_span_anna_nowak_is_kept(self):
        spans = [_person_span("Anna Nowak")]
        result = filter_false_person_spans(spans)
        assert len(result) == 1, "PERSON span 'Anna Nowak' must NOT be filtered"

    def test_email_span_with_iban_substring_is_kept(self):
        # label is NOT private_person → must never be filtered regardless of text
        spans = [_other_span("email_address", "iban@example.com")]
        result = filter_false_person_spans(spans)
        assert len(result) == 1, "Non-private_person span must be kept even if text contains keyword"

    def test_account_number_span_is_kept(self):
        spans = [_other_span("private_account_number", "12345")]
        result = filter_false_person_spans(spans)
        assert len(result) == 1, "ACCOUNT_NUMBER span must always be kept"

    def test_person_span_knipowski_kept_word_boundary(self):
        # 'nip' appears inside 'Knipowski' — NOT a word boundary match, so span must be kept
        spans = [_person_span("Knipowski")]
        result = filter_false_person_spans(spans)
        assert len(result) == 1, "'nip' inside 'Knipowski' must NOT trigger filter (word-boundary rule)"

    def test_person_span_pesel_knur_is_filtered_known_tradeoff(self):
        # 'pesel' as a standalone word IS a word-boundary match even though Knur is a real surname.
        # Accepted trade-off: very rare false-positive vs. over-redaction risk.
        spans = [_person_span("Pesel Knur")]
        result = filter_false_person_spans(spans)
        assert len(result) == 0, "'pesel' at word boundary in 'Pesel Knur' triggers filter (known trade-off)"

    # --- Multiple spans ---

    def test_mixed_list_only_person_with_keyword_removed(self):
        spans = [
            _person_span("Mój nip"),          # should be filtered
            _other_span("email_address", "jan@example.com"),  # kept
            _other_span("email_address", "anna@example.com"),  # kept
        ]
        result = filter_false_person_spans(spans)
        assert len(result) == 2, "Only the PERSON span with keyword should be removed"
        labels = [s["label"] for s in result]
        assert "private_person" not in labels

    def test_five_spans_two_keywords_filtered(self):
        spans = [
            _person_span("Robert Szewczyk"),   # kept — no keyword
            _person_span("Mój nip"),            # filtered
            _person_span("PESEL klienta"),      # filtered
            _other_span("email_address", "x@y.com"),   # kept
            _other_span("postal_code", "00-001"),      # kept
        ]
        result = filter_false_person_spans(spans)
        assert len(result) == 3, "Only 2 PERSON spans with keywords should be removed"

    def test_empty_list_returns_empty(self):
        result = filter_false_person_spans([])
        assert result == [], "Empty input must return empty list"


# ---------------------------------------------------------------------------
# Phase 2.1a — find_polish_inflected_persons (Polish PERSON detector)
# ---------------------------------------------------------------------------

from pii_regex import find_polish_inflected_persons


class TestPolishInflectedPersons:
    """
    Detector polskich imion+nazwisk z whitelist gatingiem + blocklist brandów.

    Wariant A: imię odmienione + nazwisko mianownik ("Anną Nowak").
    Wariant B: imię + nazwisko z końcówką fleksyjną ("Pawłem Górskim").

    Phase 2.1a fix dla bug z livestreamu 2026-05-01: OPF model całkowicie
    pomija polskie formy odmienione PERSON. Detector uzupełnia recall.
    """

    # --- Positive cases (powinny matchować) ---

    def test_pawel_gorski_inflected_variant_b(self):
        """Bug z livestreamu: 'Pawłem Górskim' (narzędnik m. + narzędnik nazwiska)."""
        spans = find_polish_inflected_persons("rozmawiam z Pawłem Górskim wczoraj")
        assert len(spans) == 1
        assert spans[0]["text"] == "Pawłem Górskim"
        assert spans[0]["variant"] == "B"
        assert spans[0]["source"] == "regex_pl_inflected"
        assert spans[0]["label"] == "private_person"

    def test_anna_nowak_inflected_variant_a(self):
        """Wariant A: imię odmienione 'Anną' + nazwisko mianownik 'Nowak'."""
        spans = find_polish_inflected_persons("Anną Nowak spotkałem wczoraj")
        assert len(spans) == 1
        assert spans[0]["text"] == "Anną Nowak"
        assert spans[0]["variant"] == "A"

    def test_marek_kowalski_nominative_caught(self):
        """Mianownik też łapany (variant A) - dedup z OPF zrobi merge."""
        spans = find_polish_inflected_persons("Marek Kowalski przyszedł")
        assert len(spans) == 1
        assert spans[0]["text"] == "Marek Kowalski"

    def test_hyphenated_surname(self):
        """'Jan Górski-Kowalski' - hyphenated surname obsługiwany."""
        spans = find_polish_inflected_persons("Pan Jan Górski-Kowalski przyszedł")
        # Pan nie w whitelist więc 'Pan Jan' skip, ale 'Jan Górski-Kowalski' łapane.
        assert any(s["text"] == "Jan Górski-Kowalski" for s in spans)

    def test_marie_skłodowską_female_inflected(self):
        """Żeńskie imię odmienione + nazwisko z końcówką."""
        spans = find_polish_inflected_persons("Spotkałem Marię Skłodowską w bibliotece.")
        assert len(spans) == 1
        assert spans[0]["text"] == "Marię Skłodowską"

    def test_robert_lewandowski_inflected(self):
        """'Robertem Lewandowskim' - 'Robertem' jako odmiana 'Robert'."""
        spans = find_polish_inflected_persons("z Robertem Lewandowskim wczoraj")
        assert len(spans) == 1
        assert spans[0]["text"] == "Robertem Lewandowskim"

    def test_pawle_locative_form(self):
        """'Pawle Górskim' - miejscownik imienia."""
        spans = find_polish_inflected_persons("o Pawle Górskim była mowa")
        assert len(spans) == 1
        assert spans[0]["text"] == "Pawle Górskim"

    def test_full_livestream_text(self):
        """Pełen livestream case - 2 osoby (Anna Nowak mianownik + Pawłem Górskim)."""
        text = (
            "[00:14] Cześć, tu Anna Nowak z kanału Marketing Garage. "
            "Dzisiaj rozmawiam z Pawłem Górskim, founderem startupu Brandbox."
        )
        spans = find_polish_inflected_persons(text)
        found_texts = [s["text"] for s in spans]
        assert "Anna Nowak" in found_texts
        assert "Pawłem Górskim" in found_texts
        assert "Marketing Garage" not in found_texts
        assert "Sheriff Octopus" not in found_texts
        assert "Brandbox" not in found_texts

    # --- Negative cases (NIE powinny matchować) ---

    def test_no_brand_marketing_garage(self):
        spans = find_polish_inflected_persons("Marketing Garage to firma")
        assert spans == []

    def test_no_brand_sheriff_octopus(self):
        spans = find_polish_inflected_persons("Sheriff Octopus to maskotka")
        assert spans == []

    def test_no_open_source(self):
        spans = find_polish_inflected_persons("Open Source software is great")
        assert spans == []

    def test_no_apple_silicon(self):
        spans = find_polish_inflected_persons("Apple Silicon procesory")
        assert spans == []

    def test_no_unknown_first_name(self):
        """Pierwszy token nie z whitelisty (obcojęzyczne imię) - skip."""
        spans = find_polish_inflected_persons("Xavier Martínez przyszedł")
        assert spans == []

    def test_no_context_trigger_kanal(self):
        """Trigger 'kanał' przed sekwencją - skip."""
        spans = find_polish_inflected_persons("kanał Marketing Garage rośnie")
        assert spans == []

    def test_no_context_trigger_startup(self):
        """Trigger 'startupu' przed Brandbox."""
        spans = find_polish_inflected_persons("founder startupu Brandbox")
        assert spans == []

    # --- Boundary / edge cases ---

    def test_empty_text(self):
        assert find_polish_inflected_persons("") == []

    def test_single_word_no_match(self):
        """Pojedyncze imię bez nazwiska - regex wymaga 2 tokenów."""
        assert find_polish_inflected_persons("Paweł") == []
        assert find_polish_inflected_persons("Pawłem") == []

    def test_three_word_picks_first_pair(self):
        """'Jan Maria Rokita' (3 tokeny) - łapie 'Jan Maria' jako pair (Maria w whitelist).
        Phase 2.1a obsługuje 2 tokeny - 3-tokenowe rozszerzenie do Phase 2.1b."""
        # 'Jan Maria' będzie matchowane (Maria pasuje LAST_NAME_NOMINATIVE_PATTERN).
        # To znana limitacja - canonical_id w pii_service rozwiąże aliasing.
        spans = find_polish_inflected_persons("Jan Maria Rokita przyszedł")
        # Może być 'Jan Maria' lub 'Maria Rokita' lub oba
        assert len(spans) >= 1

    def test_dedup_variant_a_b_same_range(self):
        """Mianownik Marek Kowalski - może matchować przez wariant A (Marek + Kowalski).
        Wariant B by też matchował 'Markiem Kowalskim' ale tu mianownik. Brak dedup conflict."""
        spans = find_polish_inflected_persons("Marek Kowalski Markiem Kowalskim")
        # Każdy w innym rangu - 2 spany, oba różne
        texts = [s["text"] for s in spans]
        assert "Marek Kowalski" in texts
        assert "Markiem Kowalskim" in texts
        assert len(spans) == 2

    def test_confidence_b_higher_than_a(self):
        """Wariant B (nazwisko z końcówką) bardziej pewny niż A (mianownik)."""
        text_b = "rozmawiam z Pawłem Górskim"
        text_a = "Anną Nowak spotkałem"
        b_span = find_polish_inflected_persons(text_b)[0]
        a_span = find_polish_inflected_persons(text_a)[0]
        assert b_span["confidence"] > a_span["confidence"]
