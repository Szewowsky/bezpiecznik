# Privacy Tool

Lokalna apka desktop do wykrywania i maskowania PII (dane osobowe) w tekstach. Drag-and-drop pliku lub paste tekst → masked output. **Wszystko lokalnie. Zero chmury.**

Pod maską: [OpenAI Privacy Filter](https://github.com/openai/privacy-filter) (Apache 2.0, ~3 GB model, ~50M aktywnych parametrów MoE) + [Gradio](https://gradio.app) jako UI.

> ⚠️ **Output wymaga human review.** To narzędzie to *data minimization aid*, nie compliance certification. RODO wciąż wymaga DPA dla US-vendors.

## Po co

Sanityzacja tekstów przed wysłaniem do external LLM API (Gemini, OpenAI, OpenRouter). Use cases:

- Pre-API sanitization danych klientów (kursy, mentoring)
- Pre-publish scan transkryptów YouTube
- Sanityzacja voice notes / wispr-notes
- Detekcja API keys / secrets w tekstach z code-on-screen

## Setup (macOS Apple Silicon)

```bash
# 1. Klon + venv
cd privacy-tool
python3 -m venv .venv
source .venv/bin/activate

# 2. Install
pip install -r requirements.txt

# 3. Pierwszy run (model ~3 GB pobierze się automatycznie do ~/.opf/)
python app.py
```

Apka odpali się na `http://localhost:7860` (auto-launch w przeglądarce).

## Wymagania

- macOS Apple Silicon (M-series)
- Python 3.10+
- ~6 GB wolnego miejsca (model + deps + venv)
- Internet (jednorazowo, do pobrania modelu)

## Co potrafi (MVP)

- Drag-drop `.txt` / `.md`
- Paste textarea jako fallback
- Output: zredagowany tekst + lista entities (JSON view)
- Copy do clipboard + download `*_redacted.md`
- Permanent warning banner

## Czego NIE potrafi (świadomie out-of-scope)

- Hosted version (Phase 2)
- Auth / multi-user
- Batch folder processing
- PDF/DOCX/Excel
- Real-time streaming
- Compliance certification

## Kategorie PII (8 domyślnych z Privacy Filter)

`PERSON` · `EMAIL` · `PHONE` · `ADDRESS` · `ACCOUNT_NUMBER` · `URL` · `DATE` · `SECRET`

**Brak:** `ORGANIZATION` (świadoma decyzja OpenAI). Nazwy firm mogą być over-redacted jako `PERSON` gdy brzmią jak nazwisko (`Robur Media` → `[PERSON] Media`).

## Polski recall (baseline test 2026-04-27)

~85% z baseline modelem. Wszystkie standardowe PII (PESEL, telefon, email, adres, nazwisko) wykryte. Główny błąd: nazwy firm jako `PERSON`. **Bez finetune** w MVP — ship z warningiem, finetune gdy realnie boli.

## License

TBD (start private). Privacy Filter sam jest Apache 2.0.

## Status

**Phase 1 — Setup + smoke test** (in progress).

PRD: [`Content Rob/materiały/PRDs/2026-04-27_privacy-tool-prd.md`](../Content%20Rob/materia%C5%82y/PRDs/2026-04-27_privacy-tool-prd.md)
