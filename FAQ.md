# FAQ - najczęstsze pytania

## Bezpieczeństwo i prywatność

### Czy Bezpiecznik wysyła moje dane do internetu?

**Nie.** Cała analiza odbywa się lokalnie na Twoim komputerze. Po pierwszym uruchomieniu, gdy aplikacja pobiera model AI (jednorazowo, ~3 GB), nie ma już żadnej komunikacji z internetem. Możesz to sprawdzić - odłącz wifi i Bezpiecznik dalej działa.

### Czy mogę używać Bezpiecznika do danych klientów?

Tak, **dlatego powstał**. Wszystko zostaje na Twoim komputerze. Ale pamiętaj:
- Bezpiecznik to **pomoc** w minimalizacji danych, nie certyfikat zgodności z RODO.
- Wynik **zawsze sprawdź wzrokowo** - tryb "Z podświetleniem" pokazuje co zostało wykryte.
- RODO i tak wymaga umowy DPA z dostawcą AI (OpenAI, Anthropic itd.) jeśli przetwarzasz dane klientów - Bezpiecznik tego nie zastępuje.

### Co Bezpiecznik wykrywa najlepiej?

Solidnie wykrywa: **osoby (imiona/nazwiska), e-maile, telefony, IBAN, NIP, PESEL, kody pocztowe, adresy z prefiksem (ul./al./Aleje)**.

Czasem przegapia:
- nazwy firm bez sufiksów (np. "Brandbox", "Codepoint" - bo nie ma "Sp. z o.o.")
- imiona spoza listy 50 najpopularniejszych w Polsce (np. egzotyczne lub archaiczne)
- nietypowe formy odmiany (np. archaiczne wołacze - "Pawle!" jako wezwanie)
- same nazwy miast bez kontekstu (np. samo "Warszawa")
- alias dedup ten samej osoby w różnych formach (np. "Paweł" i "Pawłem Górskim" mogą trafić do osobnych placeholderów - fix w przyszłej wersji)

Właśnie dlatego po każdym maskowaniu **sprawdź wynik wzrokowo** - tryb "Z podświetleniem" pomaga.

### Czy ktoś może podejrzeć moje dane?

Nie. Aplikacja słucha tylko na adresie `localhost` (127.0.0.1), co znaczy, że jest dostępna tylko z Twojego komputera. Inne urządzenia w sieci jej nie widzą.

---

## Instalacja i uruchamianie

### Czy muszę być programistą żeby tego użyć?

Nie. Instrukcja krok po kroku w [README.md](README.md) jest pisana dla osób, które wcześniej nie miały kontaktu z Terminalem. Najtrudniejszy moment to skopiowanie kilku komend - resztę robi komputer.

### Działa na Windowsie?

Aktualnie testowane tylko na **Macu (Apple Silicon)**. Na Windowsie powinno działać po analogicznych krokach (instalacja Pythona, git clone, pip install), ale autor tego nie weryfikował.

### Działa na Macu z procesorem Intel?

Powinno, ale nie było testowane. Modele AI mogą być wolniejsze (CPU bez akceleracji Apple Silicon).

### Ile zajmuje miejsca?

- Sam kod Bezpiecznika: ~5 MB
- Środowisko Python z bibliotekami: ~500 MB
- Model AI (pobiera się przy pierwszym użyciu): ~3 GB
- **Łącznie: ~3.5 GB**

### Czy aplikacja włącza się przy starcie Maca?

Nie - musisz uruchomić ją ręcznie (krok 6 w README). Jeśli chcesz auto-start, daj znać autorowi.

### Czy mogę uruchomić Bezpiecznika z aplikacji typu Dock/menubar?

Aktualnie nie. Trzeba mieć otwarte okno Terminala. **Phase 2** zakłada dodanie Quick Action (right-click w Finderze) - jeszcze nie zrobione.

---

## Użytkowanie

### Co to są te `<OSOBA_1>`, `<EMAIL_2>` w wyniku?

To **placeholdery** - zamienniki danych osobowych. Bezpiecznik utrzymuje stałe oznaczenia: jeśli "Anna Nowak" pojawia się 3 razy w tekście, za każdym razem dostanie ten sam placeholder `<OSOBA_1>`. AI wciąż rozumie, że to ta sama osoba, ale nie wie kim jest naprawdę.

### Co jeśli Bezpiecznik coś przegapi?

1. **Sprawdź zawsze wzrokowo** - przełącz na tryb "Z podświetleniem" i przejdź wzrokiem po tekście.
2. Jeśli coś brakuje, **edytuj tekst w panelu wejściowym**, dopisz coś co Bezpiecznik wykryje (np. zamiast samego "Brandbox" napisz "firma Brandbox") i powtórz analizę.
3. Albo ręcznie zamaskuj brakujące fragmenty przed wysłaniem.

### Co jeśli Bezpiecznik zamaskuje coś, co nie powinno być zamaskowane?

W panelu **Wykryte dane** (z prawej) możesz odznaczyć kategorię - np. ukryć wszystkie "DATA" jeśli daty są dla Ciebie ważne. Zamaskowane zostaną tylko zaznaczone kategorie.

Albo po prostu skopiuj wynik i ręcznie podmień to, co zostało za bardzo zamaskowane.

### Mogę wgrać PDF / DOCX / Excel?

Aktualnie **nie**. Obsługujemy `.md`, `.txt`, `.csv`, `.tsv`, `.json`, `.log`, `.html`, `.srt`, `.vtt` (formaty tekstowe).

Workaround dla PDF/DOCX:
- PDF: otwórz w Podglądzie, **Plik → Eksportuj jako tekst...** lub skopiuj treść do TextEdit
- DOCX: otwórz w Pages/Word, skopiuj treść, wklej w panel **Wklej tekst**
- Excel: zapisz jako CSV

### Mogę przeanalizować cały folder na raz?

Aktualnie **nie**. Każdy plik osobno. Phase 2 zakłada batch processing.

### Czy wynik mogę edytować?

Tak. Po analizie kliknij **Edytuj tekst** (w trybie upload) lub po prostu zmień tekst w panelu wejściowym - następna analiza użyje nowej wersji.

---

## Aktualizacja

### Skąd będę wiedzieć, że wyszła nowa wersja?

- Skrypt `./update.sh` sprawdza i pokazuje, czy jest coś nowego.
- Autor będzie informował o większych aktualizacjach (LinkedIn, mail).
- Lista zmian (changelog) jest na GitHub w zakładce **Releases**.

### Czy aktualizacja zachowa moje ustawienia?

Twoje motywy, rozmiar tekstu i pozycja paneli są zapisane lokalnie - nie znikną przy aktualizacji.

### Co jeśli aktualizacja się nie powiedzie?

Skrypt `update.sh` ma zabezpieczenie: jeśli coś idzie nie tak, **przerywa update bez modyfikacji** Twoich plików. W przypadku problemów:

1. Zrób screenshot błędu
2. Wyślij autorowi
3. Tymczasowo używaj poprzedniej wersji

### Co jeśli używam starej wersji i coś nie działa?

Najpierw spróbuj zaktualizować (`./update.sh`). 90% problemów to fixy w nowych wersjach.

---

## Problemy techniczne

### "command not found: python3"

Pythona nie ma. Pobierz z [python.org/downloads](https://www.python.org/downloads/), wybierz wersję 3.12 lub nowszą. Po instalacji **zamknij i otwórz Terminal ponownie**.

### "command not found: git"

Wpisz `git --version` w Terminalu - macOS sam zaproponuje instalację Xcode Command Line Tools. Kliknij Install.

### "Permission denied" przy `./update.sh`

W Terminalu wykonaj raz:

```bash
chmod +x update.sh
```

Potem `./update.sh` zadziała.

### "Address already in use" przy uruchamianiu serwera

Inny program zajmuje port 8000 (albo poprzednia instancja Bezpiecznika nie wyłączyła się). Rozwiązania:

1. Wyłącz wszystkie okna Terminala i otwórz nowe.
2. Lub uruchom na innym porcie:
   ```bash
   .venv/bin/uvicorn server:app --port 8001
   ```
   Wtedy w przeglądarce wpisz `http://localhost:8001`.

### Pierwsze maskowanie trwa wieczność

Pierwsze uruchomienie ściąga model AI (~3 GB). To może potrwać 5-15 minut zależnie od łącza. **Nie zamykaj Terminala** w tym czasie.

Następne maskowania są natychmiastowe (model już jest na dysku).

### Aplikacja zamarła / pokazuje błąd

1. W Terminalu (gdzie uruchomiony jest serwer) naciśnij `Ctrl+C` żeby zatrzymać.
2. Uruchom ponownie: `.venv/bin/uvicorn server:app --port 8000`
3. Odśwież stronę w przeglądarce (`⌘+R`).

Jeśli błąd się powtarza - screenshot + wyślij autorowi.

### Czy mogę odinstalować Bezpiecznika?

Tak. W Finderze przejdź do `~/Documents/bezpiecznik` (lub gdzie zainstalowałeś) i wyrzuć cały folder do kosza. Model AI w tle (`~/.cache/huggingface/`) możesz też usunąć - to ~3 GB. Aplikacja nie zostawia żadnych innych śladów na komputerze.

---

## Współpraca

### Mogę zaproponować nowy feature?

Tak - napisz do autora (LinkedIn, mail, GitHub Issues jeśli masz dostęp).

### Mogę używać Bezpiecznika komercyjnie?

Skontaktuj się z autorem - aktualnie repo jest prywatne, licencja TBD.

### Mogę dodać własną kategorię PII (np. numer dowodu)?

Tak, ale wymaga edycji kodu (`pii_regex.py`). Jeśli to powtarzający się use-case - daj znać autorowi.

---

## Reszta

### Skąd nazwa "Bezpiecznik"?

Bo jest jak bezpiecznik elektryczny - gdy coś idzie źle, **przerywa obwód** zanim Twoje wrażliwe dane trafią do ChatGPT/Claude. Tylko zamiast prądu, blokuje wyciek danych osobowych.

### Mam jeszcze pytanie - gdzie pisać?

LinkedIn: [Robert Szewczyk](https://linkedin.com/in/szewowsky) lub mail (jeśli go masz).
