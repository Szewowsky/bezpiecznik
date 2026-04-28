"""
Privacy Tool — Gradio legacy UI (port 7860).

Dla nowego UI (Bezpiecznik, port 8000): uvicorn server:app --host 127.0.0.1 --port 8000

Run: python app.py
UI: http://localhost:7860 (auto-launch)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import gradio as gr

from pii_service import redact_text


WARNING_BANNER = """
> ⚠️ **Output wymaga human review.** Privacy Filter to *data minimization aid*,
> nie compliance certification. RODO wciąż wymaga DPA dla US-vendors.
> Sprawdź każdy redacted span przed wysłaniem do external LLM API.
"""

TMP_DIR = Path(tempfile.gettempdir()) / "bezpiecznik"


def redact(text: str, file_path: str | None) -> tuple[str, dict, str | None]:
    """
    Gradio handler — wraps wspólny pii_service.redact_text() w format Gradio outputs.

    Returns:
        (redacted_text, summary_dict, download_path)
    """
    # Priority: file > text
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")

    text = (text or "").strip()
    if not text:
        return ("⚠️ Wklej tekst lub przeciągnij plik.", {}, None)

    result = redact_text(text)
    detections = result["detections"]
    final_redacted = result["redacted_text"]

    # Recompute by_label dla detections (z polskimi etykietami)
    by_label: dict[str, int] = {}
    for d in detections:
        by_label[d["label"]] = by_label.get(d["label"], 0) + 1

    summary = {
        "by_label": by_label,
        "span_count": len(detections),
        "detected_spans": [
            {
                "label": d["label"],
                "text": d["text"],
                "placeholder": d["placeholder"],
                "source": d["source"],
                "position": f"{d['start']}-{d['end']}",
            }
            for d in detections
        ],
    }

    # Save redacted output to temp file for download (no body logging — NFR-P3)
    TMP_DIR.mkdir(exist_ok=True)
    out_path = TMP_DIR / "redacted.md"
    out_path.write_text(final_redacted, encoding="utf-8")

    return (final_redacted, summary, str(out_path))


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Privacy Tool", theme=gr.themes.Soft()) as ui:
        gr.Markdown("# 🔒 Privacy Tool — lokalny PII redactor")
        gr.Markdown(WARNING_BANNER)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### Input")
                file_input = gr.File(
                    label="Drag & drop plik (.txt / .md)",
                    file_types=[".txt", ".md"],
                    type="filepath",
                )
                text_input = gr.Textbox(
                    label="...lub wklej tekst tutaj",
                    lines=14,
                    placeholder="Wklej fragment emaila, transkryptu, notatki...",
                )
                submit_btn = gr.Button("🔒 Redact PII", variant="primary", size="lg")

            with gr.Column(scale=1):
                gr.Markdown("### Output")
                redacted_output = gr.Textbox(
                    label="Redacted text",
                    lines=14,
                    show_copy_button=True,
                    interactive=False,
                )
                entities_output = gr.JSON(label="Detected entities (per category)")
                download_output = gr.File(label="Download redacted file")

        submit_btn.click(
            fn=redact,
            inputs=[text_input, file_input],
            outputs=[redacted_output, entities_output, download_output],
        )

        gr.Markdown(
            "---\n"
            "**🔧 Regex layer (deterministic, PL):** "
            "`<IBAN>` · `<NIP>` · `<PESEL>` · `<KOD_POCZTOWY>`\n\n"
            "**🤖 OPF model (kontekstowe):** "
            "`<PRIVATE_PERSON>` · `<PRIVATE_EMAIL>` · `<PRIVATE_PHONE>` · "
            "`<PRIVATE_ADDRESS>` · `<PRIVATE_URL>` · `<PRIVATE_DATE>` · `<SECRET>`\n\n"
            "**Brak kategorii `ORGANIZATION`** — nazwy firm mogą być over-redacted jako PERSON. "
            "Filtr false-positive: spany PERSON zawierające `nip`/`pesel`/`iban`/`konto` "
            "są pomijane (regex łapie cyfry)."
        )

    return ui


if __name__ == "__main__":
    print(f"🚀 Privacy Tool (Gradio legacy) starting on port 7860")
    print(f"   Dla nowego UI (Bezpiecznik): uvicorn server:app --port 8000")
    ui = build_ui()
    ui.launch(
        server_name="127.0.0.1",  # localhost-only (NFR-P7)
        inbrowser=os.environ.get("PRIVACY_TOOL_INBROWSER", "1") == "1",
        show_error=True,
    )
