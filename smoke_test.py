"""
Smoke test polski — Phase 1 decision gate z PRD.

Sprawdza recall na 3 polskich samples (samples/*.txt) — hybrid approach:
OPF model + regex layer (IBAN PL, NIP, PESEL).

Run: python smoke_test.py
"""

from __future__ import annotations

from pathlib import Path

from opf import OPF

from pii_regex import (
    apply_redaction,
    filter_false_person_spans,
    find_pii,
    merge_with_opf_spans,
)


def main():
    samples = sorted(Path("samples").glob("*.txt"))
    if not samples:
        raise SystemExit("❌ Brak sampli w samples/")

    print("⏳ Loading model on CPU...")
    model = OPF(device="cpu", output_mode="typed")
    print("✅ Model loaded.\n")

    for path in samples:
        text = path.read_text(encoding="utf-8")
        print("=" * 80)
        print(f"📄 Sample: {path.name}")
        print("=" * 80)
        print("INPUT:\n" + text)
        print("-" * 80)

        # OPF
        opf_result = model.redact(text).to_dict()
        opf_spans = filter_false_person_spans(opf_result["detected_spans"])

        # Regex layer (PL strukturalne PII)
        regex_spans = find_pii(text)

        # Merge
        merged = merge_with_opf_spans(opf_spans, regex_spans)
        redacted = apply_redaction(text, merged)

        print("REDACTED (hybrid):\n" + redacted)
        print("-" * 80)
        print(f"SUMMARY: {len(merged)} spans (OPF: {len(opf_spans)}, regex added: {len(regex_spans)})")

        by_label: dict[str, int] = {}
        for s in merged:
            by_label[s["label"]] = by_label.get(s["label"], 0) + 1
        for label, count in sorted(by_label.items()):
            print(f"  - {label}: {count}")
        print("-" * 80)
        print("DETECTED SPANS:")
        for span in merged:
            source = span.get("source", "opf")
            marker = "🔧" if source.startswith("regex") else "🤖"
            print(f"  {marker} [{span['label']:24}] {span['text']!r:60} → {span['placeholder']} ({source})")
        print()


if __name__ == "__main__":
    main()
