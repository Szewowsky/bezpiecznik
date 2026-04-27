"""
Pytest suite for pii_regex.py — deterministic regex layer for Polish structural PII.

Covers:
- Positive (recall) cases: IBAN PL, NIP PL, PESEL PL
- Negative (precision) cases: false positives that must NOT match
- merge_with_opf_spans() logic
- apply_redaction() correctness
"""

import pytest
from pii_regex import find_pii, merge_with_opf_spans, apply_redaction, RegexSpan


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
        assert iban.label == "private_account_number"
        assert iban.placeholder == "<PRIVATE_ACCOUNT_NUMBER>"

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
        assert nip.label == "private_account_number"
        assert nip.placeholder == "<PRIVATE_ACCOUNT_NUMBER>"

    def test_nip_colon_separator(self):
        text = "Numer NIP: 952-345-67-90"
        spans = find_pii(text)
        nip_spans = [s for s in spans if s.source == "regex:nip_pl"]
        assert len(nip_spans) == 1


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
        assert pesel.label == "private_account_number"
        assert pesel.placeholder == "<PRIVATE_ACCOUNT_NUMBER>"


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
        assert "<PRIVATE_ACCOUNT_NUMBER>" in result
