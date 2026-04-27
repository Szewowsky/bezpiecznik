"""
Smoke test polski — Phase 1 decision gate z PRD.

Sprawdza recall na 3 polskich samples (samples/*.txt).
Nie automatic recall scoring — to wizualny check do oceny przez Roberta.

Run: python smoke_test.py
"""

from __future__ import annotations

import json
from pathlib import Path

from opf import OPF


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

        result = model.redact(text).to_dict()

        print("REDACTED:\n" + result["redacted_text"])
        print("-" * 80)
        print(f"SUMMARY: {result['summary']['span_count']} spans detected")
        for label, count in result["summary"]["by_label"].items():
            print(f"  - {label}: {count}")
        print("-" * 80)
        print("DETECTED SPANS:")
        for span in result["detected_spans"]:
            print(f"  [{span['label']:24}] {span['text']!r} → {span['placeholder']}")
        print()


if __name__ == "__main__":
    main()
