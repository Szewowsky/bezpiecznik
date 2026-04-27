# Privacy Tool

Lokalna apka desktop do wykrywania i maskowania PII (dane osobowe) w tekstach. Drag-and-drop pliku lub paste tekst → masked output. **Wszystko lokalnie. Zero chmury.**

**Hybrid detection:**
- 🤖 [OpenAI Privacy Filter](https://github.com/openai/privacy-filter) — kontekstowe PII (PERSON, EMAIL, PHONE, ADDRESS, SECRET)
- 🔧 Regex layer dla polskich strukturalnych identyfikatorów (IBAN PL, NIP, PESEL)

UI: [Gradio 5.x](https://gradio.app) (single-process, ~120 linii Pythona).

> ⚠️ **Output wymaga human review.** Narzędzie to *data minimization aid*, nie compliance certification. RODO wciąż wymaga DPA dla US-vendors.

## Po co

Sanityzacja tekstów przed wysłaniem do external LLM API (Gemini, OpenAI, OpenRouter):

- Pre-API sanitization danych klientów (kursy, mentoring)
- Pre-publish scan transkryptów YouTube
- Sanityzacja voice notes / wispr-notes
- Detekcja API keys / secrets w tekstach z code-on-screen

## Setup (macOS Apple Silicon)

```bash
# 1. Venv (Python 3.10–3.14)
cd privacy-tool
python3 -m venv .venv
source .venv/bin/activate

# 2. Install
pip install -r requirements.txt

# 3. Pierwszy run (model ~3 GB pobierze się automatycznie do ~/.opf/)
python app.py
```

Apka odpali się na `http://localhost:7860` (auto-launch w przeglądarce). Przy pierwszym `redact` model wczyta się ~50s (CPU).

## Wymagania

- macOS Apple Silicon (M-series)
- Python 3.10+ (przetestowane na 3.14.3)
- ~6 GB wolnego miejsca (model + deps + venv)
- Internet (jednorazowo, do pobrania modelu)

> **Dependency notes (Python 3.13+):** stdlib `audioop` został usunięty. Wymagamy shim `audioop-lts` (już w `requirements.txt`). Gradio 4.x ma bug z Pythonem 3.14 — używamy Gradio 5.x.

## Co potrafi (MVP)

- Drag-drop `.txt` / `.md`
- Paste textarea jako fallback
- Output: zredagowany tekst + lista entities (JSON view, oznaczenie `source: opf|regex:*`)
- Copy do clipboard + download `*_redacted.md`
- Permanent warning banner
- Localhost-only binding (`127.0.0.1:7860`)

## Czego NIE potrafi (świadomie out-of-scope)

- Hosted version (Phase 2)
- Auth / multi-user
- Batch folder processing
- PDF / DOCX / Excel
- Real-time streaming
- Compliance certification
- Wykrywanie kategorii `ORGANIZATION` (brak w taksonomii Privacy Filter)
- Wykrywanie kategorii `DATE` (przegapia polskie daty — out of scope)

## Kategorie PII

| Kategoria | Source | Komentarz |
|-----------|--------|-----------|
| `PRIVATE_PERSON` | OPF | Imię, nazwisko, kontekstowo |
| `PRIVATE_EMAIL` | OPF | Wszystkie formaty |
| `PRIVATE_PHONE` | OPF | +48, bez prefix, ze spacjami |
| `PRIVATE_ADDRESS` | OPF | Polskie adresy z kontekstem |
| `PRIVATE_ACCOUNT_NUMBER` | OPF + 🔧 regex | Numery kont, NIP, PESEL — regex łata przegapienia OPF |
| `PRIVATE_URL` | OPF | URLs |
| `PRIVATE_DATE` | OPF | Daty (słaby recall na PL — known limitation) |
| `SECRET` | OPF | API keys, tokens (hit np. `sk_test_...`) |

**Regex layer** (deterministic, dla strukturalnych PL PII):
- IBAN PL: 26 cyfr z/bez prefix `PL`, ze/bez separatorów (` ` / `-`)
- NIP PL: 10 cyfr po słowie kluczowym `NIP`, formaty z myślnikami i bez
- PESEL: 11 cyfr po słowie kluczowym `PESEL` (do 30 znaków przed)

## Polski recall (smoke test 2026-04-27, hybrid layer)

3 polskie samples (email OMA, transkrypt YT, wispr note) — wszystkie krytyczne PII wykryte:

| Kategoria | Recall (przed regex) | Recall (po regex) |
|-----------|---------------------|-------------------|
| EMAIL | 100% | 100% |
| PHONE | 100% | 100% |
| SECRET | 100% | 100% |
| PERSON | ~67% | ~67% |
| ADDRESS | 50% | 50% |
| **ACCOUNT_NUMBER** | 50% | **100%** ← regex łata IBAN/NIP/PESEL |

**30/30 pytestów PASS** (`test_pii_regex.py`).

## License

TBD (start private). Privacy Filter sam jest Apache 2.0.

## Status

**Phase 1 — Setup + smoke + UI launch test:** ✅ DONE (2026-04-27)

PRD: [`Content Rob/materiały/PRDs/2026-04-27_privacy-tool-prd.md`](../Content%20Rob/materia%C5%82y/PRDs/2026-04-27_privacy-tool-prd.md)

### Phase 2 (planned)

- macOS Quick Action via CLI (right-click w Finderze)
- Polish finetune (jeśli recall realnie boli — lazy approach)
- Operating point preset (recall vs precision slider)
- Side-by-side preview (original vs redacted)
- Hosted version dla uczestników kursów (osobny PRD)
