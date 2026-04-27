"""
Privacy Tool — lokalny PII redactor (Gradio + OpenAI Privacy Filter).

Run: python app.py
UI: http://localhost:7860 (auto-launch)
"""

from __future__ import annotations

import os
from pathlib import Path

import gradio as gr

try:
    from opf import OPF
except ImportError:
    raise SystemExit(
        "❌ Brak pakietu 'opf'. Zainstaluj: pip install -r requirements.txt"
    )


WARNING_BANNER = """
> ⚠️ **Output wymaga human review.** Privacy Filter to *data minimization aid*,
> nie compliance certification. RODO wciąż wymaga DPA dla US-vendors.
> Sprawdź każdy redacted span przed wysłaniem do external LLM API.
"""

# Privacy Filter supports cpu / cuda. Na macOS Apple Silicon — tylko CPU.
DEVICE = os.environ.get("OPF_DEVICE", "cpu")
MODEL: OPF | None = None  # lazy-loaded on first inference
TMP_DIR = Path("/tmp/privacy-tool")


def get_model() -> OPF:
    """Lazy load model on first inference (faster startup)."""
    global MODEL
    if MODEL is None:
        print(f"⏳ Loading Privacy Filter on {DEVICE.upper()} (first run downloads ~3 GB)...")
        MODEL = OPF(device=DEVICE, output_mode="typed")
        print("✅ Model loaded.")
    return MODEL


def redact(text: str, file_path: str | None) -> tuple[str, dict, str | None]:
    """
    Main redaction handler.

    Returns:
        (redacted_text, summary_dict, download_path)
    """
    # Priority: file > text
    if file_path:
        text = Path(file_path).read_text(encoding="utf-8")

    text = (text or "").strip()
    if not text:
        return ("⚠️ Wklej tekst lub przeciągnij plik.", {}, None)

    model = get_model()
    result = model.redact(text)
    data = result.to_dict()

    # Build human-friendly summary
    summary = {
        "by_label": data["summary"]["by_label"],
        "span_count": data["summary"]["span_count"],
        "detected_spans": [
            {
                "label": s["label"],
                "text": s["text"],
                "placeholder": s["placeholder"],
                "position": f"{s['start']}-{s['end']}",
            }
            for s in data["detected_spans"]
        ],
    }

    # Save redacted output to temp file for download (no body logging — NFR-P3)
    TMP_DIR.mkdir(exist_ok=True)
    out_path = TMP_DIR / "redacted.md"
    out_path.write_text(data["redacted_text"], encoding="utf-8")

    return (data["redacted_text"], summary, str(out_path))


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
            "**Kategorie:** `PRIVATE_PERSON` · `PRIVATE_EMAIL` · `PRIVATE_PHONE` · "
            "`PRIVATE_ADDRESS` · `PRIVATE_ACCOUNT_NUMBER` · `PRIVATE_URL` · "
            "`PRIVATE_DATE` · `PRIVATE_SECRET`. "
            "**Bez kategorii** `ORGANIZATION` — nazwy firm mogą być over-redacted jako PERSON."
        )

    return ui


if __name__ == "__main__":
    print(f"🚀 Privacy Tool starting (device={DEVICE})")
    ui = build_ui()
    ui.launch(
        server_name="127.0.0.1",  # localhost-only (NFR-P7)
        inbrowser=True,
        show_error=True,
    )
