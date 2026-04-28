# Bezpiecznik

**Lokalny strażnik danych wrażliwych - przed wysłaniem do AI.**

Wklejasz tekst (mail, transkrypt, notatkę) lub przeciągasz plik. Bezpiecznik znajduje i maskuje dane osobowe (imiona, e-maile, telefony, IBAN, NIP, PESEL, adresy) i daje Ci bezpieczną wersję, którą możesz spokojnie wysłać do ChatGPT, Claude czy innego AI.

> **Wszystko dzieje się na Twoim komputerze.** Tekst nigdy nie opuszcza tej aplikacji - zero połączeń z internetem (poza pierwszym pobraniem modelu).

---

## Spis treści

1. [Dla kogo to jest](#dla-kogo-to-jest)
2. [Instalacja krok po kroku](#instalacja-krok-po-kroku-dla-osób-nietechnicznych)
3. [Jak korzystać](#jak-korzystać)
4. [Aktualizacja do nowszej wersji](#aktualizacja-do-nowszej-wersji)
5. [FAQ](FAQ.md)
6. [Część techniczna](#część-techniczna-dla-developerów)

---

## Dla kogo to jest

Jeśli pracujesz z AI (ChatGPT, Claude, Gemini) i czasem wrzucasz do niego:
- maile od klientów,
- transkrypty rozmów,
- notatki głosowe,
- dane do faktur,
- raporty z imionami i kontaktami,

to **Bezpiecznik** zamaskuje wszystkie dane osobowe **zanim** wyślesz tekst do chmury. Zamiast `Anna Nowak, anna@example.com` wyślesz `<OSOBA_1>, <EMAIL_1>`. AI dostanie wszystko czego potrzebuje do pracy, ale bez Twoich (lub klienta) prywatnych danych.

---

## Instalacja krok po kroku (dla osób nietechnicznych)

> Przewidywany czas: **15 minut** (z czego 5 minut to pobieranie modelu w tle podczas pierwszego uruchomienia).
> Wymagania: **Mac** (Apple Silicon - M1/M2/M3/M4), **macOS Sonoma lub nowszy**, ~6 GB wolnego miejsca.

### Krok 1: Otwórz Terminal

- W prawym górnym rogu Maca kliknij ikonę **lupy** (Spotlight) lub naciśnij `⌘ + Spacja`
- Wpisz: `Terminal` i naciśnij Enter
- Otworzy się czarne (lub białe) okno - to **Terminal**. Tam wpisuje się komendy.

### Krok 2: Sprawdź czy masz Pythona

W Terminalu wklej (Cmd+V) i naciśnij Enter:

```bash
python3 --version
```

Powinno pojawić się np. `Python 3.13.0` (cyfra po `3.` musi być co najmniej **10**, czyli 3.10, 3.11, 3.12, 3.13 lub 3.14).

**Jeśli widzisz błąd "command not found":**
- Pobierz Pythona z [python.org/downloads](https://www.python.org/downloads/) (wybierz wersję 3.12 lub nowszą)
- Po zainstalowaniu zamknij Terminal i otwórz go ponownie
- Powtórz `python3 --version`

### Krok 3: Sprawdź czy masz git

W Terminalu:

```bash
git --version
```

Jeśli widzisz błąd, macOS sam zaproponuje instalację - kliknij **Install** w okienku, które wyskoczy. Trwa to ~5 minut.

### Krok 4: Pobierz Bezpiecznika

Wklej w Terminalu:

```bash
cd ~/Documents
git clone https://github.com/Szewowsky/bezpiecznik.git
cd bezpiecznik
```

### Krok 5: Zainstaluj zależności

W Terminalu (jesteś już w katalogu `bezpiecznik`):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

To zajmuje **5-10 minut**. Ściąga się ~3 GB różnych bibliotek. Możesz w tym czasie zrobić sobie kawę.

### Krok 6: Uruchom Bezpiecznika

W Terminalu (wciąż w katalogu `bezpiecznik`):

```bash
.venv/bin/uvicorn server:app --port 8000
```

W oknie pojawi się komunikat typu:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

To znaczy, że Bezpiecznik działa. **Nie zamykaj tego okna Terminala** - aplikacja działa dopóki ono jest otwarte.

### Krok 7: Otwórz aplikację w przeglądarce

W Safari lub Chrome wpisz w pasku adresu:

```
http://localhost:8000
```

Zobaczysz Bezpiecznika. **Pierwszy raz**, gdy klikniesz "Zamaskuj dane", aplikacja pobiera model AI (~3 GB, jednorazowo). Potrwa to **~50 sekund**. Każde następne maskowanie jest natychmiastowe.

---

## Jak korzystać

### Wariant A: Wklejam tekst

1. Wybierz zakładkę **Wklej tekst** (domyślnie)
2. Wklej tekst do pola (Cmd+V)
3. Kliknij **Zamaskuj dane**
4. Po prawej zobaczysz wersję z zamaskowanymi danymi
5. Kliknij **Kopiuj zamaskowane** lub **Pobierz .md**

### Wariant B: Wgrywam plik

1. Wybierz zakładkę **Wgraj plik**
2. Kliknij **Wybierz plik z dysku** lub przeciągnij plik z Findera
3. Pojawia się podgląd zawartości
4. Klik **Zamaskuj dane**

Obsługiwane formaty: `.md`, `.txt`, `.csv`, `.tsv`, `.json`, `.log`, `.html`, `.srt`, `.vtt` (do 5 MB).

### Wariant C: Z weryfikacją wzrokową

W panelu po prawej przełącz na **Z podświetleniem** - zobaczysz oryginał z kolorowymi zaznaczeniami, co zostało wykryte. Pomocne, gdy chcesz sprawdzić czy nic ważnego nie zostało pominięte.

### Po pracy

Wracając do Terminala (gdzie chodzi serwer), naciśnij `Ctrl + C` żeby zatrzymać aplikację.

Następnym razem - krok 6 i 7 (pomijasz instalację).

---

## Aktualizacja do nowszej wersji

Gdy autor wypuści nową wersję, masz **trzy sposoby** aktualizacji:

### Sposób 1: Skrypt update (zalecany, jeden klik)

W Terminalu, w katalogu `bezpiecznik`:

```bash
./update.sh
```

Skrypt pokaże co się zmieniło, zapyta o potwierdzenie i wszystko zainstaluje. Twoje lokalne zmiany (jeśli były) zostaną zachowane.

### Sposób 2: Ręcznie (dla zaawansowanych)

```bash
cd ~/Documents/bezpiecznik
git pull
source .venv/bin/activate
pip install -r requirements.txt
```

### Sposób 3: Powiadomienie od autora

Autor będzie informował o nowych wersjach (LinkedIn, mail). Każda nowa wersja będzie miała listę zmian (changelog) na GitHub w zakładce **Releases**.

> **Tip:** Przed aktualizacją zamknij aplikację (`Ctrl+C` w Terminalu), gdzie chodzi serwer. Po aktualizacji uruchom ponownie krokiem 6 powyżej.

---

## FAQ

Najczęstsze pytania (zwłaszcza dla osób nietechnicznych): **[FAQ.md](FAQ.md)**

---

## Część techniczna (dla developerów)

### Co to jest

Hybrid PII detection (lokalnie):

- 🤖 **OpenAI Privacy Filter** - kontekstowe PII (PERSON, EMAIL, PHONE, ADDRESS, SECRET, URL)
- 🔧 **Regex layer** - polskie strukturalne identyfikatory (IBAN PL, NIP, PESEL, kod pocztowy)
- 🇵🇱 **Address reklasyfikator** - "ul. Słoneczna 12" + "Aleje Jerozolimskie 100" → ADRES (nie OSOBA)

Dwa frontendy:
- **Bezpiecznik** (port 8000) - FastAPI + React (Babel-in-browser), 3 motywy, polskie etykiety, **drag&drop + paste tabs + dialog confirm + 9 formatów**
- **Gradio legacy** (port 7860) - prosty drag-drop + JSON output

### Setup deweloperski

```bash
cd bezpiecznik
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Bezpiecznik (nowy UI)
uvicorn server:app --port 8000

# Gradio legacy
python app.py
```

### Testy

```bash
.venv/bin/pytest test_pii_regex.py test_server.py -v   # 76/76 PASS
```

### Architektura

```
bezpiecznik/
├── server.py           FastAPI: static + /api/redact, port 8000
├── app.py              Gradio legacy, port 7860
├── pii_service.py      Wspólny pipeline (redact_text)
├── opf_runtime.py      Singleton OPF loader (3 GB shared)
├── pii_regex.py        Regex PL: IBAN, NIP, PESEL, kod, adres + reklasyfikator
├── test_pii_regex.py   55 testów (regex layer)
├── test_server.py      21 testów (API contract + dedup + reklasyfikacja)
├── update.sh           Skrypt aktualizacji dla nietechnicznych
└── web/                Frontend Bezpiecznik
    ├── index.html
    ├── styles.css      3 motywy (minimal-dark / terminal / light)
    ├── app.jsx         Root + WarningStrip + tweaks panel
    ├── editor.jsx      InputPanel (tabs paste/upload) + OutputPanel
    ├── detection-panel.jsx
    ├── data.jsx        SAMPLES + LABEL_META
    └── tweaks-panel.jsx
```

### API

`POST /api/redact` `{text}` → `{detections: [...], redacted_text}`.

Etykiety polskie: `OSOBA, EMAIL, TELEFON, ADRES, URL, DATA, SEKRET, IBAN, NIP, PESEL, KOD`.

### Czego NIE robi

- Hosted version (Phase 2)
- Auth / multi-user
- Batch folder processing
- PDF / DOCX / Excel
- Real-time streaming
- Compliance certification
- Wykrywanie kategorii `ORGANIZATION` (poza taksonomią Privacy Filter)
- Wykrywanie kategorii `DATE` (słabo dla PL - out of scope)

### Status

- **Phase 1** ✅ DONE (2026-04-27 rano) - Setup + Gradio MVP + 55/55 testów
- **Phase 1.5** ✅ DONE (2026-04-27 wieczorem) - Bezpiecznik UI (FastAPI + React, 3 motywy)
- **Phase 2 UX** ✅ DONE (2026-04-28) - Tabs paste/upload + drag&drop + dialog confirm + preview + 9 formatów
- **Phase 2 detection** (planned) - spaCy `pl_core_news_lg` (ORG, fleksja, miasta)

### License

TBD (start private). Privacy Filter sam jest Apache 2.0.

---

> ⚠️ **Output wymaga human review.** Narzędzie to *data minimization aid*, nie compliance certification. RODO wciąż wymaga DPA dla US-vendors.
